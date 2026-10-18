"""Engine tests for web/zip.js: streaming ZIP64, modes, progress, cancel,
ZipCrypto password protection.

The browser engine is driven from Node (tests/zip_harness.mjs, no
dependencies) and every produced archive is verified with Python's
zipfile - an independent implementation. Entry payloads travel as
sidecar files (<out>.expect/<name>) so the suite can byte-compare the
extracted content against the exact originals fed to buildZip.
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import zipfile

from tests.conftest import TestResult

r = TestResult()

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARNESS = os.path.join(REPO, "tests", "zip_harness.mjs")

# 1 KB UTF-8 payload with accents + CJK (the plan's unicode entry).
TEXT = "OpenDrop streaming zip - \u00e9t\u00e9, \u7167\u7247, \u2615\n" * 30
TEXT_BYTES = TEXT.encode("utf-8")
BIN_NAME = "payload.bin"
TEXT_NAME = "\u00e9t\u00e9-\u7167\u7247.txt"
ENTRIES = [
    {"name": BIN_NAME, "size": 1024 * 1024, "kind": "random"},
    {"name": TEXT_NAME, "kind": "text", "text": TEXT},
]
TOTAL_RAW = 1024 * 1024 + len(TEXT_BYTES)

# ZipCrypto passwords: the round-trip password, a mismatching one for the
# negative tests, and a unicode one (its UTF-8 bytes seed the keys).
PWD = "secret123"
PWD_BYTES = PWD.encode("utf-8")
WRONG_PWD = "wrong-password"
UNI_PWD = "\u00e9t\u00e9\U0001F512"   # "été" + lock emoji


def _node_available():
    try:
        p = subprocess.run(["node", "--version"], capture_output=True,
                           text=True, timeout=30)
        return p.returncode == 0, p.stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)


def _run_harness(workdir, tag, spec):
    """Write the spec JSON, run the harness, parse its single JSON line."""
    spec_path = os.path.join(workdir, tag + ".spec.json")
    out_path = os.path.join(workdir, tag + ".zip")
    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False)
    proc = subprocess.run(["node", HARNESS, spec_path, out_path],
                          capture_output=True, cwd=REPO,
                          encoding="utf-8", errors="replace", timeout=180)
    line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    try:
        res = json.loads(line)
    except ValueError:
        res = {"ok": False,
               "error": "no JSON line (rc=%d): %s"
                        % (proc.returncode,
                           (proc.stderr or proc.stdout).strip()[:300])}
    return res, out_path


def _sidecars(out_path):
    """{entry name: exact payload bytes} from the harness sidecars."""
    got = {}
    for name in (BIN_NAME, TEXT_NAME):
        safe = name.replace("/", "_").replace("\\", "_")
        with open(os.path.join(out_path + ".expect", safe), "rb") as f:
            got[name] = f.read()
    return got


def _open_zip(out_path):
    """(ZipFile|None, raw bytes|None, error|None) - never raises."""
    if not os.path.exists(out_path):
        return None, None, "zip file not written: " + out_path
    with open(out_path, "rb") as f:
        data = f.read()
    try:
        return zipfile.ZipFile(io.BytesIO(data)), data, None
    except Exception as e:   # suite reports failures, it never crashes
        return None, data, "%s: %s" % (type(e).__name__, e)


def _check_roundtrip(tag, zf, expect):
    names = zf.namelist()
    r.check("%s: both entry names present" % tag,
            BIN_NAME in names and TEXT_NAME in names, ascii(names))
    bad = zf.testzip()
    r.check("%s: testzip() clean" % tag, bad is None, ascii(bad))
    for name in (BIN_NAME, TEXT_NAME):
        got = zf.read(name)
        r.check("%s: %s bytes match the payload" % (tag, "text entry"
                if name == TEXT_NAME else "random entry"),
                got == expect[name],
                "%d extracted vs %d expected bytes" % (len(got),
                                                       len(expect[name])))


def _local_flag_bits(data, zinfo):
    """General-purpose bit 0 from the LOCAL header (zipfile.filelist only
    carries the central header's copy). Local header layout: signature
    (4 bytes) + version needed (2) + flags (2)."""
    off = zinfo.header_offset
    return int.from_bytes(data[off + 6:off + 8], "little") & 0x1


def _check_password_roundtrip(tag, zf, expect, pwd):
    """One check: both entries extract byte-exact with the given password.

    A missing entry name lands in `problems` too (zipfile.open raises
    KeyError), and ZipExtFile re-checks the CRC32 while reading, so a
    clean full read plus this byte comparison proves decryption end to
    end without needing testzip().
    """
    problems = []
    for name in (BIN_NAME, TEXT_NAME):
        try:
            with zf.open(name, pwd=pwd) as f:
                got = f.read()
        except Exception as e:   # wrong key must be reported, not crash
            problems.append("%s: %s: %s" % (name, type(e).__name__, e))
            continue
        if got != expect[name]:
            problems.append("%s: %d extracted vs %d expected bytes"
                            % (name, len(got), len(expect[name])))
    r.check("%s: entries decrypt byte-exact with the password" % tag,
            not problems, "; ".join(problems) or "both entries match")


def _wrong_password_mode(work, tag, spec, open_pwd):
    """(harness_ok, modes): try to open the spec-built archive with a
    password that does not match the one it was built with.

    Normally the 12-byte encryption header's check byte rejects the wrong
    key at open() time with RuntimeError. The header's first 11 bytes are
    random, so with probability 1/256 the check byte accidentally
    collides and the failure surfaces later instead (BadZipFile on the
    CRC, zlib.error on garbage deflate); in that case build a fresh
    archive (fresh header) and retry, so the suite reports the real
    failure mode deterministically.
    """
    modes = []
    harness_ok = False
    for _ in range(3):
        res, out = _run_harness(work, tag, spec)
        harness_ok = res.get("ok") is True
        zf, data, err = _open_zip(out)
        if zf is None:
            modes.append("zip not readable: " + str(err))
            continue
        try:
            with zf.open(BIN_NAME, pwd=open_pwd) as f:
                while f.read(1 << 20):
                    pass
            modes.append("accepted (no error)")
        except RuntimeError as e:
            modes.append("RuntimeError: %s" % e)
        except Exception as e:
            modes.append("%s: %s" % (type(e).__name__, e))
        # Retry only the rare late-collision verdicts; a clean
        # RuntimeError (or no encryption at all) is final.
        if (modes[-1].startswith("RuntimeError") or
                modes[-1] == "accepted (no error)"):
            break
    return harness_ok, modes


def test_zip_web():
    print("--- web/zip.js engine: Node harness + Python zipfile ---\n")
    have_node, node_ver = _node_available()
    r.check("node available on PATH", have_node, node_ver)
    if not have_node:
        print("\nnode not found: this suite drives web/zip.js from Node.")
        return r.summary()

    work = tempfile.mkdtemp(prefix="od_zipweb_")

    # 1. deflate (the default mode)
    res, out = _run_harness(work, "deflate", {"entries": ENTRIES})
    r.check("deflate: harness ok", res.get("ok") is True, ascii(res))
    zf, data, err = _open_zip(out)
    r.check("deflate: python zipfile opens the archive", zf is not None, err)
    if zf is not None:
        _check_roundtrip("deflate", zf, _sidecars(out))
        plain_c = [zi.flag_bits & 0x1 for zi in zf.filelist]
        plain_l = [_local_flag_bits(data, zi) for zi in zf.filelist]
        r.check("deflate: encryption flag clear without a password",
                all(f == 0 for f in plain_c) and all(f == 0 for f in plain_l),
                (plain_c, plain_l))

    # 2. store: same entries, no compression
    res, out = _run_harness(work, "store",
                            {"entries": ENTRIES, "mode": "store"})
    r.check("store: harness ok", res.get("ok") is True, ascii(res))
    zf, data, err = _open_zip(out)
    r.check("store: python zipfile opens the archive", zf is not None, err)
    if zf is not None:
        _check_roundtrip("store", zf, _sidecars(out))
        info = zf.getinfo(BIN_NAME)
        r.check("store: random entry stored raw (csize == usize)",
                info.compress_size == info.file_size,
                (info.compress_size, info.file_size))

    # 3. forceZip64: ZIP64 records even for a small archive
    res, out = _run_harness(work, "zip64",
                            {"entries": ENTRIES, "forceZip64": True})
    r.check("forceZip64: harness ok", res.get("ok") is True, ascii(res))
    zf, data, err = _open_zip(out)
    r.check("forceZip64: python zipfile opens the archive", zf is not None, err)
    if zf is not None:
        r.check("forceZip64: zipfile parsed 2 entries (zip64 EOCD read)",
                len(zf.filelist) == 2, len(zf.filelist))
        _check_roundtrip("forceZip64", zf, _sidecars(out))
        # Bound the signature scan to the archive tail: `find` over the whole
        # file could match a stray PK\x06\x06/PK\x06\x07 byte sequence inside
        # the random entry payload and read as a spurious ordering failure
        # (~1-in-4000 per run). The real records sit in order just before the
        # classic EOCD, so search backwards from each record's right neighbour.
        peocd = data.rfind(b"PK\x05\x06")                          # classic EOCD (last)
        ploc = data.rfind(b"PK\x06\x07", 0, peocd)                # zip64 locator
        p64 = data.rfind(b"PK\x06\x06", 0, ploc)                  # zip64 EOCD record
        r.check("forceZip64: zip64 EOCD + locator before classic EOCD",
                0 <= p64 < ploc < peocd, (p64, ploc, peocd))

    # 4. progress: monotone raw-byte events, exact final count
    res, out = _run_harness(work, "progress", {"entries": ENTRIES})
    events = res.get("progress") or []
    total = res.get("totalRaw")
    r.check("progress: harness ok, totalRaw = raw bytes fed in",
            res.get("ok") is True and total == TOTAL_RAW, ascii(res))
    r.check("progress: >= 2 events, non-decreasing",
            len(events) >= 2 and all(a <= b for a, b in zip(events,
                                                            events[1:])),
            events)
    r.check("progress: last event == totalRaw",
            bool(events) and events[-1] == total,
            "last=%r total=%r" % (events[-1:], total))

    # 5. cancel mid-entry: rejected + nothing written
    res, out = _run_harness(work, "cancel",
                            {"entries": [ENTRIES[0]],
                             "cancelAfterBytes": 500000})
    r.check("cancel: buildZip rejected, harness reports cancelled",
            res.get("cancelled") is True and res.get("ok") is False,
            ascii(res))
    r.check("cancel: no zip file on disk", not os.path.exists(out), out)

    # 6. ZipCrypto, password + deflate: encrypted flag in both headers,
    #    password mandatory, byte-exact decryption with the right key.
    res, out = _run_harness(work, "pwd-deflate",
                            {"entries": ENTRIES, "password": PWD})
    r.check("pwd-deflate: harness ok", res.get("ok") is True, ascii(res))
    zf, data, err = _open_zip(out)
    r.check("pwd-deflate: python zipfile opens the archive", zf is not None,
            err)
    if zf is not None:
        enc_c = [zi.flag_bits & 0x1 for zi in zf.filelist]
        enc_l = [_local_flag_bits(data, zi) for zi in zf.filelist]
        r.check("pwd-deflate: bit 0 set in local and central headers",
                all(f == 1 for f in enc_c) and all(f == 1 for f in enc_l),
                (enc_c, enc_l))
        try:
            zf.read(BIN_NAME)
            refused = None
        except RuntimeError as e:
            refused = str(e)
        r.check("pwd-deflate: reading without a password is refused",
                refused is not None, ascii(refused))
        _check_password_roundtrip("pwd-deflate", zf, _sidecars(out),
                                  PWD_BYTES)

    # 7. ZipCrypto, password + store: no compression, header + raw bytes
    res, out = _run_harness(work, "pwd-store",
                            {"entries": ENTRIES, "mode": "store",
                             "password": PWD})
    r.check("pwd-store: harness ok", res.get("ok") is True, ascii(res))
    zf, data, err = _open_zip(out)
    r.check("pwd-store: python zipfile opens the archive", zf is not None,
            err)
    if zf is not None:
        _check_password_roundtrip("pwd-store", zf, _sidecars(out), PWD_BYTES)
        info = zf.getinfo(BIN_NAME)
        r.check("pwd-store: stored raw + 12-byte encryption header",
                info.compress_size == info.file_size + 12,
                (info.compress_size, info.file_size))

    # 8. unicode password: the UTF-8 bytes of été+lock seed the keys
    res, out = _run_harness(work, "pwd-unicode",
                            {"entries": ENTRIES, "password": UNI_PWD})
    r.check("pwd-unicode: harness ok", res.get("ok") is True, ascii(res))
    zf, data, err = _open_zip(out)
    r.check("pwd-unicode: python zipfile opens the archive", zf is not None,
            err)
    if zf is not None:
        _check_password_roundtrip("pwd-unicode", zf, _sidecars(out),
                                  UNI_PWD.encode("utf-8"))

    # 9. forceZip64 + password: ZIP64 records on an encrypted archive
    res, out = _run_harness(work, "pwd-zip64",
                            {"entries": ENTRIES, "forceZip64": True,
                             "password": PWD})
    r.check("pwd-zip64: harness ok", res.get("ok") is True, ascii(res))
    zf, data, err = _open_zip(out)
    r.check("pwd-zip64: python zipfile opens the archive", zf is not None,
            err)
    if zf is not None:
        _check_password_roundtrip("pwd-zip64", zf, _sidecars(out),
                                  PWD_BYTES)

    # 10. wrong password against a zip built with PWD -> RuntimeError
    ok, modes = _wrong_password_mode(work, "wrongpwd",
                                     {"entries": ENTRIES, "password": PWD},
                                     WRONG_PWD.encode("utf-8"))
    r.check("wrongpwd: harness ok", ok, ascii(modes))
    r.check("wrongpwd: wrong password rejected with RuntimeError",
            bool(modes) and modes[-1].startswith("RuntimeError"),
            ascii(modes))

    # 11. negative test as a second spec run: zip built with a different
    #     password, opened with the correct one -> must not match either
    ok, modes = _wrong_password_mode(work, "pwd-mismatch",
                                     {"entries": ENTRIES,
                                      "password": WRONG_PWD},
                                     PWD_BYTES)
    r.check("pwd-mismatch: harness ok", ok, ascii(modes))
    r.check("pwd-mismatch: zip built with another password rejected",
            bool(modes) and modes[-1].startswith("RuntimeError"),
            ascii(modes))

    return r.summary()


if __name__ == "__main__":
    sys.exit(0 if test_zip_web() else 1)
