# Send-tab zip upgrade - progress, ZIP64, password (v0.15.0) - Design Spec

## Intent

The Send tab zips a dropped or picked folder in the browser before it
travels. Today that step is opaque and fragile: a silent "Preparing..."
bar, whole files read into memory, a hard 4 GB ceiling (no ZIP64 - the
archive throws `tooLarge` and the generic catch shows "Could not read
the folder."), and a server-side 10 GB per-request cap on top. A 14 GB
folder means minutes of invisible deflation ending in a bare error.

The user wants **information and control**: see the zip advance (and be
able to cancel), decide per folder whether it gets a password and
whether it is compressed at all, learn immediately when the size cannot
fit the share instead of after twenty minutes, and lose the 10 GB cap
(the receive quota is the real limit - "ca passe ou pas c'est notre
choix").

## Goals

1. **Zip progress on the transfer card**: the "Preparing..." line
   becomes a live bar - `Compression... 42 % (6.0/14.0 GB)` - updated
   per chunk; Cancel works throughout the zip.
2. **ZIP64**: no more 4 GB ceilings (entry size, archive size, entry
   count). A 14 GB folder zips and uploads.
3. **Streaming memory model**: files read in ~1-4 MB chunks
   (`file.stream()`), CRC computed incrementally, deflated output
   collected in Blob parts (browser disk-backed storage). One huge file
   no longer means one huge ArrayBuffer.
4. **Password on folder zips**: opt-in checkbox before zipping; checking
   it reveals a password field. Classic ZipCrypto, hand-rolled, no
   dependency - opens directly in Windows Explorer.
5. **Compression choice**: per folder batch, `Standard` (streamed
   deflate-raw) or `Rapide` (store, no compression - near-instant,
   same weight). Default Standard.
6. **Early size check**: right after the batch is walked (metadata
   only, no reads) and BEFORE any zipping: batch total (loose files +
   raw folder sizes) vs remaining quota (`GET /api/quota` ->
   `limit_bytes - usage_bytes`; `limit_bytes = 0` means unlimited and
   always passes). Too big -> one immediate error card naming the
   batch's weight, the space left and the shortfall; the whole batch
   is refused (nothing zipped, nothing sent). A failed quota fetch
   fails open (log, proceed) - the server enforces exact quota at
   reservation anyway.
7. **Server: remove `MAX_UPLOAD_SIZE` (10 GB, server.py:43)** - the
   quota tracker governs. Update every doc/test that mentions it.
8. **Docs + version**: README safety-limits line, CHANGELOG entry,
   version bump to 0.15.0 (new feature set).
9. **FR + EN strings** for every new label, hint and error.

## Non-goals

- No progress UI in the Download-tab multi-select zip (it rides the new
  engine and gains ZIP64 for free; only the Send card gets a bar).
- No AES/WinZip encryption (needs a dependency or heavy WebCrypto
  plumbing; ZipCrypto is the compatible, dependency-free call).
- No upload resume/retry, no streaming upload (a browser must materialize
  the whole Blob before the first byte leaves - Blob parts are
  disk-backed, RAM stays low).
- No change to the desktop app's drag-to-Shared-files path.
- No server-side streaming quota preview: the client pre-check is UX
  only; the server still enforces exact quota at reservation (507).

## Constraints

- No new dependencies anywhere (ZIP64 + ZipCrypto hand-rolled in
  `web/zip.js`).
- Liquid Glass look preserved; new controls reuse existing glass classes.
- Web strings FR+EN; code comments English.
- PowerShell 5.1 environment (no `&&`, `git commit -F`).
- Additive changes except the mandated deletions (`MAX_UPLOAD_SIZE`, the
  `tooLarge` machinery, the "Preparing..." static state).

## Decisions (builder follows, user may veto)

- **One options panel for the whole batch** (builder-check Q1-Q3).
  When a batch contains at least one folder, the transfer card shows -
  before any zip work - the batch listing (loose files by name, folders
  with name + raw size), the password checkbox (unchecked by default),
  the password field (revealed on check) and the compression select
  (Standard/Rapide); the password and the mode apply to every folder of
  the batch. Zipping starts on the explicit **Commencer** button and
  EVERYTHING waits for it: nothing is zipped, uploaded or sent before
  the panel is confirmed - mixed batches included; once the zips are
  built the existing queue uploads loose files and folder zips in their
  original drop order. Batches of plain files keep today's immediate
  upload with no panel. Rationale: the checkbox must exist *before* the
  zip ("avant de le zip, une case a cocher... ou a passer"), a
  deterministic pre-zip moment needs an explicit start, and one shared
  panel keeps the state machine a single pre-flight screen.
- **Drop zone gets two explicit buttons** (user decision): `Choisir
  des fichiers` and `Choisir un dossier` side by side; the whole zone
  stays a single drop target for files AND folders; the old "Choose a
  file" headline with its small hidden folder link is removed (it read
  as a cheat). New FR/EN strings for both buttons.
- **ZipCrypto details**: general-purpose flag bit 0 set; 12-byte
  encryption header (11 random bytes + high byte of the plaintext CRC);
  keys seeded from the UTF-8 password, updated per byte with the CRC32
  polynomial; method stays 0 (store) or 8 (deflate). Standard on
  passwords: opens in Windows Explorer, 7-Zip, Android/iOS zip apps;
  honest note in the UI hint that it protects against the curious, not
  against attackers.
- **Deflate policy change**: the old per-entry "use deflate only if it
  shrank" auto-fallback disappears - a streaming pass cannot know the
  output size before committing. Standard always deflates; Rapide always
  stores; an engine without `CompressionStream` degrades Standard to
  store silently (valid zip - the old engine-missing fallback stays,
  only the shrink-check goes). The user chooses per batch.
- **Progress unit**: raw input bytes consumed / total raw bytes of the
  batch's folders; same denominator in both modes.
- **Cancel**: `AbortSignal` threaded into `buildZip`; `btnCancel`
  aborts the signal and bumps the existing `prepareEpoch`.
- **Early-check message**: shows the batch's weight, the space left and
  the shortfall (`send.tooBig` FR/EN), rendered on the error card.
- **Versioning**: 0.15.0. The `v0.14.0` tag stays where it points (the
  my-IP fix `b7c89a1` rides into 0.15.0's changelog); no re-tagging.

## Verification (input for the implementation plan)

- **Password round-trip**: a Node harness runs `web/zip.js` (Blob +
  CompressionStream exist in modern Node) to build password zips in both
  modes; Python's `zipfile` (reads and decrypts ZipCrypto) extracts them
  and byte-compares. Automated, no browser needed.
- **ZIP64**: code reviewed against the APPNOTE; real-world check is the
  user's own >4 GB folder hand-test (14 GB case).
- **Regression**: all 9 Python suites green (adjust any test touching
  `MAX_UPLOAD_SIZE`), `node --check` on `web/app.js` + `web/zip.js`,
  dotnet build untouched (no desktop change).
- **Docs truth**: README/CHANGELOG lines match measured behavior.
