# Send-tab zip v2 (progress, ZIP64, password) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the opaque, memory-hungry, 4 GB-capped folder zipping of the web Send tab with a streaming ZIP64 engine that shows live progress, supports an optional ZipCrypto password and a Standard/Rapide compression choice, checks the batch against the remaining quota before doing any work, and drop the server's obsolete 10 GB per-request cap.

**Architecture:** `web/zip.js` is rewritten as a streaming engine (chunked reads, incremental CRC, per-entry Blob parts, ZIP64 when sizes demand it, ZipCrypto layered on the stored bytes). `web/app.js` grows a pre-flight step: walk metadata -> quota pre-check -> one options panel per batch (password + compression + explicit Start) -> zipped queue -> the existing upload pipeline untouched. The server loses its `MAX_UPLOAD_SIZE` constant; the quota tracker is the only ceiling.

**Tech Stack:** vanilla JS (no dependencies), Python 3 stdlib test suites (homegrown, no framework), Node as the zip-engine test driver, Python `zipfile` as the independent verifier.

**Spec:** `docs/superpowers/specs/2026-10-15-send-zip-password-progress-design.md` (approved 2026-10-16; includes the builder-check rulings: one shared panel per batch, everything waits for Start, batch-total quota check, fail-open on quota fetch, Standard degrades to store without CompressionStream, and the user's two-button drop zone).

## Global Constraints

- No new dependencies (ZIP64, ZipCrypto, progress all hand-rolled in `web/zip.js`).
- Web strings: FR + EN for every new label/hint/error; code comments English.
- Liquid Glass preserved; new UI reuses existing classes (`.settings-check`, `.move-select`, `.paste-input`, `.btn-unlock`) plus minimal new CSS.
- Additive changes except mandated deletions: `MAX_UPLOAD_SIZE` (server.py:43 + check at :799-800), the zip.js `tooLarge` machinery, the static "Preparing..." state, the `.link-folder` single-link in the drop zone.
- PowerShell 5.1 environment: no `&&`; check `$LASTEXITCODE` after every command.
- **NO git commit and NO push all night** — the user orders commit tomorrow. Each task ends with a ledger update, not a commit.
- Do not kill: this OpenCode instance, Zen Browser, critical system processes. Killing other processes is allowed when needed.
- Version lands at 0.15.0; CHANGELOG date `2026-10-16`.

## Review Focus

1. **ZIP64 central-directory offsets when the archive crosses 4 GB** — expected: extractable by Python `zipfile` and Windows Explorer. Pinned by the `forceZip64` checks in Task 1; the real-size confirmation is the user's manual run (checklist).
2. **ZipCrypto check-byte and password encoding vs third-party tools** — expected: Python `zipfile` decrypts with the UTF-8 password bytes; wrong password fails. Pinned by Task 2's round-trip checks + user's Explorer test.
3. **Progress counts raw input bytes in both modes** — expected: last `onProgress` call equals total raw bytes exactly, monotonic in between. Pinned by Task 1's progress checks.
4. **Cancel mid-zip rejects with `cancelled` and never starts an upload** — expected: aborted signal -> buildZip rejects promptly; app bumps `prepareEpoch` and aborts. Pinned by Task 1's cancel check + Task 4's epoch/signal wiring (user tests the button).
5. **Quota pre-check edges** — unlimited (`limit_bytes = 0`) always passes; `totalRaw == remaining` passes; `totalRaw > remaining` refuses with the three numbers in the message. Client-side math is reviewed in Task 4 and pinned by the user's manual quota test (checklist).

---

### Task 1: Streaming ZIP64 engine + engine test suite

**Files:**
- Modify: `web/zip.js` (full rewrite of `buildZip` internals; keep the IIFE + `OpenDropZip` global)
- Create: `tests/zip_harness.mjs`
- Create: `tests/test_zip_web.py`
- Modify: `.github/workflows/tests.yml` (add `test_zip_web` to the suite loop)

**Interfaces:**
- Produces (Task 2 and Task 4 consume):
  `OpenDropZip.buildZip(entries, opts) -> Promise<Blob>`
  - `entries`: `[{ name: string, file: File|Blob, date?: Date }]` (unchanged shape)
  - `opts`: `{ mode?: "deflate"|"store" (default "deflate"), password?: string (T2), signal?: AbortSignal, onProgress?: (doneRaw: number, totalRaw: number) => void, forceZip64?: boolean }`
  - rejects with `err.cancelled === true` when `signal` aborts
  - `OpenDropZip.crc32(bytes)` stays exported unchanged.
- Harness contract: `node tests/zip_harness.mjs <specJsonPath> <outZipPath>`; spec JSON `{ entries: [{name, size, kind: "random"|"text", text?}], mode?, password?, forceZip64?, cancelAfterBytes? }`; prints one JSON line `{ ok, cancelled?, progress: [doneRaw...], totalRaw }`.

- [ ] **Step 1: Write `tests/zip_harness.mjs`**

Node ESM script; imports `../web/zip.js` (side effect sets `globalThis.OpenDropZip`); entries built from Blobs (random via `crypto.randomFillSync` in 1 MB buffers); registers `onProgress` pushing `doneRaw` into an array; `cancelAfterBytes` aborts an `AbortController` from within `onProgress`; writes result Blob to `outZipPath` unless cancelled; prints the JSON line.

- [ ] **Step 2: Write `tests/test_zip_web.py` (homegrown suite style of `tests/test_devices.py`)**

Checks (each `r.check(name, cond, detail)`):
1. node available (`node --version`) — suite aborts with a clear message if missing.
2. deflate zip (2 entries: 1 MB random `.bin`, 1 KB UTF-8 text named `été-照片.txt`): Python `zipfile` opens, both names present, `testzip()` returns None, bytes equal the originals (regenerate the same random payload in Python? No — the harness writes the payload bytes to `<out>.expect/<entry>` sidecar files; the suite compares).
3. store zip (same entries, `mode: "store"`): same assertions; compressed size == raw size for the random entry.
4. `forceZip64: true` zip: Python `zipfile` opens it, `_RealGetContents` path exercised (assert `len(zf.filelist) == 2` and content matches — Python reads the zip64 EOCD).
5. progress: events non-decreasing, `len(events) >= 2` for a 1 MB entry, last event == totalRaw.
6. cancel: `cancelAfterBytes: 500000` on a 1 MB entry -> harness reports `cancelled: true`, no zip file on disk.

- [ ] **Step 3: Run the suite to verify it fails**

Run: `python -m tests.test_zip_web`
Expected: FAIL (harness exists but `web/zip.js` still exports the old `buildZip(entries)` without `opts` — e.g. cancel/zip64 checks fail; old code throws `tooLarge` for forceZip64 sizes it never sees — the deflate/store checks may pass old code, that is fine and expected).

- [ ] **Step 4: Rewrite `web/zip.js` `buildZip` internals**

Keep: CRC table/`crc32`, `dosStamp`, the IIFE, the export object.
Implement:
- `totalRaw` = sum of `entry.file.size ?? 0`; `onProgress` after every consumed chunk (1 MB read chunks).
- Per entry: `file.stream()` reader loop -> a `TransformStream` that (a) updates the running CRC32 over plaintext, (b) counts into `onProgress`, (c) forwards; pipe through `CompressionStream("deflate-raw")` in `deflate` mode (missing engine -> store silently), or read-through in `store` mode.
- Collected output parts per entry accumulate into an 8 MB staging buffer (flush full buffers into the parts list) so RAM stays flat; the local header is written AFTER the entry's data is known (parts array order preserved: header inserted at the entry's start index).
- ZIP64 (APPNOTE 4.5) whenever `rawSize >= 0xFFFFFFFF || compressed >= 0xFFFFFFFF || offset >= 0xFFFFFFFF || entries >= 0xFFFF || opts.forceZip64` — `>=`, NOT `>`: the marker value itself is not representable classically (review-corrected 2026-10-16): local header sizes set to `0xFFFFFFFF` with extra field id `0x0001` (uncomp then comp, 8 bytes each); central header sizes/offset `0xFFFFFFFF` with extra `0x0001` (uncomp, comp, offset); `version needed = 45`; after the central directory, when any of sizes/offset/count overflowed: zip64 EOCD record `0x06064b50` + zip64 locator `0x07064b50` before the classic EOCD (classic fields saturated `0xFFFF`/`0xFFFFFFFF`).
- Abort: `opts.signal.aborted` checked per chunk; rejection error carries `cancelled = true`.
- Signatures/flags: UTF-8 names flag `0x0800` kept; method 8/0 per mode.

- [ ] **Step 5: Run the suite to verify it passes**

Run: `python -m tests.test_zip_web`
Expected: 6/6 (or more) passed, 0 failed.

- [ ] **Step 6: Syntax check + CI wiring**

Run: `node --check web/zip.js` (exit 0) and `node --check tests/zip_harness.mjs` (exit 0); edit `.github/workflows/tests.yml` loop to `... test_devices test_zip_web`.

- [ ] **Step 7: Ledger update (NO commit — user gate)**

Append task status + counts to `.superpowers/sdd/2026-10-16-send-zip-v15/progress.md`.

---

### Task 2: ZipCrypto password support

**Files:**
- Modify: `web/zip.js`
- Modify: `tests/zip_harness.mjs` (password + wrong-password cases)
- Modify: `tests/test_zip_web.py` (round-trip checks)

**Interfaces:**
- Consumes: Task 1's `buildZip(entries, opts)`.
- Produces: same signature; `opts.password` now real — general-purpose bit 0 set, 12-byte encryption header (11 random bytes from `crypto.getRandomValues` + 1 check byte = high byte of the plaintext CRC32), keys `k0/k1/k2` seeded `0x12345678/0x23456789/0x34567890`, per plaintext byte: `k0 = CRC_TABLE[(k0 ^ b) & 0xFF] ^ (k0 >>> 8); k1 = Math.imul(k1 + (k0 & 0xFF), 134775813) + 1 >>> 0; k2 = CRC_TABLE[(k2 ^ (k1 >>> 24)) & 0xFF] ^ (k2 >>> 8)`; output byte = `plain ^ (((k2 | 2) * ((k2 | 2) ^ 1)) >>> 8)` with keys updated per encrypted byte; encryption wraps the STORED bytes (post-deflate) of header + data; CRC fields stay the plaintext CRC.

- [ ] **Step 1: Extend the harness** — `password` passes through; add `wrongPassword` mode that emits a second spec run with a different password for the negative test.
- [ ] **Step 2: Extend `test_zip_web.py`** — checks: (a) password+deflate zip opens with `zf.open(name, pwd=b"secret123")`, bytes match; (b) password+store same; (c) wrong password raises `RuntimeError`; (d) unicode password `été🔒` opens with `pwd="été🔒".encode("utf-8")`; (e) encrypted entry flags bit 0 set (`zf.filelist[i].flag_bits & 0x1`).
- [ ] **Step 3: Run to verify fail** — `python -m tests.test_zip_web` -> the 5 new checks FAIL (old engine ignores `password`).
- [ ] **Step 4: Implement ZipCrypto in `web/zip.js`** per the interface constants above (encrypt pass over the stored parts as they are flushed; seed with the UTF-8 password bytes).
- [ ] **Step 5: Run to verify pass** — `python -m tests.test_zip_web` all green.
- [ ] **Step 6: `node --check web/zip.js`** exit 0.
- [ ] **Step 7: Ledger update (NO commit).**

---

### Task 3: Drop zone with two explicit buttons

**Files:**
- Modify: `web/index.html:54-68` (drop-zone block)
- Modify: `web/app.js` (element refs + wiring; strings T.en/T.fr)
- Modify: `web/style.css` (`.drop-btn` row; remove the now-unused `.link-folder` rule if nothing else references it)

**Interfaces:**
- Consumes: existing `#file-input` / `#folder-input` (unchanged ids).
- Produces: `#btn-choose-files` + `#btn-choose-folder` (kept id) as sibling glass buttons; strings `drop.chooseFiles` ("Choose files" / "Choisir des fichiers"), `drop.chooseFolder` ("Choose a folder" / "Choisir un dossier"); `drop.hint` ("or drop it here" / "ou déposez ici") stays centred under the button row; `drop.folderHint` stays.

- [ ] **Step 1: HTML** — replace the "Choose a file" paragraph + `.link-folder` button with: icon, `<p data-i18n="drop.choose">` removed, a `.drop-btn-row` containing the two buttons, then the two hints. Inputs stay.
- [ ] **Step 2: Strings** — add `drop.chooseFiles` FR/EN; adjust `drop.chooseFolder` if wording changes; keep every existing key green.
- [ ] **Step 3: app.js wiring** — `btnChooseFiles` ref + `fileInput.click()`; keep `btnChooseFolder` wiring (already `folderInput.click()` with `stopPropagation`).
- [ ] **Step 4: CSS** — `.drop-btn-row { display:flex; gap:10px; justify-content:center }`; `.drop-btn` reuses the existing button glass look (model on `.btn-unlock` sizing, smaller); delete `.link-folder` rules only if grep shows no other use.
- [ ] **Step 5: Verify** — `node --check web/app.js` exit 0; grep confirms no `link-folder` reference remains; ids/keys consistency grep (`btn-choose-files`, `drop.chooseFiles` in EN+FR).
- [ ] **Step 6: Ledger update (NO commit).**

---

### Task 4: Send flow — pre-check, options panel, zip progress, cancel

**Files:**
- Modify: `web/index.html:71-80` (transfer card gains the options panel)
- Modify: `web/app.js` (prepare path ~1630-1830, new refs, strings)
- Modify: `web/style.css` (panel layout, minimal)

**Interfaces:**
- Consumes: `OpenDropZip.buildZip(entries, {mode, password, signal, onProgress})` (Task 1/2), `#btn-choose-files/#btn-choose-folder` (Task 3), existing queue (`enqueueFiles`, `pumpQueue`, `uploadFile`), `fetchWithTimeout` + `authQuery()`.
- Produces: batch-descriptor prepare functions `prepareDropped(dt) -> Promise<batch>` and `preparePickedFolders(list) -> Promise<batch>` where `batch = { items: [{kind:"file", file} | {kind:"folder", name, entries: [{name, file}], rawSize}], totalRaw }`; `quotaAllows(totalRaw, usage, limit) -> boolean` (limit 0 = unlimited); new element ids `#send-options`, `#send-options-list`, `#chk-zip-password`, `#zip-password-input`, `#zip-mode`, `#btn-start`; strings `send.optionsTitle`, `send.zipPassword`, `send.zipPasswordPlaceholder`, `send.compression`, `send.modeStandard`, `send.modeFast`, `send.start`, `send.zipping` ("Compression… {0} ({1} / {2})"), `send.tooBig`, `send.zipFailed`.

- [ ] **Step 1: HTML panel** — inside `#transfer-info`, a `#send-options` block (hidden by default): title, list container, `.settings-check` checkbox, hidden `.paste-input` password field, `.move-select` with the two modes, `.btn-unlock` Start button. Existing progress elements stay for both zipping and upload phases.
- [ ] **Step 2: prepare rework** — `prepareDropped`/`preparePickedFolders` stop zipping: they build the batch descriptor (walking is unchanged; `rawSize` = sum of `file.size` in the folder). `prepareThenSend`: batch with no folder -> `enqueueFiles(files)` exactly as today.
- [ ] **Step 3: pre-check** — `fetchWithTimeout("/api/quota?" + authQuery())` -> `quotaAllows(totalRaw, usage_bytes, limit_bytes)`; fail-open on any error; refusal -> `#error-detail` gets `send.tooBig` with `formatSize(totalRaw)`, `formatSize(remaining)`, `formatSize(shortfall)` and `showSendView("error")`.
- [ ] **Step 4: panel + zip phase** — folder batches render the panel; Start builds each folder sequentially via `buildZip` with a shared `AbortController` (created per batch), aggregated `onProgress` over the folders' raw totals driving `#progress-bar` width + `#progress-text` = `t("send.zipping", pct, formatSize(done), formatSize(total))`; zipped `File`s replace their folder items in original order -> `enqueueFiles(queue)`. Checkbox toggles the password field; empty password with checkbox on -> treat as no password (or disable Start — pick: disable Start until non-empty).
- [ ] **Step 5: cancel + errors** — `btnCancel` also `abort()`s the controller; a `cancelled` rejection returns to the drop view silently; any other zip rejection -> `send.zipFailed` on the error card; `prepareEpoch` guards every state transition (existing pattern).
- [ ] **Step 6: strings + CSS** — all keys FR/EN; panel styled with the reused classes (no new glass surfaces beyond a thin layout).
- [ ] **Step 7: Verify** — `node --check web/app.js` exit 0; grep id/key consistency; full python suite run `python -m tests.test_zip_web` still green (untouched engine).
- [ ] **Step 8: Ledger update (NO commit).**

---

### Task 5: Server — remove the 10 GB cap

**Files:**
- Modify: `src/opendrop/server/server.py:43` (delete constant), `:799-800` (delete the check)
- Modify: `src/opendrop/server/*` only as needed to drop an unused `FileTooLargeError` import (grep first; remove the class from its module only if zero references remain anywhere)
- Modify: `tests/test_security.py:195-228` (replace the size-cap block)
- Modify: `README.md:52`

**Interfaces:**
- Consumes: existing quota reserve right after the deleted check (unchanged).
- Produces: uploads refused ONLY by quota (507) and rate limits; `test_security` keeps a "no fixed cap" check + a plain upload regression (suite total will change — record the new count for Task 6).

- [ ] **Step 1: server edits** — delete `MAX_UPLOAD_SIZE = 10 * 1024 * 1024 * 1024  # 10 GB` and the `if content_length > MAX_UPLOAD_SIZE: raise FileTooLargeError(...)` block; grep `MAX_UPLOAD_SIZE|FileTooLargeError` repo-wide and clean the leftovers (imports only — do not delete the exception class if anything else references it).
- [ ] **Step 2: tests** — replace `tests/test_security.py:195-228` with: (a) `not hasattr(server_module, "MAX_UPLOAD_SIZE")` -> "10 GB per-request cap removed"; (b) a plain small upload still succeeds (regression of the untouched path). Record the suite's new count.
- [ ] **Step 3: README:52** — `**Safety limits**: 10 GB per file, per-IP rate limits, sanitized file names` -> `**Safety limits**: storage quota (the real ceiling), per-IP rate limits, sanitized file names`.
- [ ] **Step 4: Verify** — `python -m tests.test_security`, `python -m tests.test_quota`, `python -m tests.test_beta` all green with counts.
- [ ] **Step 5: Ledger update (NO commit).**

---

### Task 6: Release 0.15.0 — version, CHANGELOG, counts, full regression

**Files:**
- Modify: `pyproject.toml:3`, `src/opendrop/main.py:84`, `packaging/windows/OpenDrop.iss:14+17`, `desktop/OpenDrop/OpenDrop.csproj:15-17` (all to `0.15.0`)
- Modify: `CHANGELOG.md` (new `## [0.15.0] - 2026-10-16` entry)
- Modify: `README.md`, `SECURITY.md`, `CONTRIBUTING.md` (suite lists + counts to measured truth)

**Interfaces:**
- Consumes: measured counts from Tasks 1/2/4/5 suites.
- Produces: the releasable tree (still uncommitted until the user orders).

- [ ] **Step 1: version bump** at the four locations (same pattern as 0.14.0).
- [ ] **Step 2: CHANGELOG entry** in the file's English voice: streaming ZIP64 engine (no more 4 GB ceiling), live zip progress + Cancel, Standard/Rapide choice, optional ZipCrypto password on folder zips, batch quota pre-check with a clear refusal, drop zone with two explicit buttons, server 10 GB per-request cap removed (quota governs), the my-IP web settings line riding along, suite count updates.
- [ ] **Step 3: doc counts** — run every suite bare; update README/SECURITY/CONTRIBUTING tables and totals to the measured numbers (including the new `test_zip_web` row).
- [ ] **Step 4: full regression** — all suites bare, all green; `node --check` on `web/app.js`, `web/zip.js`, `tests/zip_harness.mjs`.
- [ ] **Step 5: env sync** — `python -m pip install -e . --no-deps` -> `importlib.metadata.version("opendrop-lan") == "0.15.0"`; `dotnet build desktop/OpenDrop/OpenDrop.csproj` -> 0 errors (1 pre-existing AVL​N3001 warning accepted).
- [ ] **Step 6: Ledger final + morning summary** (manual-test checklist for the user; NO commit).
