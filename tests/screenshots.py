"""Release screenshots: FR/EN x dark/light of the Send page.

Run as `python -m tests.screenshots` - the module name carries NO
test_ prefix on purpose, so it never joins a suite loop. Playwright is
an OPTIONAL test extra (`pip install -e ".[e2e]"`): when the module or
chromium is missing, this script prints a loud SKIPPED line and exits
0 - unless OPENDROP_SHOTS_REQUIRED=1 (CI) turns any skip or launch
failure into a red run. A screenshot failure is ALWAYS a failure, flag
or no flag: skipping is only for missing tooling, never for a broken
app.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from tests.conftest import TestResult, _start_server, _url, ip, urlopen

r = TestResult()

_REQUIRED = os.environ.get("OPENDROP_SHOTS_REQUIRED") == "1"

# The four release screenshots: language x theme, exactly the matrix
# the release workflow uploads.
VARIANTS = [("fr", "dark"), ("fr", "light"), ("en", "dark"), ("en", "light")]

# The release screenshots are taken at one fixed size so the four
# images are comparable line by line.
VIEWPORT = {"width": 1280, "height": 800}


def _device_token(port, token):
    """The 32-char device token, exactly what the desktop displays."""
    with urlopen(_url(port, "/api/devices", token)) as resp:
        return json.loads(resp.read())["device_token"]


def _pair(page, port, token) -> None:
    """Pair through the REAL overlay - the locked phone flow.

    Copied from tests/test_e2e.py: a locked page opened by the #pair=
    QR link pre-fills #pair-token, #btn-pair registers this IP and
    hands back a session token the page stores before reloading into
    the app. Every variant starts its own server (fresh device
    registry), so each one pairs itself exactly once.
    """
    device = _device_token(port, token)
    # No ?token= on purpose: this is the locked phone flow.
    page.goto(f"https://{ip}:{port}/#pair={device}")
    page.fill("#pair-token", device)
    page.click("#btn-pair")
    # Pair answers with a fresh session token and reloads into the
    # app; #drop-zone only exists (visible) inside the unlocked app.
    page.wait_for_selector("#drop-zone", timeout=15_000)


def _skip(reason):
    print(f"SKIPPED ({reason})")
    if _REQUIRED:
        print("OPENDROP_SHOTS_REQUIRED=1: a skip is a failure.")
        return False
    return r.summary()


def _shoot(browser) -> None:
    """One fresh server + one fresh context per (language, theme).

    language/theme are create_server kwargs, forwarded by conftest's
    _start_server(**kwargs); each server gets a fresh port and its own
    device registry, so every variant pairs itself. All waits carry an
    explicit timeout, and the context/server are closed on every path.
    """
    ref = os.environ.get("GITHUB_REF_NAME") or "dev"
    out_dir = Path("dist")
    out_dir.mkdir(parents=True, exist_ok=True)
    for lang, theme in VARIANTS:
        server = None
        context = None
        try:
            server, port, token = _start_server(language=lang, theme=theme)
            context = browser.new_context(ignore_https_errors=True,
                                          viewport=VIEWPORT)
            page = context.new_page()
            _pair(page, port, token)
            page.goto(_url(port, "/"))
            page.wait_for_selector(".logo", timeout=15_000)
            # The static HTML ships en+dark; French and light are applied
            # only by the async /api/info answer (app.js applyLang /
            # applyTheme). .logo sits in the static markup, so waiting
            # for it alone RACES that fetch - measured 2026-10-19:
            # fr-dark and en-dark came out byte-identical (same SHA256,
            # screenshot taken before French applied). Pin the FINAL
            # language+theme state before the shot; all waits stay
            # bounded (15 s), and a server that never applies its own
            # config fails loudly instead of shipping wrong images.
            page.wait_for_function(
                "([l, t]) => document.documentElement.lang === l &&"
                " document.documentElement.getAttribute('data-theme') === t",
                arg=[lang, theme], timeout=15_000)
            # Every fresh document plays the .logo/#app rise-in entrance
            # animation (style.css: #app starts at opacity 0, delay 0.08s,
            # 0.55s long), and Playwright's "visible" IGNORES opacity -
            # .logo and the lang/theme gate can all pass while #app is
            # still invisible (measured 2026-10-19: shots came out as a
            # bare backdrop). #app has the LONGEST entrance (ends last),
            # so waiting for its computed opacity of 1 pins every
            # entrance animation's end - bounded at 15 s.
            page.wait_for_function(
                "() => getComputedStyle(document.getElementById('app'))"
                ".opacity === '1'", timeout=15_000)
            path = out_dir / f"OpenDrop-{ref}-{lang}-{theme}.png"
            page.screenshot(path=str(path), full_page=False)
            r.check(f"screenshot {lang}-{theme}", True)
        except Exception as e:
            # A screenshot failure is ALWAYS a failure: skipping is
            # only for missing tooling, never for a broken app.
            r.check(f"screenshot {lang}-{theme}", False,
                    f"{type(e).__name__}: {e}")
        finally:
            if context is not None:
                context.close()
            if server is not None:
                server.shutdown()
                server.server_close()


def screenshots():
    print("--- Release screenshots (fr/en x dark/light) ---\n")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        return _skip(f"playwright is not installed ({e}); "
                     'run: python -m pip install -e ".[e2e]"')

    try:
        pw = sync_playwright().start()
    except Exception as e:
        return _skip(f"playwright failed to start: {e}")

    try:
        try:
            browser = pw.chromium.launch()
        except Exception as e:
            first = str(e).splitlines()[0] if str(e) else type(e).__name__
            return _skip(f"chromium is not installed "
                         f"(python -m playwright install chromium); {first}")
        try:
            _shoot(browser)
        finally:
            browser.close()
    finally:
        pw.stop()

    return r.summary()


if __name__ == "__main__":
    sys.exit(0 if screenshots() else 1)
