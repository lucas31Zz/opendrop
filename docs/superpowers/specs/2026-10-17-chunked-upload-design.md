# Design: chunked upload with automatic retry (reliable multi-GB sends)

Date: 2026-10-17
Status: approved in chat by the author ("vas y !"); builder-check run, all
questions resolved (see "Builder-check resolutions" - the author can veto
any call there; nothing was committed).

## Why

Manual testing of v0.15.0 found that a 4.75 GB folder zip zips fine in the
browser, uploads to 100 % shown, and then dies: the server never receives
the end of the request body. Evidence chain (all on the author's machine):

- Python client, 4.7 GB multipart POST over TLS: complete in 7.9 s.
- Edge (Chromium), 4.93 GB: complete in 17.3 s, 100.000 %.
- Firefox (playwright build): stalls on every body size tried (4.93 GB,
  2 GiB, 1 GiB, 50 MB; XHR and fetch alike), always with the final
  ~7.6 KB never reaching the wire while the client reports 100 %.
- The author's real Zen browser: a **5 GB plain file uploads fine**,
  small zips upload fine, the **big composed zip fails every time**.

Conclusion: size and transport are innocent; the failure is how Gecko
drains a giant composed Blob (the zip engine's `new Blob(parts)`) into a
single request. The server-side 120 s idle window added in this release is
correct and stays (it turns a silent stall into an honest error); the fix
is to never put a multi-gigabyte composed Blob in one request.

## The fix in one sentence

Every upload - zip or loose file - is sent as a sequence of small multipart
POSTs (128 MiB slices of the Blob) appended in order into a uniquely named
staging file (`<name>.<uploadId>.part`) that is verified, hashed and
renamed to its final name when the last slice lands; slices that stall or
drop are retried automatically (3 attempts each).

## Goals

- Big sends work in every browser, including Zen/Firefox, using only
  universally available primitives (XMLHttpRequest, FormData, Blob.slice).
- A stalled or dropped slice retries itself; progress keeps moving; an
  error appears only when retries are exhausted.
- Same UI as today: one progress bar (bytes acknowledged by the server),
  same cancel button, same success card with filename/size/SHA-256.
- Single code path: a small upload is a one-slice upload.
- Failures leave no junk: terminal errors and cancel unlink the staging
  file; a same-name complete file is never touched.

## Non-goals (out of scope)

- Resuming across a page reload or new session (a fresh send starts at
  zero with a new upload id).
- Parallel slices; one in flight, strictly sequential.
- Keep-alive reuse (the server closes after each request today; each slice
  is a fresh connection - a few dozen TLS handshakes).
- Incremental cross-request hashing (stateless server): the final SHA-256
  is one read-back pass on the last slice.
- Hiding in-progress files from the file list (today's growing partial is
  visible too; `.part` visibility is parity, see resolutions).
- The pre-existing `limiter_upload` 10/min ceiling on distinct new uploads
  (a batch of more than 10 fresh uploads within a minute could already 429
  before this change; unchanged here, flagged for the deferred list).

## Anti-goals

- No new dependencies (client or server).
- No change to quota semantics (507), auth (401/403), token, origin, or
  path-safety checks; rate-limit posture must not weaken.
- No behavior change for legacy clients (requests without the new params
  take today's exact code path); the existing checks must stay green.

## Constraints

- PowerShell 5.1; no `&&`; check `$LASTEXITCODE`.
- UI strings FR+EN; code comments English.
- Nothing committed or pushed until the author orders it.
- Test counts in README/SECURITY/CONTRIBUTING/CHANGELOG updated when
  suites gain checks.

## Protocol

Route stays `POST /api/upload?token=...` (origin and token checks
unchanged). New query parameters:

| param    | meaning                                                        |
|----------|----------------------------------------------------------------|
| `upload` | client-generated opaque id (`[0-9a-f]{8,32}`), unique per send; selects the staging file |
| `name`   | the file's final name (URL-encoded, sanitized server-side); authoritative in staging mode |
| `offset` | byte offset within the staging file this body appends to       |
| `total`  | full final size of the file (client-known)                     |
| `last`   | `1` on the final slice (verify, hash, rename, `done`)          |
| `cancel` | `1` = unlink this send's staging file, no body                 |

- A request **without `upload`** is a legacy whole-file request and takes
  today's code path byte-for-byte (back-compat for cached pages and the
  existing suites).
- Staging path: `download_dir / (sanitize(name) + "." + id + ".part")`
  where `id` must match `^[0-9a-f]{8,32}$` (plus `is_safe_path` as
  defense in depth).
- **Amendment (builder-check follow-up):** in staging mode the query's
  `name` is authoritative, not the multipart part's `Content-Disposition`
  filename. The server must know the staging path *before* reading any of
  the body (to answer the `offset > 0` resync and the body-less
  `cancel`), and the disposition filename only becomes available once the
  headers are parsed. The client always sends the same name in both
  places; the parser ignores the disposition filename when `staging` is
  set. Legacy requests keep trusting the disposition, as today.

### Staging rules (the idempotency core)

`offset == 0` (first slice or a retry of it): create-or-**truncate** the
staging file, then append. Deterministic id => a lost slice-0 response
retries into the SAME staging file: no orphan, no clobber, two tabs can
never interleave (different ids).

`offset > 0`:

1. staging missing -> `409 {success:false, size:0}` (client restarts at
   zero; slice 0 recreates it).
2. `size > offset`  -> truncate to `offset`, then append (stale tail from
   a killed write).
3. `size < offset`  -> `409 {success:false, size:actual}` (client adopts
   `actual` and continues; slices are dynamic from the committed point).
4. `size == offset` -> append.

`last == 1`, after the write:

1. `stat(staging) == total`, else `409 {size: actual}` (resync).
2. SHA-256 of the whole staging file (read-back pass).
3. Uniquify the final name exactly like today (`xb` semantics): a
   complete same-name file is never overwritten; then
   `os.replace(staging, final)` (same directory).
4. Answer today's final shape `{success, filename, size, sha256}`.

Responses:

- non-last slice: `{success:true, size}` - `size` is the staging file's
  committed byte count; the client's new `committed` value comes only
  from here (a short `size` self-heals without a special case).
- last slice: today's final response, `filename` = post-uniquify name.
- `cancel=1&upload=<id>&name=<name>`: `{success:true}` (missing file is
  success); unlinks the guarded staging file only.

`transfer_state`: every slice carries `total`; at slice start
`active=True, error=None, received=offset`; `on_progress` adds `offset`
so `received` counts committed-plus-current bytes across slices;
`size=total`; only `last` sets `done=True` + final filename. A mid-slice
stall still reports its honest error for that moment (observers see a
brief error during a retry, then the next slice start clears it).

Quota: `reserve(content_length)` / `release` in `finally` per request,
exactly as today; staging files live in the receive folder so their bytes
are counted like today's in-place partials.

### Limiters (posture preserved)

- `/api/upload` gets a carve-out from the generic 120/min limiter
  because it enforces its own, stricter-for-purpose limits (applied in
  `_route_upload`, **before** `_check_token`, so token guessing on this
  path stays bounded even though `limiter_general` no longer covers it):
  - no `upload` param or `offset == 0` -> `limiter_upload` (10/min,
    unchanged: this is the expensive "new upload" and the existing pins
    still hold).
  - `offset > 0` **or** `cancel=1` -> new `limiter_part =
    RateLimiter(240, 60s)` (bounds token guessing at 4/s on this path
    while allowing 128 MiB slices at any realistic LAN speed - 110
    slices for 14 GB). A cancel is a cheap cleanup, not a new upload:
    charging it to the 10/min budget would starve a user who cancels
    and retries, so it shares the continuation budget instead.
- `limiter_general` untouched for every other route (its 120/min test
  keeps passing).

### The 120 s idle window

`UPLOAD_IDLE_TIMEOUT` (this release's earlier fix) applies unchanged to
each slice body read; an in-slice stall answers `400 Transfer interrupted
(the connection stalled)`, which the client treats as retryable.

## Client (web/app.js)

`uploadFile(file)` becomes a slice loop around the existing XHR plumbing:

- `uploadId = crypto.getRandomValues(new Uint8Array(8))` hex (fallback:
  `Math.random` hex if `crypto` is absent - it never is on supported
  browsers, but the line costs nothing); `committed = 0`.
- Loop while `committed < file.size`:
  - `end = min(committed + 128 MiB, size)`; `slice = file.slice(committed,
    end)`; `fd.append("file", slice, file.name)` (explicit name).
  - Query: `authQuery() + "&upload=" + id + "&offset=" + committed +
    "&total=" + size + "&last=" + (end === size ? 1 : 0)`.
  - Advance `committed` only from the response's `size`.
- Progress bar/speed/ETA recompute from `committed + e.loaded` over
  `file.size` (same rendering code and elements).
- On `200 {success:true}` of the last slice: today's path (queueDone++,
  showBatchSuccess with filename/size/sha256).
- Retryable (same slice, max 3 attempts, ~1 s pause; 429 waits 3 s):
  `error` event, HTTP 400 (stall), 408, 429, 5xx (507 included, see the
  terminal ruling below), network-ish failures. No error UI while
  retrying; the bar keeps its place.
- `409` is a resync, not an attempt: adopt `size`, continue (guarded:
  three consecutive resyncs with no progress -> honest failure).
- A lost final response stays idempotent: on completion the server keeps
  a short-lived record `upload id -> (filename, size, sha256)`, bounded
  by age (~5 min) and count. A retried last slice - including a
  single-slice send, which retries at offset 0, where the resync branch
  never runs - is answered from that record with the original success
  instead of rebuilding the file, which would complete a second time and
  leave a duplicate next to the first. A record miss falls back to the
  409 resync, so the record only removes a double cost; correctness
  never rests on it.
- Terminal (today's error flow: `sendQueue = []`, `finishQueue()`,
  error card): 401/403, other non-retryable 4xx, attempts exhausted,
  resync guard tripped. Each terminal outcome fires
  `cancel=1&upload=<id>&name=<name>` (fire-and-forget) so no staging
  survives a visible failure. A 401/403 skips the cleanup (the token is
  dead, so the cancel request would just 403). 507 is deliberately
  retryable, not terminal (ruling, review round): the terminal flow
  fires the cancel, which would unlink a staging file that may already
  hold every byte of the file - exactly what a transient finalize lock
  on Windows (AV scanning the freshly claimed name) produces. A quota
  507 is deterministic, so its retries are bounded waste (at most three
  more slices) and the honest quota message still follows at exhaustion.
- Cancel button: existing `currentXhr.abort()` + `cancel=1` cleanup.
- While the last slice's response (read-back hash) is pending: new key
  `upload.finalizing` (FR « Finalisation… » / EN "Finalizing…").
- `upload.unreachable`, `upload.serverError`, `session.expired`
  handling unchanged.

## Server files

- `src/opendrop/server/server.py`: `_route_upload` parses `upload`,
  `offset`, `total`, `last`, `cancel` and applies the limiter rules
  (carve-out from `limiter_general` for this path; the limiters run
  before the strict id/offset validation so junk params cannot bypass
  the budgets); `_handle_upload` implements staging rules, `last`
  verification/hash/rename, per-slice `transfer_state`, and the
  completion record above; `cancel` unlinks the guarded staging path
  with a few short retries (on Windows the aborted slice's handle - or
  an AV scanner - can deny the unlink for a moment). Pre-read answers
  (the resync 409) sit on the existing drain, whose byte bound now
  covers one whole slice (128 MiB + framing): closing on a full-size
  unread slice would reset the connection and could eat the very
  response the client needs. DiskError/TimeoutError/generic mappings
  unchanged.
- `src/opendrop/server/multipart.py`: `parse_multipart_upload(...,
  offset=0, staging_path=None)` - `staging_path` (validated) replaces the
  `xb` destination when provided; `r+b` + seek for `offset > 0`, truncate
  for `0`; abort cleanup unlinks only the staging file it was given
  (legacy path keeps today's behavior).
- `src/opendrop/server/rate_limit.py`: add `limiter_part`.

## Tests (planned additions; counts updated in docs afterwards)

- Multi-slice assembly: 3 slices -> exact bytes at staging, committed
  sizes track, last returns whole-file sha256 verified against an
  independent hash, final file appears only after `last`.
- Append rules: stale tail truncated; short 409 adopts size; missing
  staging at `offset>0` -> `409 size 0`.
- `last` size verification: `total` mismatch -> 409, no rename.
- Uniquify at rename: a complete same-name file survives a second send;
  post-uniquify filename is in the final response.
- `upload` id validation: bad id (path chars, wrong length) rejected;
  staging path stays inside the receive dir.
- `cancel=1` unlinks staging; repeat cancel succeeds; legacy requests
  (no `upload`) behave exactly as today (existing suites green).
- Protocol pins (review round): the query `name` beats the multipart
  disposition filename (staging and final name come from the query); a
  traversal name stays contained in the receive folder (upload and
  cancel); a real received file is never touched by cancel; a zero-byte
  send completes with the empty hash; a retried last slice after
  completion answers the recorded result without creating a duplicate.
- Limiters: 11th `offset=0`/legacy upload still 429 (existing pin);
  >10 `offset>0` slices succeed within a minute (new pin).
- `transfer_state`: `done` only on last slice; `received` crosses slices
  monotonically.

## Acceptance (manual, before any commit is ordered)

The author runs the original failing scenario end to end in **Zen**:
drop `Dossier-Gros-4Go`, zip, send - it must complete with the success
card and SHA-256, file valid (open the zip). Plus one phone-side send if
convenient. Regression spot-checks: small file send, password zip.

## Builder-check resolutions (Q -> decision)

1. Offset-0 reuse could destroy a complete same-name file of a different
   size -> **no reuse of final names at all**: uploads write to a unique
   staging file and `os.replace` only after verification; uniquify at
   rename preserves today's "never clobber" exactly. (My call.)
2. Concurrent same-name writers -> per-send `upload` id gives each send
   its own staging file; `cancel` can only ever unlink `.part` files.
   (My call.)
3. Partial visibility/quota -> parity with today (today's growing partial
   is already in the folder and counted); not hidden, `.part` suffix is
   self-explanatory. (My call.)
4. Slice 0 always sends explicit `upload/offset=0/total`; absent params =
   untouched legacy path for cached pages. (My call.)
5. `last` verifies `stat == total` before hashing/rename -> 409 resync.
   (My call.)
6. Mid-retry `transfer_state` -> each slice start resets
   `active/error/received`; observers may see the honest stall error
   briefly between attempts. (My call.)
7. Slice-0 retries vs `limiter_upload` -> retries cap at 3, below the
   10/min budget; distinct-new-upload 429 behavior is pre-existing and
   unchanged (deferred-list note). (My call.)
8. Acceptance gate -> manual Zen multi-GB verification added above;
   commit remains ordered by the author only after it passes. (My call -
   matches the standing process.)
