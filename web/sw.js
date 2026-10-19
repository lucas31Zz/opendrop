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
// previous release survives an update.
const CACHE = "opendrop-shell-v1";

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
// network failure.
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
            .catch(() => caches.match(request))
    );
});
