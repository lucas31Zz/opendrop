# Chunked upload with automatic retry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make multi-gigabyte sends work in every browser (the author's Zen/Firefox never drains a giant composed Blob into one request) by sending every upload as a sequence of 128 MiB multipart POSTs appended into a uniquely named staging file, verified, hashed and renamed when the last slice lands, with stalled slices retried automatically.

**Architecture:** The client (`web/app.js` `uploadFile`) becomes a sequential slice loop over `Blob.slice` with a per-send random `upload` id; the server (`multipart.py` + `server.py`) gains a staging mode: slices append at `offset` into `download_dir/<name>.<uploadId>.part` (stale tails truncated, short offsets answered with a 409 resync carrying the committed size), the last slice verifies `size == total`, hashes the whole file with one read-back pass, uniquifies the final name with today's `xb` semantics and `os.replace`s the staging file onto it. Requests without the new params keep today's exact code path (cached pages stay compatible).

**Tech Stack:** vanilla JS (XHR + FormData + Blob.slice only), Python 3 stdlib, homegrown test suites (no framework).

**Spec:** `docs/superpowers/specs/2026-10-17-chunked-upload-design.md` (approved in chat; builder-check resolutions included — note the amendment in Task 3 adds the `name` query param the pre-body 409 checks and body-less cancel need).

## Global Constraints

- No new dependencies.
- Web strings: FR + EN for every new label; code comments English.
- Additive except the internal rewrite of `uploadFile`; the UI (views, buttons, progress bar) is unchanged, plus one new progress text ("Finalisation… / Finalizing…").
- PowerShell 5.1 environment: no `&&`; check `$LASTEXITCODE` after every command.
- **NO git commit and NO push** — the author orders the commit only after the manual Zen acceptance (see Task 3). Each task ends with a ledger update, not a commit.
- Do not kill: this OpenCode instance, Zen Browser, critical system processes.

## Review Focus

1. **A same-name complete file is never clobbered** — final names are claimed with `xb` (atomic) before `os.replace`; pinned by Task 1 check "Completed name is uniquified".
2. **Slice retry is idempotent** — the server truncates any stale tail back to `offset` before appending, so a lost response or a killed write heals on the next attempt; pinned by the "Stale tail is truncated" check + the author's Zen retry observation.
3. **Rate-limit posture** — token guessing on the upload path stays bounded *before* auth (10/min new uploads, 240/min continuations, both applied in `_route_upload` before `_check_token`, replacing the generic 120/min for this path only); the existing general test hits `/api/files` and is untouched; pinned by the limiter checks + full regression.
4. **Legacy byte-compat** — requests without `upload`/`offset`/`total`/`last`/`cancel` take today's `_open_dest`/uniquify/remove-on-abort path unchanged; pinned by every pre-existing check staying green.
5. **Gecko slice drain** — 128 MiB composed slices are the proven-small class; the acceptance test is the author's original failing scenario (4 Go folder zip in Zen), not an automated suite (Playwright's Gecko stalls at all sizes and is unrepresentative).

---

### Task 1: Server staging protocol (limiters, route params, parser append mode, 409 rules, completion)

**Files:**
- Modify: `src/opendrop/server/rate_limit.py` (+`limiter_part`)
- Modify: `src/opendrop/server/multipart.py` (staging mode)
- Modify: `src/opendrop/server/server.py` (do_POST carve-out, `_route_upload` params + cancel, `_handle_upload` staging orchestration)
- Modify: `tests/conftest.py` (+`_upload_slice` helper)
- Modify: `tests/test_server.py` (+11 checks, new section "Chunked upload (staging)")

**Interfaces (consumed by Task 2):**
- `POST /api/upload?token=T&upload=<16 hex>&name=<urlencoded>&offset=<int>&total=<int>&last=0|1` — body: one multipart `file` part (any filename in the disposition; the query `name` is authoritative).
  - non-last slice → `200 {"success": true, "size": <committed bytes>}`
  - last slice → `200 {"success": true, "filename": <final uniquified name>, "size": total, "sha256": <whole-file hash>}`
  - resync → `409 {"success": false, "size": <actual staging size>}` (0 when missing)
  - `cancel=1&upload=<id>&name=<name>` (no body) → `200 {"success": true}`; unlinks the staging file if present.
- `limiter_part = RateLimiter(max_requests=240, window=60)` in `rate_limit.py`.

- [ ] **Step 1: Write the new checks in `tests/test_server.py` (red first) — plus `_upload_slice` in `tests/conftest.py`**

`_upload_slice(port, token, name, content, upload_id, offset, total, last=0)`: same multipart body construction as `_upload` (boundary `----TEST`, `filename=<name>`), URL = `_url(port, "/api/upload", token)` + `f"&upload={upload_id}&name={quote(name)}&offset={offset}&total={total}&last={last}"`; returns the `urlopen` response (tests catch `urllib.error.HTTPError` for 4xx and `json.loads(e.read())`).

New section "Chunked upload (staging)" after the stall test, one server per section via `_start_server()` (reuse the main one), cleanup by exact names afterwards. Checks (each `r.check(...)`):

1. **Chunked upload assembles 3 slices** — payload `b"A"*1000 + b"B"*1000 + b"C"*500`, id = `"a1b2c3d4e5f60708"`; slices at offsets 0/1000/2000, `total=2500`, `last=1` on the third. Expect: third response `{success, filename: "chunky.bin", size: 2500, sha256 == hashlib.sha256(payload).hexdigest()}`; disk content equals payload; **no `*.part` left in `dd`**.
2. **Non-last slice answers the committed size** — first slice answers `{"success": true, "size": 1000}`; staging file `chunky2.bin.<id>.part` exists with 1000 bytes. Then `cancel` to clean up.
3. **transfer_state tracks slices** — after a non-last slice: `active True, done False, received 1000, size 2500`; after the last: `done True`, `filename` is the final name. (Import `transfer_state, transfer_lock` from `opendrop.server.server`; read under the lock.)
4. **Stale tail is truncated** — slice1 = 1000 bytes at offset 0; then offset=400 with `b"XY"`, `last=1, total=402` → response size 402, disk = `b"A"*400 + b"XY"`.
5. **Short offset answers 409 with the actual size** — offset=5000 while staging has 1000 bytes → HTTPError 409, body `{"success": false, "size": 1000}`.
6. **Missing staging answers 409 size 0** — offset=10 for an unknown `upload`/`name` → 409, `{"success": false, "size": 0}`.
7. **`last` with a wrong total answers 409 and keeps staging** — 500-byte slice, `last=1, total=9999` → 409 `{"success": false, "size": 500}`; staging file still there; no final file.
8. **A completed name is uniquified** — pre-place a complete `chunky3.bin` (any bytes) in `dd`; then a single-slice send (offset 0, `last=1`) named `chunky3.bin` → response `filename == "chunky3 (1).bin"` (uniquify inserts the counter before the extension); both files exist; the pre-placed bytes untouched.
9. **cancel unlinks staging; repeat cancel succeeds** — after one slice, `cancel=1` → 200, staging gone; cancel again → 200 (missing file is success).
10. **Invalid upload id rejected** — `upload=../evil` → 400; `upload=xyz` (too short) → 400.
11. **Continuation slices bypass the 10/min upload limiter; new uploads keep it** — reset `limiter_upload` and `limiter_part` first; 12 consecutive `offset>0` slices (small, same send, offsets advancing) → all succeed; then 11 single-slice uploads with `offset=0` and distinct names → the 11th raises HTTPError 429. Reset both limiters again after.

Run: `python tests/test_server.py` — Expected: FAIL (400s/404s: the protocol does not exist yet).

- [ ] **Step 2: `rate_limit.py` — add `limiter_part`**

After `limiter_upload` (line 32): `limiter_part = RateLimiter(max_requests=240, window=60)`.

- [ ] **Step 3: `server.py` — dispatcher carve-out + `_route_upload` rewrite + cancel handler**

- Line 26 import: add `limiter_part`. Import `re` if absent; import `sanitize_filename` alongside the existing `is_safe_path` import if absent.
- `do_POST` (lines 443-458): parse `urlparse(self.path)` **before** the general limiter; apply `limiter_general.allow(ip)` only when `path != "/api/upload"` (the upload route enforces its own limiters, before auth, as the general one was). Everything else in `do_POST` unchanged.
- `_route_upload(self, query, ip)`:
  ```python
  upload_id = query.get("upload", [""])[0]
  cancel = query.get("cancel", [""])[0] == "1"
  offset = _int_param(query, "offset", 0)          # helper: bad int -> 0; negative -> reject 400
  if upload_id and not re.fullmatch(r"[0-9a-f]{8,32}", upload_id):
      raise MultipartParseError("Invalid upload id")
  # Limiters BEFORE _check_token (they replace the general limiter on this path).
  if upload_id and offset > 0 and not cancel:
      if not limiter_part.allow(ip):
          raise RateLimitError()
  else:
      if not limiter_upload.allow(ip):
          raise RateLimitError("Too many uploads, try again in a moment")
  self._check_token(query, ip)
  if cancel:
      self._handle_upload_cancel(upload_id, query); return
  if not upload_id:
      self._handle_upload(); return               # legacy path, byte-compatible
  name = query.get("name", [""])[0]
  safe_name = sanitize_filename(name)
  if not safe_name or not is_safe_path(self._download_dir, safe_name):
      raise FilenameUnsafeError("File name not allowed")
  total = _int_param(query, "total", 0)
  last = query.get("last", ["0"])[0] == "1"
  self._handle_upload(upload_id=upload_id, safe_name=safe_name,
                      offset=offset, total=total, last=last)
  ```
- `_handle_upload_cancel(self, upload_id, query)`: same `name` sanitize + `is_safe_path` validation (invalid → `FilenameUnsafeError`); `staging = Path(self._download_dir) / f"{safe_name}.{upload_id}.part"`; `unlink()` missing-is-fine, other `OSError` → `DiskError`; under `transfer_lock`, clear the transfer only if `transfer_state.get("upload_id") == upload_id` (`active False, done False, error None`); `_send_json({"success": True})`.
- `_handle_upload` signature gains keyword defaults (`upload_id=None, safe_name=None, offset=0, total=0, last=False`) so the legacy call site works untouched.

- [ ] **Step 4: `multipart.py` — staging mode + `open_dest_exclusive`**

- Rename `_open_dest` → `open_dest_exclusive` (public: the server claims the final name on the last slice); update its one internal caller.
- `parse_multipart_upload(..., on_progress=None, staging=None)` where `staging = (dest_path: Path, offset: int)`; return tuple grows a 4th element `committed` (bytes on disk after the request; legacy = final file size). Legacy behavior otherwise **byte-identical** (same `xb` create, same remove-on-abort).
- Staging mode inside the parser:
  - headers are still parsed/consumed (the stream must advance), but the extracted filename is ignored — `dest_path` from the server is authoritative.
  - `offset == 0`: open `dest_path` with `"w+b"` (truncate-or-create — heals stale partials).
  - `offset > 0`: open `"r+b"`; `seek(0, SEEK_END)` → `actual`; if `actual < offset` → close, return `(dest_path.name, "offset mismatch", None, actual)`; if `actual > offset` → `os.ftruncate(fd, offset)` (drops the stale tail); `seek(offset)`.
  - abort cleanup (`BaseException` handler and the close-flush failure): `_remove_quiet(dest)` **only in legacy mode** — committed slice bytes must survive a retry.
  - `DiskError` mapping unchanged.
- Helper `_sha256_file(path)` (64 KiB loop) lives in `multipart.py` or `server.py` — the last-slice whole-file hash (one read-back pass).

- [ ] **Step 5: `server.py` `_handle_upload` — staging orchestration**

- When `upload_id` is set, compute `staging_path = Path(self._download_dir) / f"{safe_name}.{upload_id}.part"` and **before** quota/body (fast resyncs, drained by the existing rejection path):
  - `offset > 0` and staging missing → `self._send_json({"success": False, "size": 0}, status=409)`; return.
  - `offset > 0` and `stat < offset` → same with `size=actual`; return.
- Quota `reserve(content_length)` / `release` in `finally`: unchanged (per-slice reservation).
- `transfer_state` at slice start: `active True, filename "", size (total if staging else content_length), received offset, done False, error None, upload_id upload_id`; `started_at` reset only when `offset == 0` (or legacy). `on_progress`: staging → `received = offset + n`, legacy unchanged.
- Parser call passes `staging=(staging_path, offset)` when staging.
- New branch before the generic `if error:` block: `error == "offset mismatch"` (race fallback) → 409 resync as above with the parser's `committed`.
- Success path, staging:
  - `not last` → transfer_state `received/size = committed, active True, done False`; respond `{"success": True, "size": committed}`.
  - `last` → if `committed != total` → 409 `{"success": False, "size": committed}` (staging kept); else whole-file SHA-256 via read-back (`DiskError` on `OSError`), claim the final name with `open_dest_exclusive`, close the claim handle, `os.replace(staging_path, final)`; transfer_state `done True, filename final_name`; the existing "File received" log (extract the ASCII-fallback print into a small `_log_received` helper to avoid a third copy); respond the legacy final shape `{success, filename, size, sha256}`.
- Legacy success path: unchanged (the 4th tuple element may replace the post-hoc `stat` — same value).

- [ ] **Step 6: Run the suite green**

Run: `python tests/test_server.py` — Expected: 28/28 (17 existing + 11 new). If a pre-existing check regresses, the legacy path was touched: fix, don't adjust the old checks.

- [ ] **Step 7: Ledger update** (`.superpowers/sdd/2026-10-16-send-zip-progress-password/progress.md`): protocol done, counts, any deviations.

---

### Task 2: Client slice loop (`web/app.js` + i18n)

**Files:**
- Modify: `web/app.js` (rewrite `uploadFile`, +`makeUploadId`/`sendSlice`/`sendCleanup`, cancel wiring, 2 i18n keys)

**Interfaces:** consumes Task 1's protocol exactly; produces no new interface (queue/progress/success/error views unchanged).

- [ ] **Step 1: i18n keys** — `"upload.finalizing": "Finalizing…"` in the EN dict (after `upload.unreachable`, line 80) and `"upload.finalizing": "Finalisation\u2026"` in the FR dict (line ~179).

- [ ] **Step 2: Rewrite `uploadFile` (line 1583) as a slice loop**

- Module-level constants: `var SLICE_SIZE = 128 * 1024 * 1024;` with the Gecko rationale comment.
- `makeUploadId()`: 8 bytes from `crypto.getRandomValues` (fallback `Math.random`) → 16 lowercase hex chars.
- State per send: `uploadId`, `committed = 0`, `attempts = 0`, `resyncs = 0`, module-level `currentSend = {id, name}` (used by cancel/cleanup).
- `sendSlice()`: `end = min(committed + SLICE_SIZE, file.size)`; `isLast = end === file.size ? 1 : 0`; `FormData` with `file.slice(committed, end)` **and explicit name** `file.name`; URL = `"/api/upload?" + authQuery() + "&upload=" + id + "&name=" + encodeURIComponent(file.name) + "&offset=" + committed + "&total=" + file.size + "&last=" + isLast`.
- Progress listener: overall math — `overall = committed + e.loaded`; pct over `file.size`; speed/ETA from `uploadStart` and `overall`; when `pct === 100 && isLast` → `progressText = t("upload.finalizing")` (covers the read-back hash wait).
- `load` handler:
  - 401/403 → `endSession(t("session.expired"))` (unchanged).
  - **409** → resync: `resyncs++`, `committed = resp.size || 0`; `resyncs >= 3` → `failTerminal(t("upload.serverError", 409))`; else `sendSlice()` immediately (not an attempt).
  - **200 && resp.success** → reset `attempts`/`resyncs`; if `isLast` → today's completion (`currentSend = null`, `queueDone++`, `pumpQueue()` or `showBatchSuccess(resp)` + `finishQueue()`); else `committed = resp.size` and `sendSlice()`.
  - **200 without success** → `failTerminal(resp.error || t("upload.serverError", xhr.status))`.
  - **retryable status** (400, 408, 429, 5xx) and `attempts < 3` → `attempts++`, `setTimeout(sendSlice, xhr.status === 429 ? 3000 : 1000)` (the stall answer is honest but recoverable: same slice, same `committed`).
  - else → `failTerminal(resp.error || t("upload.serverError", xhr.status))`.
- `error` event (network cut): retryable as above with `setTimeout` 1000; on exhaustion `failTerminal(t("upload.unreachable"))`.
- `failTerminal(msg)`: `sendCleanup()` (only when `currentSend` exists) → `currentXhr = null; currentSend = null; sendQueue = []; finishQueue(); errorDetail.textContent = msg; showSendView("error")`.
- `sendCleanup()`: `fetch("/api/upload?" + authQuery() + "&cancel=1&upload=" + currentSend.id + "&name=" + encodeURIComponent(currentSend.name), {method: "POST", keepalive: true}).catch(noop)`.
- `btnCancel` handler (line 2032): after the existing `currentXhr.abort()`, add `sendCleanup()` before `currentSend = null`.
- Remove the old single-XHR body of `uploadFile` entirely; keep `filenameEl/filesizeEl/showSendView("transfer")` init.

- [ ] **Step 3: Static + regression checks**

Run: `node --check web/app.js` (syntax), then `python tests/test_zip_web.py` (web suite still green) and `python tests/test_server.py` (server untouched by this step).

- [ ] **Step 4: Manual acceptance prepared for the author** — the checklist goes in the ledger: big folder zip in Zen (the original failing scenario), small file, cancel mid-send, batch of two files.

- [ ] **Step 5: Ledger update.**

---

### Task 3: Docs, counts, changelog, full regression

**Files:**
- Modify: `docs/superpowers/specs/2026-10-17-chunked-upload-design.md` (protocol amendment)
- Modify: `CHANGELOG.md`, `README.md`, `SECURITY.md`, `CONTRIBUTING.md`, `.superpowers/sdd/2026-10-16-send-zip-progress-password/commit-msg.txt`

- [ ] **Step 1: Design doc amendment** — protocol table gains `name` (authoritative final name, URL-encoded; enables the pre-body 409 checks and the body-less cancel); cancel row references `name`; note that the multipart disposition filename is ignored in staging mode.

- [ ] **Step 2: Full regression** — run all 10 suites (`python tests/test_security.py`, `test_routes.py`, `test_paths.py`, `test_quota.py`, `test_sessions.py`, `test_tls.py`, `test_server.py`, `test_beta.py`, `test_devices.py`, `test_zip_web.py`). Expected: all green; count the new total (400 + 11 = 411 if Task 1 landed as planned) by summing each suite's final count line.

- [ ] **Step 3: Counts + prose** — update the check counts in README/SECURITY/CONTRIBUTING; CHANGELOG `Fixed` gains the chunked-upload bullet (Gecko multi-GB sends: every upload now travels in 128 MiB slices with automatic per-slice retry, staged and renamed on completion — never clobbers a same-name file); `commit-msg.txt` counts + a short paragraph + review-focus line.

- [ ] **Step 4: Ledger update + report to the author** — summary in French, then the manual Zen acceptance request. The commit stays gated on the author's explicit order after that test passes.
