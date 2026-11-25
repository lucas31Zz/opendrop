/* OpenDrop service worker: NETWORK-FIRST shell, cache as offline fallback.

   The point of this file is plan Review Focus 3 - a stale service
   worker must NEVER pin users on an old UI after a release. So the
   network is asked FIRST for every shell asset and the cache is only
   consulted when the network fails: a release can never serve a stale
   shell. /api/** (uploads, downloads, Range responses) is never
   intercepted - only the exact GET paths listed in SHELL are handled
   at all, everything else falls through to the browser's default
   network handling.
*/
// One versioned cache name. BUMP THE -vN SUFFIX whenever the shell's
// static assets change (style.css, app.js, zip.js, index.html, icons):
// the activate handler below then deletes every older cache, so no
// previous release survives an update. -v4 ships the iPhone perf
// batch (web/app.js + web/style.css: rAF scroll pill, diffed
// transfer/quota paints, touch blur+entrance budget); -v3 shipped
// the pinned #pair= pairing overlay (web/app.js).
const CACHE = "opendrop-shell-v4";

// Exact allowlist of the shell's static paths (pathname only).
const SHELL = [
    "/",
    "/style.css",
    "/app.js",
    "/zip.js",
    "/manifest.webmanifest",
    "/icons/icon-192.png",
    "/icons/icon-512.png"
];

// Last-resort body when BOTH the network and the cache failed for a
// shell navigation. Handing `undefined`/null to respondWith would make
// Safari surface its own internal error page ("FetchEvent.respondWith
// received an error: Returned response is null") - what a QR scan used
// to show whenever the server was unreachable. A real Response keeps
// the failure inside the app (its own i18n "Server unreachable" state)
// or, here, on a small dedicated page.
const OFFLINE_HTML =
    "<!doctype html><html lang=en><meta charset=utf-8>" +
    "<meta name=viewport content=\"width=device-width,initial-scale=1\">" +
    "<title>OpenDrop</title>" +
    "<style>body{font-family:system-ui,sans-serif;display:grid;place-items:center;" +
    "min-height:100vh;margin:0;background:#101014;color:#e8e8ee;text-align:center}" +
    "p{line-height:1.7;padding:0 24px}b{font-size:17px}</style>" +
    "<p><b>OpenDrop est injoignable.</b><br>Le serveur est peut-être " +
    "arrêté : réessayez plus tard.<br><br><b>OpenDrop is unreachable." +
    "</b><br>The server may be stopped - try again later.</p></html>";

// Install: precache the whole shell, all-or-nothing. A missing shell
// asset REJECTS the install - that is a feature, not a bug: a broken
// precache can never activate and replace a working worker.
self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE).then((cache) => cache.addAll(SHELL))
    );
});

// Activate: drop every cache from an older version, then claim the
// open pages so they are controlled without waiting for a reload.
self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys()
            .then((names) => Promise.all(
                names.filter((name) => name !== CACHE)
                     .map((name) => caches.delete(name))))
            .then(() => self.clients.claim())
    );
});

// Fetch: return early (NO respondWith - the browser's default network
// handling) for anything that is not a GET of an exact SHELL pathname
// on this origin. /api/** therefore always reaches the server
// untouched. For shell paths: network-first - the network answers
// (and a 2xx answer refreshes the cache), the cache only covers a
// network failure - and a total miss answers the offline page, never
// null (see OFFLINE_HTML).
self.addEventListener("fetch", (event) => {
    const request = event.request;
    if (request.method !== "GET") return;
    const url = new URL(request.url);
    if (url.origin !== self.location.origin) return;
    if (SHELL.indexOf(url.pathname) === -1) return;
    event.respondWith(
        fetch(request)
            .then((response) => {
                // Only a 2xx answer becomes the offline fallback: a live
                // 404/5xx from the server still WINS (it is returned
                // unconditionally below) - it must simply never be
                // cached, or a transient error would outlive itself
                // while offline. The put chain also swallows its own
                // failure (e.g. cache quota): a background write must
                // never break the response already on its way.
                if (response.ok) {
                    const copy = response.clone();
                    caches.open(CACHE)
                        .then((cache) => cache.put(request, copy))
                        .catch(() => {});
                }
                return response;
            })
            .catch(() =>
                // The fallback must NEVER resolve to null: Safari turns a
                // null respondWith into its internal error page. The QR
                // navigation always carries ?token= while the precache
                // keys are the plain paths, so match IGNORING the query;
                // if iOS evicted the cache entirely, answer with
                // OFFLINE_HTML instead of falling into the same hole.
                caches.match(request, { ignoreSearch: true }).then(
                    (cached) =>
                        cached ||
                        new Response(OFFLINE_HTML, {
                            status: 503,
                            statusText: "Service Unavailable",
                            headers: { "content-type": "text/html; charset=utf-8" },
                        })
                )
            )
    );
});
