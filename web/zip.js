/* OpenDrop - minimal ZIP writer, no dependencies.
 *
 * Two jobs on this app: a folder picked or dropped on the Send tab is
 * packed here before it travels (the PC's share folder only ever sees a
 * plain .zip), and several files ticked on the Download tab come back
 * as a single archive.
 *
 * Compression uses the platform's CompressionStream("deflate-raw") when
 * the browser has it (every current engine); anywhere else - or when
 * compression does not pay off on an already-compressed file - the entry
 * is stored raw, which is still a perfectly valid ZIP.
 *
 * No ZIP64: an entry or an archive over 4 GB throws { tooLarge: true }
 * and the caller falls back to sending the files loose.
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

    function crc32(bytes) {
        var c = 0xFFFFFFFF;
        for (var i = 0; i < bytes.length; i++) {
            c = CRC_TABLE[(c ^ bytes[i]) & 0xFF] ^ (c >>> 8);
        }
        return (c ^ 0xFFFFFFFF) >>> 0;
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

    function deflateRaw(bytes) {
        if (typeof global.CompressionStream === "undefined" ||
            typeof global.Response === "undefined" || !global.Blob) {
            return Promise.resolve(null);
        }
        var piped;
        try {
            piped = new Blob([bytes]).stream()
                .pipeThrough(new CompressionStream("deflate-raw"));
        } catch (e) {
            return Promise.resolve(null);
        }
        return new Response(piped).arrayBuffer().then(function (buf) {
            return new Uint8Array(buf);
        }).catch(function () {
            return null;    // engine refused: caller stores the entry
        });
    }

    /* entries: [{ name: "path/in/zip.ext", file: File|Blob, date?: Date }]
       Returns Promise<Blob> (application/zip). Names are written as
       UTF-8 with the language flag set, so accents survive everywhere. */
    function buildZip(entries) {
        var parts = [];
        var central = [];
        var offset = 0;
        var encoder = new TextEncoder();

        var chain = Promise.resolve();
        entries.forEach(function (entry) {
            chain = chain.then(function () {
                return entry.file.arrayBuffer().then(function (buf) {
                    var bytes = new Uint8Array(buf);
                    return deflateRaw(bytes).then(function (deflated) {
                        var useDeflate = !!(deflated && deflated.length < bytes.length);
                        var data = useDeflate ? deflated : bytes;
                        if (bytes.length > 0xFFFFFFFF ||
                            offset + data.length + 30 > 0xFFFFFFFF) {
                            var err = new Error("entry too large for a classic zip");
                            err.tooLarge = true;
                            throw err;
                        }
                        var nameBytes = encoder.encode(entry.name);
                        var stamp = dosStamp(entry.date ||
                            (entry.file.lastModified ? new Date(entry.file.lastModified) : null));
                        var crc = crc32(bytes);

                        var local = new Uint8Array(30 + nameBytes.length);
                        var lv = new DataView(local.buffer);
                        lv.setUint32(0, 0x04034b50, true);       // local header signature
                        lv.setUint16(4, 20, true);               // version needed
                        lv.setUint16(6, 0x0800, true);           // UTF-8 names
                        lv.setUint16(8, useDeflate ? 8 : 0, true);
                        lv.setUint16(10, stamp.time, true);
                        lv.setUint16(12, stamp.date, true);
                        lv.setUint32(14, crc, true);
                        lv.setUint32(18, data.length, true);
                        lv.setUint32(22, bytes.length, true);
                        lv.setUint16(26, nameBytes.length, true); // extra stays 0
                        local.set(nameBytes, 30);

                        var cd = new Uint8Array(46 + nameBytes.length);
                        var cv = new DataView(cd.buffer);
                        cv.setUint32(0, 0x02014b50, true);       // central signature
                        cv.setUint16(4, 20, true);               // version made by
                        cv.setUint16(6, 20, true);               // version needed
                        cv.setUint16(8, 0x0800, true);
                        cv.setUint16(10, useDeflate ? 8 : 0, true);
                        cv.setUint16(12, stamp.time, true);
                        cv.setUint16(14, stamp.date, true);
                        cv.setUint32(16, crc, true);
                        cv.setUint32(20, data.length, true);
                        cv.setUint32(24, bytes.length, true);
                        cv.setUint16(28, nameBytes.length, true);
                        cv.setUint32(42, offset, true);          // local header offset
                        cd.set(nameBytes, 46);

                        parts.push(local, data);
                        central.push(cd);
                        offset += local.length + data.length;
                    });
                });
            });
        });

        return chain.then(function () {
            if (entries.length > 0xFFFF) {
                var err = new Error("too many entries for a classic zip");
                err.tooLarge = true;
                throw err;
            }
            var cdSize = 0;
            central.forEach(function (cd) { cdSize += cd.length; });

            var eocd = new Uint8Array(22);
            var ev = new DataView(eocd.buffer);
            ev.setUint32(0, 0x06054b50, true);                  // end of central dir
            ev.setUint16(8, entries.length, true);
            ev.setUint16(10, entries.length, true);
            ev.setUint32(12, cdSize, true);
            ev.setUint32(16, offset, true);

            parts.push.apply(parts, central);
            parts.push(eocd);
            return new Blob(parts, { type: "application/zip" });
        });
    }

    global.OpenDropZip = { buildZip: buildZip, crc32: crc32 };
})(typeof window !== "undefined" ? window : globalThis);
