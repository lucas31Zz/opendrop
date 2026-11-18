"""E2E suite: the three real browsers drive the real UI against a real server.

Run as `python -m tests.test_e2e`. Playwright is an OPTIONAL test extra
(`pip install -e ".[e2e]"`): when the module or the browsers are
missing, the suite prints a loud SKIPPED line and exits 0 - unless
OPENDROP_E2E_REQUIRED=1 (CI) turns any skip or launch failure into a
red suite. A scenario exception is ALWAYS a failure, flag or no flag:
skipping is only for missing tooling, never for a broken app.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import sys
import time

from tests.conftest import (TestResult, _start_server, _WORKSPACE, _url,
                            dd, ip, sd, urlopen)

r = TestResult()

_REQUIRED = os.environ.get("OPENDROP_E2E_REQUIRED") == "1"

BROWSERS = ["chromium", "firefox", "webkit"]

# Printed LOUDLY once at the start of EVERY run - never a silent skip,
# never a skip of a scenario: it documents WHY the scenario matrix below
# is not the full cross product. Re-include webkit in the two-slice
# scenarios when Playwright fixes the driver (or if a real Safari run
# contradicts the diagnosis - that would make it a product bug).
KNOWN_DRIVER_ISSUES = {
    "playwright-webkit-partial-blob-slice": (
        "Playwright-WebKit on Windows mis-streams a partial Blob.slice of a "
        "file-backed blob: it reads 46 bytes past the slice end (exactly the "
        "multipart epilogue length) and drops the closing boundary, so the "
        "server rightly answers 400 \"Transfer interrupted or incomplete\". "
        "Diagnosed 2026-10-19 with byte-level dumps: the same product code is "
        "green on chromium+firefox, and webkit is green for whole-file "
        "uploads up to 128 MiB. Consequence: webkit is excluded ONLY from the "
        "two-slice scenarios and still runs upload_single_slice, so it is "
        "genuinely exercised."
    ),
}

# One launched engine per name, shared by every context of that engine.
_BROWSERS: dict = {}

# Extra launch args, per engine. Chromium only: a context's
# ignore_https_errors=True covers page loads, but the SERVICE WORKER
# script fetch is not covered - against the suite's untrusted cert
# (the local CA is not installed on the test machine) the
# registration fails with the console error "An SSL certificate
# error occurred when fetching the script" and the worker never
# installs (measured 2026-10-19; firefox and webkit install fine, so
# the certificate is accepted session-wide there). The browser-wide
# flag gives chromium the SAME trust for every request of this test
# browser - it weakens no assertion, it only makes the certificate
# ignored like ignore_https_errors promises.
_LAUNCH_ARGS = {"chromium": ["--ignore-certificate-errors"]}

# The real pairing overlay is exercised once per process: every browser
# context connects from 127.0.0.1, so one pairing registers the IP for
# good - exactly how a phone stays known after it paired once.
_PAIRED = {"done": False}

# Big sources live in a dedicated folder of the conftest temporary
# workspace (atexit-cleaned): never in the repo tree, and never in dd -
# dd is what the assertions read as the receive folder.
_SRC_DIR = os.path.join(_WORKSPACE, "e2e_src")
os.makedirs(_SRC_DIR, exist_ok=True)

# 20 MB stays under one slice (SLICE_SIZE is 128 MiB), so this upload
# travels as a single request - the path webkit can still be trusted on.
SINGLE_SIZE = 20 * 1024 * 1024
# 128 MiB (one full slice) + 2 MiB: the upload travels as exactly two
# slices, so the chunked staging path is really exercised.
MULTI_SIZE = 128 * 1024 * 1024 + 2 * 1024 * 1024
# The app's SLICE_SIZE: a staging file that has reached this size is
# the proof that slice 1 arrived complete on the server.
SLICE1 = 128 * 1024 * 1024

# The 130 MB two-slice source is generated ONCE per process and shared
# by upload_multislice and upload_cancel (130 MB of os.urandom is not
# free, and both scenarios upload identical bytes).
_SOURCES: dict = {}


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _make_source(name, size):
    """A size-byte os.urandom file inside the conftest workspace."""
    path = os.path.join(_SRC_DIR, name)
    with open(path, "wb") as f:
        f.write(os.urandom(size))
    return path


def _ensure_source_file(name, size):
    """The same path for every browser of the process: generate once."""
    path = _SOURCES.get(name)
    if path is None or not os.path.exists(path):
        path = _make_source(name, size)
        _SOURCES[name] = path
    return path


def _device_token(port, token):
    """The 32-char device token, exactly what the desktop displays."""
    with urlopen(_url(port, "/api/devices", token)) as resp:
        return json.loads(resp.read())["device_token"]


def _new_context(browser_name, port, token) -> "BrowserContext":
    """Fresh context with ignore_https_errors=True (untrusted local cert).

    The first call of the process also pairs through the REAL overlay:
    a locked page opened by the #pair= QR link pre-fills #pair-token,
    #btn-pair registers this IP and hands back a session token the page
    stores before reloading straight into the app. Later contexts skip
    that step - they all share the loopback IP the pairing registered.
    """
    context = _BROWSERS[browser_name].new_context(ignore_https_errors=True)
    page = context.new_page()
    if not _PAIRED["done"]:
        device = _device_token(port, token)
        # No ?token= on purpose: this is the locked phone flow.
        page.goto(f"https://{ip}:{port}/#pair={device}")
        page.fill("#pair-token", device)
        page.click("#btn-pair")
        # Pair answers with a fresh session token and reloads into the
        # app; #drop-zone only exists (visible) inside the unlocked app.
        page.wait_for_selector("#drop-zone", timeout=15_000)
        _PAIRED["done"] = True
    return context


# The hold gate, installed as an init script BEFORE the scenario's
# navigation. It never lets Playwright's network interception near an
# upload: continuing a 128 MiB multipart body through page.route
# crawls at ~150 KB/s and dies with 400 (diagnosed on chromium and
# firefox, 2026-10-19 - see the suite report), so the queue lives in
# the page instead. XMLHttpRequest.open stashes each request's URL and
# send() QUEUES any /api/upload send that does not carry cancel=1:
# the request never leaves the page - still pending, exactly like a
# held route - while the event loop keeps running, so clicks and
# probes during the hold work normally. cancel=1 (the app sends it as
# a plain fetch anyway) and every non-upload request pass straight
# through. Nothing here ever sleeps.
_HOLD_GATE_JS = """
(() => {
    if (window.__holdGate) return;
    const realOpen = XMLHttpRequest.prototype.open;
    const realSend = XMLHttpRequest.prototype.send;
    const queue = {};
    let nextId = 0;
    window.__holdGate = {
        peek: () => Object.keys(queue).map((id) => [id, queue[id].url]),
        fire: (ids) => {
            for (const id of ids) {
                const entry = queue[id];
                delete queue[id];
                if (!entry) continue;
                // The app may have aborted a queued send meanwhile
                // (a cancel did): firing it then throws - swallowed.
                try { realSend.call(entry.xhr, entry.body, ...entry.rest); }
                catch (err) { /* already aborted: nothing to send */ }
            }
        },
        flush: () => window.__holdGate.fire(Object.keys(queue))
    };
    XMLHttpRequest.prototype.open = function (method, url, ...rest) {
        this.__holdUrl = url;
        return realOpen.call(this, method, url, ...rest);
    };
    XMLHttpRequest.prototype.send = function (body, ...rest) {
        const url = String(this.__holdUrl || "");
        if (url.indexOf("/api/upload") === -1 || url.indexOf("cancel=1") !== -1) {
            return realSend.call(this, body, ...rest);
        }
        const id = String(++nextId);
        queue[id] = { url: url, xhr: this, body: body, rest: rest };
    };
})();
"""


class _Hold:
    """Handle returned by _hold_uploads: settle() + resume_all()."""

    def __init__(self, page, hold_pred):
        self._page = page
        self._hold_pred = hold_pred

    def settle(self, deadline=15.0) -> bool:
        """Release every queued upload the predicate does NOT want held.

        hold_pred lives in Python, so the page queues first and this
        polls the queue (50 ms apart, straight Python flow - there is
        no handler to block) until at least one request has been let
        through: that release is what lets slice 1 travel at native
        speed. Returns True as soon as something was released, False
        when the deadline passes - the caller asserts on it, so a
        gate that never sees traffic fails loudly instead of
        passing silently.
        """
        end = time.time() + deadline
        while time.time() < end:
            queued = self._page.evaluate("() => window.__holdGate.peek()")
            fire = [eid for eid, url in queued if not self._hold_pred(url)]
            if fire:
                self._page.evaluate("(ids) => window.__holdGate.fire(ids)", fire)
                return True
            time.sleep(0.05)
        return False

    def resume_all(self):
        """Release every request still queued in the page.

        The per-entry try/except lives inside the page (an aborted
        send raises there and is swallowed); the evaluate itself is
        wrapped too, for the case where the page or context is
        already gone.
        """
        try:
            self._page.evaluate("() => window.__holdGate.flush()")
        except Exception:
            pass


def _hold_uploads(page, hold_pred) -> "_Hold":
    """Hold upload requests IN THE PAGE until resume_all() - no route.

    R3 (2026-10-19): the hold no longer uses page.route, because any
    registered route makes the driver pause and auto-continue every
    request, which poisons large upload bodies (see _HOLD_GATE_JS).
    The contract is unchanged: hold_pred(url) true means the request
    is STORED and never sent (pending at the page, event loop free,
    UI interaction fully available), false means it passes promptly,
    cancel=1 always passes, resume_all() releases what is left -
    try/except per entry - and nothing ever sleeps in a callback.

    The gate must be installed BEFORE the scenario navigates: init
    scripts only reach documents loaded after add_init_script.
    """
    page.add_init_script(script=_HOLD_GATE_JS)
    return _Hold(page, hold_pred)


def scenario_upload_single_slice(page, server, port, token) -> None:
    """20 MB (one slice) reaches the success card byte-identical."""
    name = "e2e_single.bin"
    received = os.path.join(dd, name)
    # A previous browser's run of this scenario may own the name (the
    # server uniquifies collisions): start from a clean exact path.
    if os.path.exists(received):
        os.remove(received)
    source = _ensure_source_file(name, SINGLE_SIZE)

    page.goto(_url(port, "/"))
    page.locator("#file-input").set_input_files(source)
    page.wait_for_selector("#success-msg", timeout=120_000)

    assert os.path.exists(received), f"{name} never landed in the receive folder"
    assert _sha256(received) == _sha256(source), "received bytes differ from source"
    parts = glob.glob(os.path.join(dd, "*.part"))
    assert not parts, f"staging leftover: {parts}"


def scenario_upload_multislice(page, server, port, token) -> None:
    """130 MB (two slices) reaches the success card byte-identical."""
    name = "e2e_two_slice.bin"
    received = os.path.join(dd, name)
    if os.path.exists(received):
        os.remove(received)
    source = _ensure_source_file(name, MULTI_SIZE)

    page.goto(_url(port, "/"))
    page.locator("#file-input").set_input_files(source)
    page.wait_for_selector("#success-msg", timeout=120_000)

    assert os.path.exists(received), f"{name} never landed in the receive folder"
    assert _sha256(received) == _sha256(source), "received bytes differ from source"
    parts = glob.glob(os.path.join(dd, "*.part"))
    assert not parts, f"staging leftover: {parts}"


def scenario_upload_cancel(page, server, port, token) -> None:
    """Cancel with slice 2 HELD: no staging left, no success card.

    hold_pred keeps every upload URL except the first slice (offset=0):
    settle() releases slice 1 so it travels at native speed and the
    staging file reaches a full slice on disk - that proof is R2's
    precondition, "slice 1 has completed and staging exists" - while
    slice 2 stays queued in the page with the event loop fully
    available. The cancel window is deterministic, not a race.
    """
    name = "e2e_two_slice.bin"
    source = _ensure_source_file(name, MULTI_SIZE)

    # The gate goes in BEFORE the navigation: init scripts only reach
    # documents loaded after add_init_script.
    hold = _hold_uploads(page, lambda url: "offset=0" not in url)
    page.goto(_url(port, "/"))
    try:
        page.locator("#file-input").set_input_files(source)

        # The page queued both slices' sends; the predicate must let
        # slice 1 through - never assume it did.
        assert hold.settle(), "the hold gate never released the first slice"
        deadline = time.time() + 30
        staged = 0
        while time.time() < deadline:
            parts = glob.glob(os.path.join(dd, name + "*.part"))
            staged = max([os.path.getsize(p) for p in parts] or [0])
            if staged >= SLICE1:
                break
            time.sleep(0.25)
        assert staged >= SLICE1, \
            f"slice 1 never landed whole (staging at {staged} bytes)"

        page.wait_for_selector("#btn-cancel", state="visible", timeout=15_000)
        page.locator("#btn-cancel").click()

        # Within 10 s this send's staging file is gone...
        leftover = glob.glob(os.path.join(dd, name + "*.part"))
        deadline = time.time() + 10
        while leftover and time.time() < deadline:
            time.sleep(0.25)
            leftover = glob.glob(os.path.join(dd, name + "*.part"))
        assert not leftover, f"staging file still present 10 s after cancel: {leftover}"
        # ...and the success card never became visible.
        assert not page.locator("#success-msg").is_visible(), \
            "success card showed after cancel"
    finally:
        hold.resume_all()


# The synthetic beforeunload probe, pinned by ruling R3: the event
# MUST be created with {cancelable: true} and MUST read defaultPrevented
# - a plain Event's returnValue is the legacy boolean !canceled (always
# True) and preventDefault is a no-op on it, so returnValue can never
# discriminate armed from idle (measured on chromium/firefox/webkit).
# armed -> true (RED before the feature: no listener yet), idle -> false.
_PROBE_JS = ("() => { const e = new Event('beforeunload', "
             "{cancelable: true}); window.dispatchEvent(e); "
             "return e.defaultPrevented; }")


def scenario_title_beforeunload(page, server, port, token) -> None:
    """Held send: "% · OpenDrop" title + armed guard; both exits restore.

    hold_pred = True holds the 20 MB file's single slice in the page:
    the transfer is active while the event loop stays free, so the tab
    title and a synthetic beforeunload probe are readable mid-flight.
    The gate is installed BEFORE navigation (init script), resume_all()
    runs in a finally, and the cancel leg repeats the whole sequence on
    a fresh context so nothing from the success leg leaks into it. The
    two assertions after each exit pin plan Review Focus 4: a guard
    left armed after cancel/finish means a "leave site?" prompt with
    nothing running.
    """
    source = _ensure_source_file("e2e_single.bin", SINGLE_SIZE)

    # The gate goes in BEFORE the navigation: init scripts only reach
    # documents loaded after add_init_script.
    hold = _hold_uploads(page, lambda url: True)
    page.goto(_url(port, "/"))
    try:
        page.locator("#file-input").set_input_files(source)
        # During the hold the title must carry the percentage - RED
        # before the feature exists: it never changes.
        page.wait_for_function(
            "() => /% \\u00b7 OpenDrop$/.test(document.title)",
            timeout=15_000)
        ret = page.evaluate(_PROBE_JS)
        assert ret, \
            f"beforeunload probe not armed while a transfer is held: {ret!r}"
    finally:
        hold.resume_all()

    # Success path: base title restored, guard silent again. The gate
    # patch stays installed for the whole document, so a send the app
    # starts AFTER the flush (a 429/5xx retry of the released slice)
    # gets queued again - release it while waiting, or the retry would
    # sit in the queue forever and the success card never shows.
    deadline = time.time() + 120
    while True:
        try:
            page.wait_for_selector("#success-msg", timeout=1000)
            break
        except Exception:
            if time.time() > deadline:
                raise
            hold.resume_all()
    title = page.evaluate("() => document.title")
    assert title == "OpenDrop", \
        f"base title not restored after success: {title!r}"
    ret = page.evaluate(_PROBE_JS)
    assert not ret, \
        f"beforeunload probe still armed after success: {ret!r}"

    # Cancel path on a FRESH context: same hold, then #btn-cancel -
    # title back to base within 10 s, probe false again.
    context = page.context.browser.new_context(ignore_https_errors=True)
    p2 = context.new_page()
    hold2 = _hold_uploads(p2, lambda url: True)
    p2.goto(_url(port, "/"))
    try:
        p2.locator("#file-input").set_input_files(source)
        p2.wait_for_function(
            "() => /% \\u00b7 OpenDrop$/.test(document.title)",
            timeout=15_000)
        ret = p2.evaluate(_PROBE_JS)
        assert ret, \
            f"beforeunload probe not armed while a held send is active: {ret!r}"
        p2.wait_for_selector("#btn-cancel", state="visible", timeout=15_000)
        p2.locator("#btn-cancel").click()
        p2.wait_for_function("() => document.title === 'OpenDrop'",
                             timeout=10_000)
        ret = p2.evaluate(_PROBE_JS)
        assert not ret, \
            f"beforeunload probe still armed after cancel: {ret!r}"
    finally:
        # Close BEFORE resuming: flushing the held offset=0 body while
        # the context is alive makes the server create fresh staging
        # for an upload that was CANCELLED, and the context closing
        # right after interrupts that body - which leaves a .part in
        # the shared receive folder other scenarios assert is clean
        # (and burns a scarce new-upload rate-budget slot). With the
        # context gone, resume_all's evaluate raises and its own
        # try/except swallows it - the flush-of-an-aborted-send
        # contract the plan calls for, minus the server-side mess.
        context.close()
        hold2.resume_all()


def scenario_range_headers(page, server, port, token) -> None:
    """A Range request against a shared file answers 206 with the slice.

    The browser drives /api/download exactly like a resuming download
    manager would; the file is a 1 MB tiled pattern written into the
    conftest share folder and removed in a finally (sd is shared by the
    whole suite).
    """
    name = "range-e2e.bin"
    path = os.path.join(sd, name)
    tile = bytes(range(256)) * 4              # 1024-byte tile
    size = len(tile) * 1024                   # 1 MB patterned
    content = tile * (size // len(tile))
    try:
        with open(path, "wb") as f:
            f.write(content)
        resp = page.request.get(_url(port, f"/api/download/{name}"),
                                headers={"Range": "bytes=10-19"})
        assert resp.status == 206, f"expected 206, got {resp.status}"
        assert resp.headers.get("content-range") == f"bytes 10-19/{size}", \
            f"bad content-range: {resp.headers.get('content-range')}"
        assert resp.body() == content[10:20], "range body differs from source"
        plain = page.request.get(_url(port, f"/api/download/{name}"))
        assert plain.status == 200, f"expected 200, got {plain.status}"
        assert plain.headers.get("accept-ranges") == "bytes", \
            f"missing accept-ranges: {plain.headers.get('accept-ranges')}"
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


# RULING R4c (harness note, recorded by Task 7 - comment only, zero
# behavior change): this Playwright build does NOT await an async
# predicate passed to page.wait_for_function. The predicate's returned
# Promise object is truthy, so `async () => false` passes in 0 ms
# (measured 2026-10-19) - any future async wait_for_function in this
# suite would be a silent no-op and prove nothing. Async waits must
# therefore be Python-side polls via page.evaluate, which DOES await
# the expression's promise (the pattern _wait_sw_active below uses).
# Every wait_for_function predicate in this suite is deliberately
# synchronous for that reason.
def _wait_sw_active(page, timeout=5.0) -> bool:
    """Poll until getRegistration() exists AND holds an active worker.

    The polling happens in PYTHON around page.evaluate: evaluate AWAITS
    the async expression's promise, while this Playwright build's
    wait_for_function does not await an async function's promise - the
    returned Promise object is truthy immediately (measured 2026-10-19:
    'async () => false' passes wait_for_function in 0.00 s), so an
    async predicate there would pass vacuously and prove nothing.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if page.evaluate(
                "async () => { const r = await navigator.serviceWorker"
                ".getRegistration(); return !!(r && r.active); }"):
            return True
        time.sleep(0.1)
    return False


def scenario_pwa_manifest_sw(page, server, port, token) -> None:
    """Manifest + service worker: linked, registered, versioned, /api free.

    The seven assertions are the mechanical proof of the plan's Review
    Focus 3 - a stale service worker pinning users on an old UI. The
    network-first design of web/sw.js is checked from the outside: the
    document links the manifest, both static routes answer live with
    the right content types, then a real page.reload() runs and
    assertion 4 onward describes the POST-RELOAD document - an ACTIVE
    worker within 5 s, a set controller, caches.keys() holding exactly
    the ONE versioned cache (proof of the versioned name plus the
    activate-time cleanup of anything else), /api/download still
    answering its Range request untouched (206 + Content-Range + the
    exact bytes - the SW must never intercept /api/**), and finally a
    working post-SW UI.
    """
    # 1) the manifest link is in the document head, absolute path
    page.goto(_url(port, "/"))
    link = page.locator("link[rel=manifest]")
    assert link.count() == 1, \
        f"expected one link[rel=manifest], found {link.count()}"
    assert link.get_attribute("href") == "/manifest.webmanifest", \
        f"manifest href is {link.get_attribute('href')!r}"

    # 2) the manifest route answers 200 with the manifest media type,
    #    and the body is a real manifest for this app
    manifest = page.request.get(_url(port, "/manifest.webmanifest"))
    assert manifest.status == 200, f"manifest status {manifest.status}"
    mct = manifest.headers.get("content-type", "")
    assert "application/manifest+json" in mct, \
        f"manifest content-type is {mct!r}"
    data = json.loads(manifest.body())
    assert data.get("name") == "OpenDrop", f"manifest name {data.get('name')!r}"
    assert data.get("display") == "standalone", \
        f"manifest display {data.get('display')!r}"
    sizes = {icon.get("sizes") for icon in data.get("icons", [])}
    assert "192x192" in sizes and "512x512" in sizes, \
        f"manifest icon sizes {sizes!r}"

    # 3) the worker script route answers 200 as javascript
    sw = page.request.get(_url(port, "/sw.js"))
    assert sw.status == 200, f"sw.js status {sw.status}"
    assert "javascript" in sw.headers.get("content-type", ""), \
        f"sw.js content-type is {sw.headers.get('content-type')!r}"

    # PRECONDITION: the first load registers the worker - it reaches
    # ACTIVE within 5 s. Without this the reload below would have no
    # worker to be controlled by and the whole post-reload half would
    # be meaningless.
    assert _wait_sw_active(page, 5.0), \
        "no ACTIVE service worker (getRegistration().active) within 5 s on first load"

    # THE RELOAD - the heart of Review Focus 3 ("an E2E reload check
    # that the live server - not a cached copy - answers"): everything
    # from here on describes the POST-RELOAD document, which only
    # exists because a genuine navigation went through the registered
    # worker. The four numbered assertions below would all be vacuous
    # on the first-load page.
    page.reload()

    # 4) after the reload the registration EXISTS and is ACTIVE, <= 5 s
    #    (getRegistration() staying undefined or worker-less would mean
    #    the engine never really registered the worker at all)
    assert _wait_sw_active(page, 5.0), \
        "no ACTIVE service worker (getRegistration().active) within 5 s after reload"

    # The reloaded document must really be CONTROLLED by the worker
    # (registration alone would not make a navigation pass through the
    # fetch handler): the caches/Range/UI assertions below are only
    # meaningful from a controlled page, so wait for the controller
    # before running them.
    page.wait_for_function(
        "() => !!navigator.serviceWorker.controller", timeout=5_000)

    # 5) exactly ONE cache, and it is the versioned shell cache: this
    #    single comparison proves both the versioned name and the
    #    activate-time deletion of every other cache (read from the
    #    reloaded, worker-controlled page).
    keys = page.evaluate("async () => await caches.keys()")
    assert keys == ["opendrop-shell-v2"], f"caches.keys() = {keys!r}"

    # 6) from the reloaded, SW-CONTROLLED page: /api/download with a
    #    Range header has to pass the worker by untouched: 206, the
    #    right Content-Range and the exact 10 bytes (a SW that
    #    intercepts /api would break resume).
    name = "pwa-range.bin"
    tile = bytes(range(256))              # 256-byte tiled pattern
    size = len(tile) * 16                 # 4 KB, still tiled
    content = tile * (size // len(tile))
    path = os.path.join(sd, name)
    try:
        with open(path, "wb") as f:
            f.write(content)
        got = page.evaluate(
            """async (url) => {
                const resp = await fetch(url, {headers: {Range: "bytes=10-19"}});
                const buf = new Uint8Array(await resp.arrayBuffer());
                return {status: resp.status,
                        contentRange: resp.headers.get("content-range"),
                        body: Array.from(buf)};
            }""",
            f"/api/download/{name}?token={token}")
        assert got["status"] == 206, f"range status {got['status']}"
        assert got["contentRange"] == f"bytes 10-19/{size}", \
            f"content-range is {got['contentRange']!r}"
        assert bytes(got["body"]) == content[10:20], \
            "range body differs from the source slice"
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

    # 7) the reloaded, worker-controlled page is a working app: a REAL
    #    post-SW navigation check - #drop-zone is only rendered by the
    #    unlocked app, so this also proves the reload landed inside the
    #    app (not on the locked/pairing screen) and that the document
    #    served through the worker still boots end to end.
    page.wait_for_selector("#drop-zone", state="visible", timeout=10_000)


# Real phone user agents: the platform trust guide below is UA-driven,
# and the runner's own context (default desktop UA) stays the contrast.
_IPHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
              "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 "
              "Mobile/15E148 Safari/604.1")
_ANDROID_UA = ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

# The progress line is JS-rendered through t(), never a [data-i18n] node:
# the suite runs on a configured machine (fr) and in CI (en), so both
# spellings are accepted - and the count differs per guide (iOS = 4
# steps, Android = 3), hence one regex per guide.
_PROGRESS_STEP2_4 = re.compile(r"(Step 2 of 4|\u00c9tape 2 sur 4)")
_PROGRESS_STEP2_3 = re.compile(r"(Step 2 of 3|\u00c9tape 2 sur 3)")


def scenario_trust_guides(page, server, port, token) -> None:
    """The platform trust guide: detected device -> its own checklist.

    Neither iOS nor Android offers an API to install a certificate or
    flip the trust settings, so web/app.js guides instead - and this
    scenario proves that contract from the OUTSIDE on real phone user
    agents (each in its own context, since the guide keys off the agent):
    1) the desktop UA sees neither guide nor banner, and the manual
       per-OS list leads with the DETECTED desktop system (never a
       phone one),
    2) iPhone: the banner opens Settings on the 4-step iOS checklist,
       step 4's address is location.origin verbatim, one tick names the
       NEXT step and SURVIVES a reload (iOS drops tabs freely),
    3) Android: the same contract on its own 3-step checklist, with the
       manual list promoted to android - every other OS stays below it
       (detection can be wrong, nothing is ever removed),
    4) 4 (iOS) / 3 (Android) ticks show the success line, empty the
       progress and hide the banner for good.
    Progress strings are matched in both languages (fr on the
    configured machine, en in CI).
    """
    # 0) the runner's own DESKTOP context: no guide, no banner.
    page.goto(_url(port, "/"))
    page.wait_for_selector("#drop-zone", state="visible", timeout=15_000)
    page.click("#settings-btn")
    page.wait_for_selector("#settings-screen", state="visible")
    assert not page.locator("#trust-guide").is_visible(), \
        "the iOS guide must stay hidden on a desktop UA"
    assert not page.locator("#trust-banner").is_visible(), \
        "the trust banner must stay hidden on a desktop UA"
    # The manual list is REORDERED by detection (never shortened): on a
    # desktop the desktop line must lead - and never a phone one.
    head_os = page.locator("#trust-steps .trust-list li").first \
        .get_attribute("data-os")
    assert head_os in ("windows", "macos", "linux"), \
        f"a desktop system must lead the list, got {head_os!r}"

    browser = page.context.browser
    context = browser.new_context(ignore_https_errors=True,
                                   user_agent=_IPHONE_UA)
    try:
        phone = context.new_page()
        phone.goto(_url(port, "/"))
        phone.wait_for_selector("#drop-zone", state="visible", timeout=15_000)

        # 1) the banner: the FIRST thing the checklist offers an
        #    iPhone that has not completed the trust setup yet.
        banner = phone.locator("#trust-banner")
        assert banner.is_visible(), "no trust banner on an iPhone UA"

        # 2) the banner is the entry point: it opens Settings directly
        #    on the unfolded guide (smooth scroll aside).
        phone.click("#trust-banner-open")
        phone.wait_for_selector("#settings-screen", state="visible")
        guide = phone.locator("#trust-guide")
        assert guide.is_visible(), "the iOS guide must unfold on an iPhone UA"

        # 3) step 4 carries this origin verbatim: compare what the page
        #    shows against BOTH the live location.origin and the URL the
        #    scenario itself navigated to.
        shown = phone.locator("#trust-origin").text_content()
        live = phone.evaluate("location.origin")
        assert shown == live, f"trust-origin {shown!r} != live origin {live!r}"
        assert shown == f"https://{ip}:{port}", \
            f"trust-origin {shown!r} != https://{ip}:{port}"

        # 4) one tick: step 1 reads as done, the progress line names
        #    step 2 (in whatever language the server publishes). Tick
        #    selectors are scoped to the iOS body: both checklists ship
        #    the same data-trust-step attributes and the Android one is
        #    display:none here (never clickable).
        phone.click('#trust-guide-ios [data-trust-step="1"]')
        assert phone.locator("#trust-step-1").evaluate(
            "el => el.classList.contains('done')"), "step 1 not ticked"
        progress = phone.locator("#trust-progress").text_content() or ""
        assert _PROGRESS_STEP2_4.search(progress), \
            f"progress after tick 1 = {progress!r}"

        # 5) a reload (iOS drops tabs all the time) keeps the thread:
        #    the tick survives and the banner is still there.
        phone.reload()
        phone.wait_for_selector("#drop-zone", state="visible", timeout=15_000)
        assert banner.is_visible(), \
            "an unfinished checklist must keep the banner after a reload"
        phone.click("#settings-btn")
        phone.wait_for_selector("#settings-screen", state="visible")
        assert phone.locator("#trust-step-1").evaluate(
            "el => el.classList.contains('done')"), \
            "the tick did not survive the reload"
        progress = phone.locator("#trust-progress").text_content() or ""
        assert _PROGRESS_STEP2_4.search(progress), \
            f"progress after reload = {progress!r}"

        # 6) four ticks: success line in, progress cleared, banner out.
        for step in (2, 3, 4):
            phone.click(f'#trust-guide-ios [data-trust-step="{step}"]')
        assert phone.locator("#trust-finish").is_visible(), \
            "no success line after the 4th tick"
        assert not banner.is_visible(), \
            "the banner must hide once the checklist is complete"
        progress = phone.locator("#trust-progress").text_content() or ""
        assert progress == "", \
            f"the progress line must clear when complete: {progress!r}"
    finally:
        context.close()

    # --- Android: same contract, its own 3-step checklist -------------
    context = browser.new_context(ignore_https_errors=True,
                                   user_agent=_ANDROID_UA)
    try:
        droid = context.new_page()
        droid.goto(_url(port, "/"))
        droid.wait_for_selector("#drop-zone", state="visible", timeout=15_000)

        # 1) the banner greets an Android the same way it greets an
        #    iPhone - and the Android checklist is the one unfolded.
        assert droid.locator("#trust-banner").is_visible(), \
            "no trust banner on an Android UA"
        droid.click("#trust-banner-open")
        droid.wait_for_selector("#settings-screen", state="visible")
        assert droid.locator("#trust-guide-android").is_visible(), \
            "the Android guide must unfold on an Android UA"
        assert not droid.locator("#trust-guide-ios").is_visible(), \
            "the iOS checklist must never show on Android"

        # 2) the manual list leads with android - and keeps every other
        #    OS below (reordered, never shortened).
        head_os = droid.locator("#trust-steps .trust-list li").first \
            .get_attribute("data-os")
        assert head_os == "android", \
            f"android must lead the list, got {head_os!r}"
        assert droid.locator("#trust-steps .trust-list li").count() == 5, \
            "reordering must never remove a system from the list"

        # 3) step 3 carries this origin verbatim (the Android checklist
        #    ends at step 3, not 4).
        shown = droid.locator("#trust-origin-android").text_content()
        live = droid.evaluate("location.origin")
        assert shown == live, \
            f"trust-origin-android {shown!r} != live origin {live!r}"

        # 4) one tick: the progress line names step 2 of 3 (the count
        #    follows the checklist, both languages accepted).
        droid.click('#trust-guide-android [data-trust-step="1"]')
        assert droid.locator("#trust-step-a1").evaluate(
            "el => el.classList.contains('done')"), "step a1 not ticked"
        progress = droid.locator("#trust-progress").text_content() or ""
        assert _PROGRESS_STEP2_3.search(progress), \
            f"android progress after tick 1 = {progress!r}"

        # 5) a reload keeps the thread here too, then three ticks show
        #    the success line and clear the banner.
        droid.reload()
        droid.wait_for_selector("#drop-zone", state="visible", timeout=15_000)
        droid.click("#settings-btn")
        droid.wait_for_selector("#settings-screen", state="visible")
        assert droid.locator("#trust-step-a1").evaluate(
            "el => el.classList.contains('done')"), \
            "the android tick did not survive the reload"
        for step in (2, 3):
            droid.click(f'#trust-guide-android [data-trust-step="{step}"]')
        assert droid.locator("#trust-finish").is_visible(), \
            "no success line after the 3rd android tick"
        assert not droid.locator("#trust-banner").is_visible(), \
            "the banner must hide once the android checklist is complete"
    finally:
        context.close()


# Scenario -> the browsers it runs on. webkit is out of the two-slice
# scenarios by the PRINTED KNOWN_DRIVER_ISSUES limitation above - it is
# genuinely exercised by upload_single_slice all the same.
SCENARIOS = [("upload_single_slice", scenario_upload_single_slice,
              ["chromium", "firefox", "webkit"]),
             ("upload_multislice", scenario_upload_multislice,
              ["chromium", "firefox"]),
             ("upload_cancel", scenario_upload_cancel,
              ["chromium", "firefox"]),
             ("range_headers", scenario_range_headers,
              ["chromium", "firefox", "webkit"]),
             ("title_beforeunload", scenario_title_beforeunload,
              ["chromium", "firefox", "webkit"]),
             ("pwa_manifest_sw", scenario_pwa_manifest_sw,
              ["chromium", "firefox", "webkit"]),
             ("trust_guides", scenario_trust_guides,
              ["chromium", "firefox", "webkit"])]


def _skip(reason):
    print(f"SKIPPED ({reason})")
    if _REQUIRED:
        print("OPENDROP_E2E_REQUIRED=1: a skip is a failure.")
        return False
    return r.summary()


def test_e2e():
    print("--- E2E multi-browser (chromium, firefox, webkit) ---\n")
    for key, text in KNOWN_DRIVER_ISSUES.items():
        print(f"!!! KNOWN DRIVER ISSUE [{key}]:")
        print(f"    {text}\n")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        return _skip(f"playwright is not installed ({e}); "
                     'run: python -m pip install -e ".[e2e]"')

    try:
        pw = sync_playwright().start()
    except Exception as e:
        return _skip(f"playwright failed to start: {e}")

    skipped = []
    server, port, token = _start_server()
    try:
        for browser_name in BROWSERS:
            try:
                _BROWSERS[browser_name] = getattr(pw, browser_name).launch(
                    args=_LAUNCH_ARGS.get(browser_name))
            except Exception as e:
                first = str(e).splitlines()[0] if str(e) else type(e).__name__
                skipped.append(f"browser {browser_name} is not installed "
                               f"(python -m playwright install {browser_name}); {first}")
                continue
            try:
                for name, fn, browsers in SCENARIOS:
                    if browser_name not in browsers:
                        continue
                    context = None
                    try:
                        context = _new_context(browser_name, port, token)
                        page = context.new_page()
                        fn(page, server, port, token)
                        r.check(f"{name} [{browser_name}]", True)
                    except Exception as e:
                        # A scenario exception is ALWAYS a failure:
                        # skipping is only for missing tooling.
                        r.check(f"{name} [{browser_name}]", False,
                                f"{type(e).__name__}: {e}")
                    finally:
                        if context is not None:
                            context.close()
            finally:
                _BROWSERS[browser_name].close()
                del _BROWSERS[browser_name]
    finally:
        server.shutdown()
        server.server_close()
        pw.stop()

    for reason in skipped:
        print(f"SKIPPED ({reason})")
    passed = r.summary()
    if skipped and _REQUIRED:
        print("OPENDROP_E2E_REQUIRED=1: a skipped browser is a failure.")
        return False
    # Without the flag a missing browser skips (loudly), but every
    # scenario that DID run still has to be green.
    return passed


if __name__ == "__main__":
    sys.exit(0 if test_e2e() else 1)
