/* OpenDrop - test harness: drives the web zip engine from Node.
 *
 * Usage: node tests/zip_harness.mjs <specJsonPath> <outZipPath>
 *
 * Spec JSON:
 *   { entries: [{ name, size, kind: "random"|"text", text? }],
 *     mode?, password?, forceZip64?, cancelAfterBytes? }
 *
 * password (a non-empty string) switches every entry to ZipCrypto
 * encryption; it is passed straight to buildZip. The wrong-password
 * negative test is a second spec run whose password differs from the
 * one the suite opens that zip with (see test_zip_web.py).
 *
 * Entry payloads are also written to <outZipPath>.expect/<name> (path
 * separators replaced by "_"), so the Python suite (test_zip_web.py)
 * can byte-compare extracted content against the exact originals.
 *
 * Prints exactly one JSON line on stdout:
 *   { ok, cancelled?, progress: [doneRaw...], totalRaw, error? }
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { randomFillSync } from "node:crypto";

import "../web/zip.js";   // side effect: globalThis.OpenDropZip

const MB = 1024 * 1024;

function fail(message) {
    process.stderr.write(message + "\n");
    process.exit(2);
}

const argv = process.argv.slice(2);
if (argv.length < 2) {
    fail("usage: node tests/zip_harness.mjs <specJsonPath> <outZipPath>");
}
const [specPath, outPath] = argv;

let spec;
try {
    spec = JSON.parse(readFileSync(specPath, "utf8"));
} catch (e) {
    fail("cannot read spec " + specPath + ": " + e.message);
}
if (!globalThis.OpenDropZip) {
    fail("web/zip.js did not set globalThis.OpenDropZip");
}

// Build the entries as Blobs; random payloads are generated in 1 MB
// buffers and every payload is kept as a sidecar expectation file.
const expectDir = outPath + ".expect";
mkdirSync(expectDir, { recursive: true });
const entries = (spec.entries || []).map(function (e) {
    let bytes;
    if (e.kind === "random") {
        bytes = new Uint8Array(e.size);
        for (let off = 0; off < bytes.length; off += MB) {
            randomFillSync(bytes, off, Math.min(MB, bytes.length - off));
        }
    } else {
        bytes = new TextEncoder().encode(e.text || "");
    }
    writeFileSync(join(expectDir, e.name.replace(/[/\\]/g, "_")), bytes);
    return { name: e.name, file: new Blob([bytes]) };
});

// Progress + cancellation wiring: every event is recorded, and the
// first event at or past cancelAfterBytes aborts the AbortController.
const progress = [];
let totalRaw = 0;
for (const e of entries) {
    totalRaw += e.file.size;
}
let aborter = null;
let cancelled = false;
const opts = {
    mode: spec.mode,                    // undefined -> engine default "deflate"
    password: spec.password,            // non-empty string -> ZipCrypto
    forceZip64: !!spec.forceZip64,
    onProgress: function (doneRaw) {
        progress.push(doneRaw);
        if (spec.cancelAfterBytes != null && !cancelled &&
            doneRaw >= spec.cancelAfterBytes) {
            cancelled = true;
            aborter.abort();
        }
    },
};
if (spec.cancelAfterBytes != null) {
    aborter = new AbortController();
    opts.signal = aborter.signal;
}

let ok = false;
let error = null;
try {
    const blob = await globalThis.OpenDropZip.buildZip(entries, opts);
    ok = true;
    if (!cancelled) {
        writeFileSync(outPath, Buffer.from(await blob.arrayBuffer()));
    }
} catch (e) {
    cancelled = cancelled || !!(e && e.cancelled);
    error = String((e && e.message) || e);
}

const result = { ok: ok, progress: progress, totalRaw: totalRaw };
if (cancelled) result.cancelled = true;
if (error != null) result.error = error;
process.stdout.write(JSON.stringify(result) + "\n");
process.exit(0);
