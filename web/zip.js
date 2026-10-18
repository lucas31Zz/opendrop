/* OpenDrop - streaming ZIP writer, no dependencies.
 *
 * Two jobs on this app: a folder picked or dropped on the Send tab is
 * packed here before it travels (the PC's share folder only ever sees
 * a plain .zip), and several files ticked on the Download tab come back
 * as a single archive.
 *
 * Files are read in chunks and fed straight to the output (optionally
 * through the platform's CompressionStream("deflate-raw"); where that
 * API is missing, entries are stored raw - still a perfectly valid
 * ZIP), so RAM stays flat whatever the folder weighs. The caller gets
 * byte-count progress through opts.onProgress, and opts.signal (an
 * AbortSignal) cancels a running zip: the rejection carries
 * cancelled = true.
 *
 * ZIP64 (APPNOTE 4.5) kicks in automatically whenever an entry, the
 * archive or the entry count crosses the classic 4 GB / 64 K limits,
 * or when opts.forceZip64 asks for it, so archives of any size stay
 * readable by standard tools.
 *
 * opts.password additionally wraps every entry in ZipCrypto (PKWARE
 * "classic") encryption - honest, deliberately weak password
 * protection, a lock against the curious rather than against an
 * attacker - with no dependencies and readable by standard tools.
 */
(function (global) {
    "use strict";

    var CRC_TABLE = (function () {
        var table = new Uint32Array(256);
        for (var n = 0; n < 256; n++) {
            var c = n;
            for (var k = 0; k < 8; k++) {
                c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
            }
            table[n] = c >>> 0;
        }
        return table;
    })();

    // Running CRC step: feeds bytes into a not-yet-finalized CRC state
    // (start from 0xFFFFFFFF, XOR with 0xFFFFFFFF at the end).
    function crc32Step(c, bytes) {
        for (var i = 0; i < bytes.length; i++) {
            c = CRC_TABLE[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8);
        }
        return c >>> 0;
    }

    function crc32(bytes) {
        return (crc32Step(0xFFFFFFFF, bytes) ^ 0xFFFFFFFF) >>> 0;
    }

    /* ZipCrypto (PKWARE "classic") encryption: an optional, deliberately
       weak password lock. The keys k0/k1/k2 seed from the UTF-8 password
       bytes and every output byte is XORed with a keystream driven by the
       same CRC32 table; the schedule advances with each PLAINTEXT byte,
       exactly mirroring a ZipCrypto decryptor. */
    var ENC_HEADER_LEN = 12;   // 11 random bytes + 1 password check byte

    function zipCrypto(passwordBytes) {
        this.k0 = 0x12345678;
        this.k1 = 0x23456789;
        this.k2 = 0x34567890;
        for (var i = 0; i < passwordBytes.length; i++) {
            this.update(passwordBytes[i]);
        }
    }

    zipCrypto.prototype.update = function (b) {
        this.k0 = CRC_TABLE[(this.k0 ^ b) & 0xFF] ^ (this.k0 >>> 8);
        this.k1 = Math.imul(this.k1 + (this.k0 & 0xFF), 134775813) + 1 >>> 0;
        this.k2 = CRC_TABLE[(this.k2 ^ (this.k1 >>> 24)) & 0xFF] ^ (this.k2 >>> 8);
    };

    // One plaintext byte -> ciphertext byte. The keystream formula
    // (k2|2) * ((k2|2) ^ 1) >> 8 must be exact in 32 bits - a plain JS
    // multiply rounds it to a float and breaks compatibility - so the
    // product runs through Math.imul.
    zipCrypto.prototype.encryptByte = function (plain) {
        var t = this.k2 | 2;
        var cipher = plain ^ ((Math.imul(t, t ^ 1) >>> 8) & 0xFF);
        this.update(plain);
        return cipher;
    };

    function encryptInPlace(state, bytes) {
        for (var i = 0; i < bytes.length; i++) {
            bytes[i] = state.encryptByte(bytes[i]);
        }
    }

    // WebCrypto where available; the fallback keeps ancient runtimes
    // working (the 11 bytes only add diffusing entropy, not secrecy).
    function fillRandom(bytes) {
        if (global.crypto && typeof global.crypto.getRandomValues === "function") {
            global.crypto.getRandomValues(bytes);
        } else {
            for (var i = 0; i < bytes.length; i++) {
                bytes[i] = (Math.random() * 256) | 0;
            }
        }
    }

    // The ZIP clock: MS-DOS date/time, two-second resolution, 1980-2107.
    function dosStamp(date) {
        var d = date || new Date();
        var year = Math.min(2107, Math.max(1980, d.getFullYear()));
        return {
            time: ((d.getHours() << 11) | (d.getMinutes() << 5) |
                   Math.floor(d.getSeconds() / 2)) & 0xFFFF,
            date: (((year - 1980) << 9) | ((d.getMonth() + 1) << 5) |
                   d.getDate()) & 0xFFFF
        };
    }

    var STAGE_SIZE = 8 * 1024 * 1024;   // staging buffer: keeps RAM flat
    var CLASSIC_MAX = 0xFFFFFFFF;       // classic ZIP field limit
    var CLASSIC_ENTRIES_MAX = 0xFFFF;

    function cancelledError() {
        var err = new Error("zip cancelled");
        err.cancelled = true;
        return err;
    }

    function hasDeflateEngine() {
        if (typeof global.CompressionStream === "undefined") return false;
        try {
            new global.CompressionStream("deflate-raw");
            return true;
        } catch (e) {
            return false;    // engine refused deflate-raw: store instead
        }
    }

    /* entries: [{ name: "path/in/zip.ext", file: File|Blob, date?: Date }]
       opts: { mode: "deflate"|"store" (default "deflate"),
               signal?: AbortSignal,
               onProgress?: (doneRaw, totalRaw) => void,
               forceZip64?: boolean,
               password?: string }
       Returns Promise<Blob> (application/zip). Names are written as
       UTF-8 with the language flag set, so accents survive everywhere.
       Rejects with an error carrying cancelled = true when signal
       aborts. onProgress reports the raw bytes consumed so far out of
       the total raw bytes of every entry.

       A non-empty opts.password switches every entry to ZipCrypto
       encryption: the UTF-8 password bytes seed the key schedule, each
       entry's stored bytes are preceded by a 12-byte encryption header
       (11 random bytes + a check byte carrying the high byte of the
       plaintext CRC), and general-purpose bit 0 is set in both the
       local and the central header. Compressed sizes count the header,
       CRC fields keep the plaintext CRC. Absent or empty = a plain
       archive, exactly as without the option. */
    function buildZip(entries, opts) {
        opts = opts || {};
        var signal = opts.signal || null;
        var onProgress = typeof opts.onProgress === "function" ? opts.onProgress : null;
        var forceZip64 = !!opts.forceZip64;
        var useDeflate = opts.mode !== "store" && hasDeflateEngine();

        var parts = [];        // output parts handed to the Blob
        var central = [];      // central directory records
        var offset = 0;        // archive offset of the next local header
        var encoder = new TextEncoder();
        var passwordBytes = typeof opts.password === "string" && opts.password ?
            encoder.encode(opts.password) : null;
        var encFlag = passwordBytes ? 1 : 0;
        var totalRaw = 0;
        var doneRaw = 0;
        var anyZip64 = false;

        entries.forEach(function (entry) {
            totalRaw += (entry.file && entry.file.size) || 0;
        });

        function throwIfAborted() {
            if (signal && signal.aborted) throw cancelledError();
        }

        // One entry: stream the plaintext through the progress/CRC
        // transform (and the compressor in deflate mode), stage the
        // output, then prepend the local header once the sizes and CRC
        // are known.
        async function addEntry(entry) {
            throwIfAborted();
            var nameBytes = encoder.encode(entry.name);
            var stamp = dosStamp(entry.date ||
                (entry.file && entry.file.lastModified ?
                 new Date(entry.file.lastModified) : null));
            var rawSize = (entry.file && entry.file.size) || 0;

            var headerSlot = parts.length;
            parts.push(null);   // the local header lands here, in order
            var cryptSlot = -1;
            if (passwordBytes) {
                cryptSlot = parts.length;
                parts.push(null);   // the 12-byte encryption header too
            }

            var stage = new Uint8Array(STAGE_SIZE);
            var stageLen = 0;
            function stageEmit(bytes) {
                var off = 0;
                while (off < bytes.length) {
                    var n = Math.min(STAGE_SIZE - stageLen, bytes.length - off);
                    stage.set(bytes.subarray(off, off + n), stageLen);
                    stageLen += n;
                    off += n;
                    if (stageLen === STAGE_SIZE) {   // flush full buffer
                        parts.push(stage);
                        stage = new Uint8Array(STAGE_SIZE);
                        stageLen = 0;
                    }
                }
            }

            // Running CRC over the plaintext + raw-byte progress +
            // cancellation, all on the same pass through the chunks.
            var crcRun = 0xFFFFFFFF;
            var progress = new TransformStream({
                transform: function (chunk, controller) {
                    throwIfAborted();
                    crcRun = crc32Step(crcRun, chunk);
                    doneRaw += chunk.length;
                    if (onProgress) onProgress(doneRaw, totalRaw);
                    throwIfAborted();   // onProgress may have aborted
                    controller.enqueue(chunk);
                }
            });

            var source = entry.file.stream().pipeThrough(progress);
            var piped = useDeflate ?
                source.pipeThrough(new global.CompressionStream("deflate-raw")) :
                source;
            var reader = piped.getReader();
            var compSize = 0;
            try {
                for (;;) {
                    var step = await reader.read();
                    if (step.done) break;
                    compSize += step.value.length;
                    stageEmit(step.value);
                    throwIfAborted();
                }
            } finally {
                reader.cancel().catch(function () {});   // no-op when done
            }
            throwIfAborted();

            var crc = (crcRun ^ 0xFFFFFFFF) >>> 0;
            var dataLen = compSize + (passwordBytes ? ENC_HEADER_LEN : 0);
            var zip64 = forceZip64 || rawSize >= CLASSIC_MAX ||
                dataLen >= CLASSIC_MAX || offset >= CLASSIC_MAX;
            if (zip64) anyZip64 = true;

            // ZipCrypto pass over the STORED bytes: a fresh key schedule
            // per entry (seeded with the password) runs first over the
            // 12-byte header, then over every staged byte in order; the
            // local header slots above stay reserved until it is done.
            if (passwordBytes) {
                var crypt = new zipCrypto(passwordBytes);
                var encHdr = new Uint8Array(ENC_HEADER_LEN);
                fillRandom(encHdr.subarray(0, ENC_HEADER_LEN - 1));
                encHdr[ENC_HEADER_LEN - 1] = (crc >>> 24) & 0xFF; // check byte
                encryptInPlace(crypt, encHdr);
                for (var pi = cryptSlot + 1; pi < parts.length; pi++) {
                    encryptInPlace(crypt, parts[pi]);
                }
                encryptInPlace(crypt, stage.subarray(0, stageLen));
                parts[cryptSlot] = encHdr;
            }

            var local = new Uint8Array(30 + nameBytes.length + (zip64 ? 20 : 0));
            var lv = new DataView(local.buffer);
            lv.setUint32(0, 0x04034b50, true);       // local header signature
            lv.setUint16(4, zip64 ? 45 : 20, true);  // version needed
            lv.setUint16(6, 0x0800 | encFlag, true); // UTF-8 names + encryption
            lv.setUint16(8, useDeflate ? 8 : 0, true);
            lv.setUint16(10, stamp.time, true);
            lv.setUint16(12, stamp.date, true);
            lv.setUint32(14, crc, true);
            lv.setUint32(18, zip64 ? 0xFFFFFFFF : dataLen, true);
            lv.setUint32(22, zip64 ? 0xFFFFFFFF : rawSize, true);
            lv.setUint16(26, nameBytes.length, true);
            lv.setUint16(28, zip64 ? 20 : 0, true);
            local.set(nameBytes, 30);
            if (zip64) {    // zip64 extra field: uncomp then comp, 8 bytes each
                var l64 = new DataView(local.buffer, 30 + nameBytes.length);
                l64.setUint16(0, 0x0001, true);
                l64.setUint16(2, 16, true);
                l64.setBigUint64(4, BigInt(rawSize), true);
                l64.setBigUint64(12, BigInt(dataLen), true);
            }

            var cd = new Uint8Array(46 + nameBytes.length + (zip64 ? 28 : 0));
            var cv = new DataView(cd.buffer);
            cv.setUint32(0, 0x02014b50, true);       // central signature
            cv.setUint16(4, zip64 ? 45 : 20, true);  // version made by
            cv.setUint16(6, zip64 ? 45 : 20, true);  // version needed
            cv.setUint16(8, 0x0800 | encFlag, true);
            cv.setUint16(10, useDeflate ? 8 : 0, true);
            cv.setUint16(12, stamp.time, true);
            cv.setUint16(14, stamp.date, true);
            cv.setUint32(16, crc, true);
            cv.setUint32(20, zip64 ? 0xFFFFFFFF : dataLen, true);
            cv.setUint32(24, zip64 ? 0xFFFFFFFF : rawSize, true);
            cv.setUint16(28, nameBytes.length, true);
            cv.setUint16(30, zip64 ? 28 : 0, true); // extra field length
            cv.setUint32(42, zip64 ? 0xFFFFFFFF : offset, true); // header offset
            cd.set(nameBytes, 46);
            if (zip64) {    // zip64 extra field: uncomp, comp, offset
                var c64 = new DataView(cd.buffer, 46 + nameBytes.length);
                c64.setUint16(0, 0x0001, true);
                c64.setUint16(2, 24, true);
                c64.setBigUint64(4, BigInt(rawSize), true);
                c64.setBigUint64(12, BigInt(dataLen), true);
                c64.setBigUint64(20, BigInt(offset), true);
            }

            if (stageLen > 0) parts.push(stage.slice(0, stageLen));
            parts[headerSlot] = local;   // header first, then its data
            central.push(cd);
            offset += local.length + dataLen;
        }

        var chain = Promise.resolve();
        entries.forEach(function (entry) {
            chain = chain.then(function () { return addEntry(entry); });
        });

        return chain.then(function () {
            throwIfAborted();
            var cdOffset = offset;
            var cdSize = 0;
            central.forEach(function (cd) { cdSize += cd.length; });
            var count = entries.length;
            var zip64Tail = anyZip64 || forceZip64 ||
                count >= CLASSIC_ENTRIES_MAX || cdOffset >= CLASSIC_MAX ||
                cdSize >= CLASSIC_MAX;

            var tail = [];
            if (zip64Tail) {    // zip64 EOCD record + locator, before the EOCD
                var z64 = new Uint8Array(56);
                var z64v = new DataView(z64.buffer);
                z64v.setUint32(0, 0x06064b50, true);
                z64v.setBigUint64(4, BigInt(44), true);    // record size
                z64v.setUint16(12, 45, true);              // version made by
                z64v.setUint16(14, 45, true);              // version needed
                z64v.setUint32(16, 0, true);               // this disk
                z64v.setUint32(20, 0, true);               // cd start disk
                z64v.setBigUint64(24, BigInt(count), true);    // entries here
                z64v.setBigUint64(32, BigInt(count), true);    // entries total
                z64v.setBigUint64(40, BigInt(cdSize), true);
                z64v.setBigUint64(48, BigInt(cdOffset), true);

                var loc = new Uint8Array(20);
                var locv = new DataView(loc.buffer);
                locv.setUint32(0, 0x07064b50, true);
                locv.setUint32(4, 0, true);                 // zip64 EOCD disk
                locv.setBigUint64(8, BigInt(cdOffset + cdSize), true);
                locv.setUint32(16, 1, true);                // total disks
                tail.push(z64, loc);
            }

            var eocd = new Uint8Array(22);
            var ev = new DataView(eocd.buffer);
            ev.setUint32(0, 0x06054b50, true);              // end of central dir
            ev.setUint16(8, zip64Tail ? 0xFFFF : count, true);
            ev.setUint16(10, zip64Tail ? 0xFFFF : count, true);
            ev.setUint32(12, zip64Tail ? 0xFFFFFFFF : cdSize, true);
            ev.setUint32(16, zip64Tail ? 0xFFFFFFFF : cdOffset, true);
            tail.push(eocd);

            parts.push.apply(parts, central);
            parts.push.apply(parts, tail);
            return new Blob(parts, { type: "application/zip" });
        });
    }

    global.OpenDropZip = { buildZip: buildZip, crc32: crc32 };
})(typeof window !== "undefined" ? window : globalThis);
