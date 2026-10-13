(function () {
    var TOKEN_KEY = "opendrop_token";

    // --- Internationalization ---------------------------------------
    // English is the default (static HTML); French is applied at startup
    // when the server reports "language": "fr" in /api/info.
    var LANG = "en";

    var T = {
        en: {
            "tab.send": "Send",
            "tab.receive": "Download",
            "drop.choose": "Choose a file",
            "drop.hint": "or drop it here",
            "transfer.cancel": "Cancel",
            "success.title": "Transfer complete",
            "success.new": "Send another file",
            "error.title": "Error",
            "error.retry": "Try again",
            "files.loading": "Loading...",
            "files.empty": "No files available.",
            "files.emptyHint": "Put files in the Share folder on the PC.",
            "files.refresh": "Refresh",
            "files.download": "Download",
            "files.rateLimited": "Too many requests. Wait.",
            "files.serverError": "Server error. Try again.",
            "files.loadError": "Load failed.",
            "session.locked": "Session locked",
            "session.scanHint": "Scan the QR code shown on the PC, or enter the session code.",
            "session.codeAria": "Session code",
            "session.unlock": "Unlock",
            "session.scan": "\ud83d\udcf7 Scan QR code",
            "session.closeScanner": "Close scanner",
            "session.retry": "Try again",
            "session.expired": "Session expired or invalid. Rescan the QR code.",
            "unlock.6chars": "The code has 6 characters.",
            "unlock.tooMany": "Too many attempts. Wait a minute.",
            "unlock.invalid": "Invalid code.",
            "unlock.offline": "Server unreachable.",
            "qr.notOpendrop": "Unrecognized QR code: not an OpenDrop link.",
            "camera.blocked": "Camera unavailable: this browser blocks access (insecure " +
                "context). Open the phone's camera app and scan the QR code: the " +
                "link opens by itself.",
            "camera.unsupported": "QR reading is not supported by this browser. Open the " +
                "phone's camera app and scan the QR code: the link opens by itself.",
            "camera.denied": "Camera access denied. Open the camera app and scan the QR " +
                "code directly.",
            "quota.unlimited": "{0} received (unlimited)",
            "quota.offline": "Server unreachable.",
            "theme.toggle": "Switch theme",
            "upload.serverError": "Server error ({0})",
            "upload.unreachable": "Could not reach the server.",
            "drop.chooseFolder": "Choose a folder",
            "drop.folderHint": "folders arrive zipped",
            "send.preparing": "Preparing...",
            "send.preparingError": "Could not read the folder.",
            "success.multiple": "{0} files sent",
            "files.search": "Search files...",
            "files.newFolder": "New folder",
            "files.folderDefault": "Folder",
            "files.rename": "Rename",
            "files.root": "Home",
            "files.moveTo": "Move to...",
            "files.selectAll": "Select all",
            "files.noMatch": "No matching files.",
            "files.emptyFolder": "This folder is empty.",
            "files.deleteFolder": "Delete folder",
            "files.downloadError": "Download failed.",
            "view.aria1": "One per row",
            "view.aria2": "Two per row",
            "view.aria4": "Four per row"
        },
        fr: {
            "tab.send": "Envoyer",
            "tab.receive": "T\u00e9l\u00e9charger",
            "drop.choose": "Choisir un fichier",
            "drop.hint": "ou glisser ici",
            "transfer.cancel": "Annuler",
            "success.title": "Transfert termin\u00e9",
            "success.new": "Envoyer un autre fichier",
            "error.title": "Erreur",
            "error.retry": "R\u00e9essayer",
            "files.loading": "Chargement...",
            "files.empty": "Aucun fichier disponible.",
            "files.emptyHint": "Mets des fichiers dans le dossier Partage sur le PC.",
            "files.refresh": "Rafra\u00eechir",
            "files.download": "T\u00e9l\u00e9charger",
            "files.rateLimited": "Trop de requ\u00eates. Attendez.",
            "files.serverError": "Erreur serveur. R\u00e9essayez.",
            "files.loadError": "\u00c9chec du chargement.",
            "session.locked": "Session verrouill\u00e9e",
            "session.scanHint": "Scannez le QR code affich\u00e9 sur le PC, ou saisissez le code de session.",
            "session.codeAria": "Code de session",
            "session.unlock": "D\u00e9verrouiller",
            "session.scan": "\ud83d\udcf7 Scanner le QR code",
            "session.closeScanner": "Fermer le scanner",
            "session.retry": "R\u00e9essayer",
            "session.expired": "Session expir\u00e9e ou invalide. Rescannez le QR code.",
            "unlock.6chars": "Le code comporte 6 caract\u00e8res.",
            "unlock.tooMany": "Trop de tentatives. Attendez une minute.",
            "unlock.invalid": "Code invalide.",
            "unlock.offline": "Serveur injoignable.",
            "qr.notOpendrop": "QR code non reconnu : ce n'est pas un lien OpenDrop.",
            "camera.blocked": "Cam\u00e9ra indisponible : ce navigateur bloque l'acc\u00e8s (contexte " +
                "non s\u00e9curis\u00e9). Ouvrez l'appareil photo du t\u00e9l\u00e9phone et scannez " +
                "le QR : le lien s'ouvre tout seul.",
            "camera.unsupported": "Lecture de QR non prise en charge par ce navigateur. Ouvrez " +
                "l'appareil photo du t\u00e9l\u00e9phone et scannez le QR : le lien " +
                "s'ouvre tout seul.",
            "camera.denied": "Acc\u00e8s cam\u00e9ra refus\u00e9. Ouvrez l'appareil photo et scannez le QR directement.",
            "quota.unlimited": "{0} re\u00e7us (illimit\u00e9)",
            "quota.offline": "Serveur injoignable.",
            "theme.toggle": "Changer de th\u00e8me",
            "upload.serverError": "Erreur serveur ({0})",
            "upload.unreachable": "Impossible de contacter le serveur.",
            "drop.chooseFolder": "Choisir un dossier",
            "drop.folderHint": "les dossiers arrivent compress\u00e9s en zip",
            "send.preparing": "Pr\u00e9paration...",
            "send.preparingError": "Impossible de lire le dossier.",
            "success.multiple": "{0} fichiers envoy\u00e9s",
            "files.search": "Rechercher des fichiers...",
            "files.newFolder": "Nouveau dossier",
            "files.folderDefault": "Dossier",
            "files.rename": "Renommer",
            "files.root": "Accueil",
            "files.moveTo": "D\u00e9placer vers...",
            "files.selectAll": "Tout cocher",
            "files.noMatch": "Aucun fichier correspondant.",
            "files.emptyFolder": "Ce dossier est vide.",
            "files.deleteFolder": "Supprimer le dossier",
            "files.downloadError": "\u00c9chec du t\u00e9l\u00e9chargement.",
            "view.aria1": "Un par ligne",
            "view.aria2": "Deux par ligne",
            "view.aria4": "Quatre par ligne"
        }
    };

    function t(key, arg) {
        var dict = T[LANG] || T.en;
        var text = dict[key];
        if (text === undefined) text = T.en[key];
        if (text === undefined) text = key;
        if (arg !== undefined) text = text.replace("{0}", arg);
        return text;
    }

    // --- theme -------------------------------------------------------
    // The desktop app publishes its light/dark choice on /api/info. This
    // page follows it by default; the button overrides it for this device
    // only, and the override is dropped as soon as the PC theme changes
    // (so following the PC again is never a manual chore).
    var THEME_KEY = "opendrop_theme";
    var THEME_BASE_KEY = "opendrop_theme_base";
    // Theme ids the server can publish: the same list as
    // src/opendrop/themes.py. Anything else falls back to "dark".
    var VALID_THEMES = ["light", "dark"];
    var serverTheme = "dark";
    var theme = "dark";

    function storeRead(key) {
        try { return localStorage.getItem(key); } catch (e) { return null; }
    }

    function storeWrite(key, value) {
        try { localStorage.setItem(key, value); } catch (e) { /* private mode */ }
    }

    function storeForget(key) {
        try { localStorage.removeItem(key); } catch (e) { /* private mode */ }
    }

    function isValidTheme(value) {
        return VALID_THEMES.indexOf(value) >= 0;
    }

    function normalizeTheme(value) {
        return isValidTheme(value) ? value : "dark";
    }

    function resolveTheme() {
        var base = normalizeTheme(serverTheme);
        var override = storeRead(THEME_KEY);
        if (isValidTheme(override)) {
            if (storeRead(THEME_BASE_KEY) === base) return override;
            storeForget(THEME_KEY);
            storeForget(THEME_BASE_KEY);
        }
        return base;
    }

    function applyTheme() {
        theme = resolveTheme();
        document.documentElement.setAttribute("data-theme", theme);
        var button = document.getElementById("theme-toggle");
        if (button) {
            // The icon shows the theme a tap switches to.
            button.textContent = theme === "dark" ? "\u2600" : "\u263e";
            var label = t("theme.toggle");
            button.title = label;
            button.setAttribute("aria-label", label);
        }
        var meta = document.querySelector('meta[name="theme-color"]');
        // Averages the mesh backdrop, so the browser chrome blends into
        // the page instead of stopping at a flat colour.
        if (meta) meta.setAttribute("content", theme === "dark" ? "#11141f" : "#eff2f8");
    }

    function toggleTheme() {
        storeWrite(THEME_KEY, theme === "dark" ? "light" : "dark");
        storeWrite(THEME_BASE_KEY, normalizeTheme(serverTheme));
        applyTheme();
    }

    var themeButton = document.getElementById("theme-toggle");
    if (themeButton) themeButton.addEventListener("click", toggleTheme);
    applyTheme();

    // --- Liquid Glass refraction: SVG displacement blended into the
    // backdrop filter of .tabs and .drop-zone. Only Chromium actually
    // renders url() there; CSS.supports only checks the grammar (it
    // says yes elsewhere too), so the engine is checked as well and
    // every other engine simply keeps the plain blur declared in
    // style.css. Runs for every visitor, session locked or not.
    if (window.CSS && CSS.supports &&
        CSS.supports("backdrop-filter", "url(#og-glass) blur(1px)") &&
        (window.chrome || /Edg\//.test(navigator.userAgent || ""))) {
        document.documentElement.classList.add("refract");
    }

    function applyLang() {
        document.documentElement.lang = LANG;
        var nodes = document.querySelectorAll("[data-i18n]");
        for (var i = 0; i < nodes.length; i++) {
            nodes[i].textContent = t(nodes[i].getAttribute("data-i18n"));
        }
        var attrs = document.querySelectorAll("[data-i18n-attr]");
        for (var j = 0; j < attrs.length; j++) {
            var spec = attrs[j].getAttribute("data-i18n-attr").split(":");
            if (spec.length === 2) attrs[j].setAttribute(spec[0], t(spec[1]));
        }
        applyTheme();
    }

    // Every request carries a deadline. A server that accepts the TCP
    // connection but never answers (frozen handler, Wi-Fi gone, phone
    // locked mid-handshake) must surface as an error the user can act on
    // instead of leaving the page stuck on a silent, near-black screen.
    function fetchWithTimeout(url, options, ms) {
        var opts = options || {};
        if (typeof AbortController === "undefined") return fetch(url, opts);
        var ctrl = new AbortController();
        var timer = setTimeout(function () { ctrl.abort(); }, ms);
        opts.signal = ctrl.signal;
        return fetch(url, opts).finally(function () { clearTimeout(timer); });
    }

    // Ask the server which language and theme it was configured with.
    fetchWithTimeout("/api/info", null, 10000)
        .then(function (r) { return r.json(); })
        .then(function (info) {
            if (info && info.lang === "fr" && LANG !== "fr") {
                LANG = "fr";
                applyLang();
            }
            if (info && normalizeTheme(info.theme) !== serverTheme) {
                serverTheme = normalizeTheme(info.theme);
                applyTheme();
            }
        })
        .catch(function () { /* server unreachable: keep the defaults */ });

    function storeToken(value) {
        try {
            localStorage.setItem(TOKEN_KEY, value);
        } catch (e) {
            // storage unavailable (private mode): nothing we can do
        }
    }

    function clearToken() {
        try {
            localStorage.removeItem(TOKEN_KEY);
        } catch (e) {
            // storage unavailable
        }
    }

    function getToken() {
        var fromUrl = new URLSearchParams(window.location.search).get("token");
        if (fromUrl) {
            storeToken(fromUrl);
            // Remove the secret from the address bar: it must not stay in
            // the history, screenshots or Referer headers.
            try {
                history.replaceState(null, "", location.pathname);
            } catch (e) {
                // ignore
            }
            return fromUrl;
        }
        try {
            return localStorage.getItem(TOKEN_KEY) || "";
        } catch (e) {
            return "";
        }
    }

    const token = getToken();

    var appEl = document.getElementById("app");
    var sessionScreen = document.getElementById("session-screen");
    var sessionDetail = document.getElementById("session-detail");

    function showSessionScreen(detail) {
        appEl.style.display = "none";
        sessionDetail.textContent = detail || "";
        sessionDetail.style.display = detail ? "" : "none";
        sessionScreen.style.display = "";
    }

    function endSession(detail) {
        // Only clear the stored token if it is the same as this page's:
        // a QR rescanned in another tab may have replaced it.
        var stored = "";
        try {
            stored = localStorage.getItem(TOKEN_KEY) || "";
        } catch (e) {
            // storage unavailable
        }
        if (!stored || stored === token) {
            clearToken();
        }
        showSessionScreen(detail);
    }

    var btnSessionRetry = document.getElementById("btn-session-retry");
    if (btnSessionRetry) {
        btnSessionRetry.addEventListener("click", function () {
            location.reload();
        });
    }

    // --- Unlock by code ---
    var codeInput = document.getElementById("code-input");
    var btnUnlock = document.getElementById("btn-unlock");
    var unlockError = document.getElementById("unlock-error");

    function showUnlockError(message) {
        unlockError.textContent = message;
        unlockError.style.display = message ? "" : "none";
    }

    function normalizeCode(value) {
        return (value || "").toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 6);
    }

    function unlockWithCode() {
        var code = normalizeCode(codeInput.value);
        if (code.length !== 6) {
            showUnlockError(t("unlock.6chars"));
            return;
        }
        showUnlockError("");
        btnUnlock.disabled = true;
        fetchWithTimeout("/api/session/unlock?code=" + encodeURIComponent(code),
            { method: "POST" }, 10000)
            .then(function (r) {
                return r.json().then(function (data) { return { status: r.status, data: data }; });
            })
            .then(function (res) {
                btnUnlock.disabled = false;
                if (res.status === 200 && res.data.token) {
                    storeToken(res.data.token);
                    location.reload();
                    return;
                }
                if (res.status === 429) {
                    showUnlockError(t("unlock.tooMany"));
                    return;
                }
                showUnlockError(res.data.error || t("unlock.invalid"));
            })
            .catch(function () {
                btnUnlock.disabled = false;
                showUnlockError(t("unlock.offline"));
            });
    }

    codeInput.addEventListener("input", function () {
        codeInput.value = normalizeCode(codeInput.value);
    });
    codeInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter") unlockWithCode();
    });
    btnUnlock.addEventListener("click", unlockWithCode);

    // --- QR scanner (mobile only) ---
    var btnScan = document.getElementById("btn-scan");
    var scanner = document.getElementById("scanner");
    var scannerVideo = document.getElementById("scanner-video");
    var btnScanClose = document.getElementById("btn-scan-close");
    var scanStream = null;
    var scanTimer = null;

    function stopScanner() {
        if (scanTimer) {
            clearInterval(scanTimer);
            scanTimer = null;
        }
        if (scanStream) {
            scanStream.getTracks().forEach(function (track) { track.stop(); });
            scanStream = null;
        }
        scanner.style.display = "none";
    }

    function handleScanned(rawValue) {
        var match = /[?&]token=([A-Za-z0-9]+)/.exec(rawValue);
        if (!match) {
            showUnlockError(t("qr.notOpendrop"));
            return;
        }
        storeToken(match[1]);
        stopScanner();
        location.reload();
    }

    // --- Decoder choice: Chrome and Edge ship BarcodeDetector, but
    // Safari (every iPhone) and Firefox do not - there the frames are
    // decoded by the bundled jsQR, fetched on demand so browsers with
    // the native detector never download it.
    var jsqrLoading = false;
    var jsqrWaiters = [];

    function flushJsQr(ok) {
        var waiters = jsqrWaiters;
        jsqrWaiters = [];
        for (var i = 0; i < waiters.length; i++) waiters[i](ok);
    }

    function withJsQR(done) {
        if (window.jsQR) { done(true); return; }
        jsqrWaiters.push(done);
        if (jsqrLoading) return;
        jsqrLoading = true;
        var script = document.createElement("script");
        script.src = "/jsqr.min.js";
        script.onload = function () {
            jsqrLoading = false;
            flushJsQr(typeof window.jsQR === "function");
        };
        script.onerror = function () {
            jsqrLoading = false;
            flushJsQr(false);
        };
        document.head.appendChild(script);
    }

    function startNativeLoop() {
        var detector = new window.BarcodeDetector({ formats: ["qr_code"] });
        var detecting = false;
        scanTimer = setInterval(function () {
            // Never queue a second detect() while one is running: on a
            // slow phone the promises would pile up and starve the UI.
            if (detecting) return;
            detecting = true;
            detector.detect(scannerVideo).then(function (codes) {
                if (codes && codes.length) handleScanned(codes[0].rawValue);
            }).catch(function () { /* no QR in view */ })
              .finally(function () { detecting = false; });
        }, 400);
    }

    function startJsQrLoop() {
        // jsQR runs on the CPU: the frame is shrunk to 480px wide first,
        // which is plenty to read a code filling the phone screen.
        var canvas = document.createElement("canvas");
        var ctx = canvas.getContext("2d", { willReadFrequently: true });
        scanTimer = setInterval(function () {
            if (document.hidden || !scannerVideo.videoWidth) return;
            var w = scannerVideo.videoWidth;
            var h = scannerVideo.videoHeight;
            var target = Math.min(w, 480);
            var targetH = Math.round(h * (target / w));
            if (canvas.width !== target || canvas.height !== targetH) {
                canvas.width = target;
                canvas.height = targetH;
            }
            ctx.drawImage(scannerVideo, 0, 0, target, targetH);
            var frame = ctx.getImageData(0, 0, target, targetH);
            // The code comes from a screen: normal polarity, skip the
            // inversion passes.
            var code = window.jsQR(frame.data, frame.width, frame.height, {
                inversionAttempts: "dontInvert"
            });
            if (code && code.data) handleScanned(code.data);
        }, 400);
    }

    function openCamera(useNative) {
        // Never two streams or two loops: tapping Scan again restarts.
        stopScanner();
        navigator.mediaDevices.getUserMedia({
            video: { facingMode: { ideal: "environment" } },
            audio: false
        }).then(function (stream) {
            scanStream = stream;
            scanner.style.display = "";
            scannerVideo.srcObject = stream;
            // iOS paints the stream only once play() runs, even with
            // playsinline and muted (this call sits in the tap gesture).
            var playing = scannerVideo.play();
            if (playing && playing.catch) playing.catch(function () { /* autoplay */ });
            if (useNative) startNativeLoop();
            else startJsQrLoop();
        }).catch(function () {
            showUnlockError(t("camera.denied"));
        });
    }

    function startScanner() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            showUnlockError(t("camera.blocked"));
            return;
        }
        if (typeof window.BarcodeDetector !== "undefined") {
            openCamera(true);
            return;
        }
        withJsQR(function (ok) {
            if (ok) openCamera(false);
            else showUnlockError(t("camera.unsupported"));
        });
    }

    btnScan.addEventListener("click", startScanner);
    btnScanClose.addEventListener("click", stopScanner);

    // Scanner button: phones and tablets only.
    if (window.matchMedia && window.matchMedia("(pointer: coarse)").matches) {
        btnScan.style.display = "";
    }

    // --- Overlay scrollbar: the native bar is hidden in style.css and a
    // pill thumb (same gradient and glow as the desktop app) rides the
    // right edge. It shows while the page moves or the pointer comes
    // near, hides again once you stop, and can be dragged. It lives
    // above the no-token guard: the session screen must scroll too.
    var scrollThumb = document.createElement("div");
    scrollThumb.className = "scroll-thumb";
    scrollThumb.setAttribute("aria-hidden", "true");
    document.body.appendChild(scrollThumb);

    var scrollHideTimer = 0;

    function scrollMetrics() {
        var root = document.documentElement;
        return {
            scrollable: Math.max(0, root.scrollHeight - window.innerHeight),
            track: window.innerHeight,
            total: root.scrollHeight
        };
    }

    function paintScrollThumb() {
        var m = scrollMetrics();
        if (m.scrollable < 8) {
            // Nothing to scroll: the pill must not float around.
            scrollThumb.classList.remove("visible");
            scrollThumb.style.pointerEvents = "";
            return;
        }
        // Short pages get a longer thumb, exactly like a native bar.
        var h = Math.max(34, m.track * (m.track / m.total));
        var travel = m.track - h;
        var y = travel > 0 ? (window.scrollY / m.scrollable) * travel : 0;
        scrollThumb.style.height = h + "px";
        scrollThumb.style.setProperty("--y", y.toFixed(1) + "px");
        scrollThumb.style.pointerEvents = "auto";
    }

    function showScrollThumb() {
        paintScrollThumb();
        scrollThumb.classList.add("visible");
        window.clearTimeout(scrollHideTimer);
        scrollHideTimer = window.setTimeout(function () {
            // Stays up while it is hovered or dragged.
            if (!scrollThumb.matches(":hover, :active")) {
                scrollThumb.classList.remove("visible");
            }
        }, 900);
    }

    window.addEventListener("scroll", showScrollThumb, { passive: true });
    window.addEventListener("resize", paintScrollThumb);
    window.addEventListener("pointermove", function (e) {
        if (e.clientX > window.innerWidth - 48) showScrollThumb();
    }, { passive: true });

    var scrollDragging = false;
    var scrollGrab = 0;

    scrollThumb.addEventListener("pointerdown", function (e) {
        scrollDragging = true;
        scrollGrab = e.clientY - scrollThumb.getBoundingClientRect().top;
        scrollThumb.classList.add("dragging");
        scrollThumb.setPointerCapture(e.pointerId);
        e.preventDefault();
    });

    scrollThumb.addEventListener("pointermove", function (e) {
        if (!scrollDragging) return;
        var m = scrollMetrics();
        var travel = m.track - scrollThumb.offsetHeight;
        if (travel <= 0 || m.scrollable <= 0) return;
        var y = Math.min(travel, Math.max(0, e.clientY - scrollGrab));
        window.scrollTo(0, (y / travel) * m.scrollable);
    });

    ["pointerup", "pointercancel"].forEach(function (type) {
        scrollThumb.addEventListener(type, function () {
            scrollDragging = false;
            scrollThumb.classList.remove("dragging");
        });
    });

    showScrollThumb();

    if (!token) {
        showSessionScreen("");
        return;
    }

    function formatSize(bytes) {
        var units = LANG === "fr" ? ["o", "Ko", "Mo", "Go"] : ["B", "KB", "MB", "GB"];
        if (bytes < 1024) return bytes + " " + units[0];
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " " + units[1];
        if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " " + units[2];
        return (bytes / (1024 * 1024 * 1024)).toFixed(2) + " " + units[3];
    }

    function formatSpeed(bytesPerSec) {
        if (!bytesPerSec) return "";
        return formatSize(bytesPerSec) + "/s";
    }

    function formatEta(seconds) {
        if (!seconds && seconds !== 0) return "";
        if (seconds < 60) return seconds + "s";
        var m = Math.floor(seconds / 60);
        var s = seconds % 60;
        return m + "min " + s + "s";
    }

    // --- EFFECTS ----------------------------------------------------
    // Pointer-driven bits of the motion layer (the spring tab
    // indicator). Everything else lives in the CSS. Nothing here runs
    // when the OS asks for reduced motion.
    var reducedMotion = !!(window.matchMedia &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches);

    // --- Spring-driven indicator under the active tab.
    var tabIndicator = document.getElementById("tab-indicator");
    var tabsWrap = document.getElementById("tabs");
    var indicator = { x: 0, w: 0, vx: 0, vw: 0, tx: 0, tw: 0, running: false };

    function indicatorTarget() {
        var active = document.querySelector(".tab.active");
        if (!active || !tabsWrap) return;
        // Offset by the wrapper border: the indicator lives inside the
        // padding box, the tabs are laid out from it too.
        var border = tabsWrap.clientLeft;
        indicator.tx = active.offsetLeft - border;
        indicator.tw = active.offsetWidth;
    }

    function indicatorPaint() {
        tabIndicator.style.width = indicator.w + "px";
        tabIndicator.style.transform = "translateX(" + indicator.x + "px)";
    }

    function indicatorTick() {
        var stiff = 210;
        var damp = 17;
        var dt = 1 / 60;

        indicator.vx += (indicator.tx - indicator.x) * stiff * dt;
        indicator.vx -= indicator.vx * damp * dt;
        indicator.x += indicator.vx * dt;

        indicator.vw += (indicator.tw - indicator.w) * stiff * dt;
        indicator.vw -= indicator.vw * damp * dt;
        indicator.w += indicator.vw * dt;

        var done = Math.abs(indicator.tx - indicator.x) < 0.2 &&
            Math.abs(indicator.vx) < 0.4 &&
            Math.abs(indicator.tw - indicator.w) < 0.2 &&
            Math.abs(indicator.vw) < 0.4;
        if (done) {
            indicator.x = indicator.tx;
            indicator.w = indicator.tw;
            indicator.vx = indicator.vw = 0;
            indicatorPaint();
            indicator.running = false;
            return;
        }
        indicatorPaint();
        requestAnimationFrame(indicatorTick);
    }

    function moveTabIndicator(animate) {
        if (!tabIndicator) return;
        var prevTx = indicator.tx;
        var prevTw = indicator.tw;
        indicatorTarget();
        if (!animate || reducedMotion) {
            indicator.x = indicator.tx;
            indicator.w = indicator.tw;
            indicator.vx = indicator.vw = 0;
            indicatorPaint();
            return;
        }
        // Coming back to where we already are: nothing to spring.
        if (prevTx === indicator.tx && prevTw === indicator.tw) return;
        if (!indicator.running) {
            indicator.running = true;
            requestAnimationFrame(indicatorTick);
        }
    }

    if (tabIndicator) {
        moveTabIndicator(false);
        window.addEventListener("resize", function () {
            moveTabIndicator(false);
        });
        // Fonts and the theme switch can change widths after load.
        window.addEventListener("load", function () {
            moveTabIndicator(false);
        });
    }

    // --- TABS ---
    var tabs = document.querySelectorAll(".tab");
    var tabSend = document.getElementById("tab-send");
    var tabReceive = document.getElementById("tab-receive");

    tabs.forEach(function (tab) {
        tab.addEventListener("click", function () {
            tabs.forEach(function (t2) { t2.classList.remove("active"); });
            tab.classList.add("active");
            moveTabIndicator(true);
            if (tab.dataset.tab === "send") {
                tabSend.style.display = "";
                tabReceive.style.display = "none";
            } else {
                tabSend.style.display = "none";
                tabReceive.style.display = "";
                loadFiles();
            }
            refreshQuota();
        });
    });

    // --- QUOTA ---
    var quotaBar = document.getElementById("quota-bar");
    var quotaText = document.getElementById("quota-text");
    var quotaTrack = document.getElementById("quota-track");
    var quotaFill = document.getElementById("quota-fill");

    function formatQuota(bytes) {
        var fr = LANG === "fr";
        var value, unit;
        if (bytes >= 1024 * 1024 * 1024) {
            value = (bytes / (1024 * 1024 * 1024)).toFixed(3);
            unit = fr ? " Go" : " GB";
        } else if (bytes >= 1024 * 1024) {
            value = (bytes / (1024 * 1024)).toFixed(1);
            unit = fr ? " Mo" : " MB";
        } else if (bytes >= 1024) {
            value = (bytes / 1024).toFixed(1);
            unit = fr ? " Ko" : " KB";
        } else {
            return bytes + (fr ? " o" : " B");
        }
        return parseFloat(value).toString().replace(".", fr ? "," : ".") + unit;
    }

    function renderQuota(usage, limit) {
        quotaBar.style.display = "block";
        quotaText.className = "quota-text";
        if (limit > 0) {
            quotaText.textContent = formatQuota(usage) + " / " + formatQuota(limit);
            quotaText.classList.add(usage >= limit ? "full" : "ok");
            // The fill eases to its new value (see .quota-fill in the
            // CSS); a first paint at 0 keeps it from jumping.
            quotaTrack.style.display = "";
            quotaFill.classList.remove("indeterminate");
            quotaFill.classList.toggle("full", usage >= limit);
            quotaFill.style.width =
                Math.min(100, (usage / limit) * 100).toFixed(1) + "%";
        } else {
            quotaText.textContent = t("quota.unlimited", formatQuota(usage));
            // No percentage to show: the fill sweeps instead, so the
            // panel never looks unfinished.
            quotaTrack.style.display = "";
            quotaFill.style.width = "";
            quotaFill.classList.add("indeterminate");
            quotaFill.classList.remove("full");
        }
    }

    // Polling: one request in flight at a time, a deadline, and a visible
    // verdict. Silence is what made a stalled server look like a frozen,
    // black page.
    var quotaBusy = false;
    var quotaFailures = 0;

    function refreshQuota() {
        if (appEl.style.display === "none") return;
        if (quotaBusy) return;
        quotaBusy = true;

        fetchWithTimeout("/api/quota?token=" + encodeURIComponent(token), null, 8000)
            .then(function (r) {
                if (r.status === 401 || r.status === 403) {
                    endSession(t("session.expired"));
                    return null;
                }
                if (!r.ok) throw new Error("http " + r.status);
                return r.json();
            })
            .then(function (data) {
                if (!data || typeof data.usage_bytes !== "number") return;
                quotaFailures = 0;
                renderQuota(data.usage_bytes, data.limit_bytes || 0);
            })
            .catch(function () {
                quotaFailures++;
                if (quotaFailures >= 3) {
                    quotaBar.style.display = "block";
                    quotaText.className = "quota-text offline";
                    quotaText.textContent = t("quota.offline");
                    quotaTrack.style.display = "none";
                }
            })
            .finally(function () {
                quotaBusy = false;
            });
    }

    refreshQuota();
    setInterval(refreshQuota, 5000);

    // --- UPLOAD ---
    var dropZone = document.getElementById("drop-zone");
    var fileInput = document.getElementById("file-input");
    var folderInput = document.getElementById("folder-input");
    var btnChooseFolder = document.getElementById("btn-choose-folder");
    var transferInfo = document.getElementById("transfer-info");
    var successMsg = document.getElementById("success-msg");
    var errorMsg = document.getElementById("error-msg");

    var filenameEl = document.getElementById("filename");
    var filesizeEl = document.getElementById("filesize");
    var queueCount = document.getElementById("queue-count");
    var progressBar = document.getElementById("progress-bar");
    var progressText = document.getElementById("progress-text");
    var btnCancel = document.getElementById("btn-cancel");
    var btnNew = document.getElementById("btn-new");
    var btnRetry = document.getElementById("btn-retry");
    var successFilename = document.getElementById("success-filename");
    var successSize = document.getElementById("success-size");
    var successHash = document.getElementById("success-hash");
    var errorDetail = document.getElementById("error-detail");

    var currentXhr = null;

    // --- Send queue: many files (and zipped folders) travel one after
    // the other; the badge counts them (2 / 5) while they run, and the
    // success screen sums the batch up when the last one lands.
    var sendQueue = [];
    var queueTotal = 0;
    var queueBytes = 0;
    var queueDone = 0;
    var prepareEpoch = 0;   // bumped on cancel: a pending zip must not
                            // start uploads after the user gave up

    function updateQueueBadge() {
        if (queueTotal > 1) {
            queueCount.textContent = (queueDone + 1) + " / " + queueTotal;
            queueCount.style.display = "";
        } else {
            queueCount.style.display = "none";
        }
    }

    function finishQueue() {
        sendQueue = [];
        queueTotal = 0;
        queueCount.style.display = "none";
        refreshQuota();
    }

    function enqueueFiles(files) {
        if (!files || !files.length) {
            showSendView("drop");
            return;
        }
        sendQueue = files.slice();
        queueTotal = files.length;
        queueBytes = 0;
        files.forEach(function (f) { queueBytes += f.size || 0; });
        queueDone = 0;
        updateQueueBadge();
        pumpQueue();
    }

    function pumpQueue() {
        if (!sendQueue.length) {
            finishQueue();
            return;
        }
        updateQueueBadge();
        uploadFile(sendQueue.shift());
    }

    function showSendView(view) {
        transferInfo.style.display = "none";
        successMsg.style.display = "none";
        errorMsg.style.display = "none";

        if (view === "drop") {
            dropZone.style.display = "";
        } else if (view === "transfer") {
            dropZone.style.display = "none";
            transferInfo.style.display = "";
        } else if (view === "success") {
            dropZone.style.display = "none";
            successMsg.style.display = "";
        } else if (view === "error") {
            dropZone.style.display = "none";
            errorMsg.style.display = "";
        }
    }

    function uploadFile(file) {
        filenameEl.textContent = file.name;
        filesizeEl.textContent = formatSize(file.size);
        progressBar.style.width = "0%";
        progressText.textContent = "0%";
        showSendView("transfer");

        var formData = new FormData();
        formData.append("file", file);

        var xhr = new XMLHttpRequest();
        currentXhr = xhr;
        var uploadStart = performance.now();

        xhr.upload.addEventListener("progress", function (e) {
            if (e.lengthComputable) {
                var pct = Math.round((e.loaded / e.total) * 100);
                progressBar.style.width = pct + "%";
                var txt = pct + "%";
                var speed = formatSpeed(e.loaded / ((performance.now() - uploadStart) / 1000));
                var remaining = (e.total - e.loaded) / (e.loaded / ((performance.now() - uploadStart) / 1000));
                if (speed) txt += " - " + speed;
                if (remaining > 0 && remaining < 86400) txt += " - " + formatEta(Math.round(remaining));
                progressText.textContent = txt;
            }
        });

        xhr.addEventListener("load", function () {
            currentXhr = null;
            if (xhr.status === 401 || xhr.status === 403) {
                sendQueue = [];
                endSession(t("session.expired"));
                return;
            }
            try {
                var resp = JSON.parse(xhr.responseText);
                if (xhr.status === 200 && resp.success) {
                    queueDone++;
                    if (sendQueue.length) {
                        pumpQueue();    // next file, badge follows along
                        return;
                    }
                    showBatchSuccess(resp);
                    finishQueue();
                    return;
                }
                errorDetail.textContent = resp.error || t("upload.serverError", xhr.status);
            } catch (err) {
                errorDetail.textContent = t("upload.serverError", xhr.status);
            }
            sendQueue = [];
            finishQueue();
            showSendView("error");
        });

        xhr.addEventListener("error", function () {
            currentXhr = null;
            sendQueue = [];
            finishQueue();
            errorDetail.textContent = t("upload.unreachable");
            showSendView("error");
        });

        xhr.open("POST", "/api/upload?token=" + encodeURIComponent(token));
        xhr.send(formData);
    }

    // One file keeps its detailed screen; a batch reports the count and
    // the total instead of only the last file's numbers.
    function showBatchSuccess(resp) {
        if (queueTotal > 1) {
            successFilename.textContent = t("success.multiple", queueTotal);
            successSize.textContent = formatSize(queueBytes);
            successHash.style.display = "none";
        } else {
            successFilename.textContent = resp.filename;
            successSize.textContent = formatSize(resp.size);
            if (resp.sha256) {
                successHash.textContent = "SHA-256: " + resp.sha256;
                successHash.style.display = "";
            } else {
                successHash.style.display = "none";
            }
        }
        showSendView("success");
    }

    // --- Folder support: a dropped or picked folder is zipped here, in
    // the browser - the PC's share folder only ever receives a plain
    // .zip. Entry walking is async and batched: readEntries hands out
    // chunks, so it loops until a chunk comes back empty.
    function readAllEntries(reader) {
        return new Promise(function (resolve, reject) {
            var all = [];
            (function loop() {
                reader.readEntries(function (batch) {
                    if (!batch.length) { resolve(all); return; }
                    all = all.concat(Array.prototype.slice.call(batch));
                    loop();
                }, reject);
            })();
        });
    }

    function collectFolderFiles(entry, prefix) {
        if (entry.isFile) {
            return new Promise(function (resolve, reject) {
                entry.file(function (f) {
                    resolve([{ name: prefix + entry.name, file: f }]);
                }, reject);
            });
        }
        if (!entry.isDirectory) return Promise.resolve([]);
        return readAllEntries(entry.createReader()).then(function (children) {
            var chain = Promise.resolve([]);
            children.forEach(function (child) {
                chain = chain.then(function (acc) {
                    return collectFolderFiles(child, prefix + entry.name + "/")
                        .then(function (more) { return acc.concat(more); });
                });
            });
            return chain;
        });
    }

    function zipFolder(name, entries) {
        return OpenDropZip.buildZip(entries).then(function (blob) {
            return new File([blob], name + ".zip", { type: "application/zip" });
        });
    }

    function prepareDropped(dataTransfer) {
        var items = dataTransfer && dataTransfer.items ?
            Array.prototype.slice.call(dataTransfer.items) : [];
        var entries = [];
        for (var i = 0; i < items.length; i++) {
            if (items[i].kind !== "file") continue;
            var entry = items[i].webkitGetAsEntry ? items[i].webkitGetAsEntry() : null;
            if (entry) entries.push(entry);
        }
        if (!entries.length) {
            // No entry API, or a plain file drop: the files go as they are.
            var plain = dataTransfer && dataTransfer.files ?
                Array.prototype.slice.call(dataTransfer.files) : [];
            return Promise.resolve(plain);
        }
        var chain = Promise.resolve([]);
        entries.forEach(function (entry) {
            chain = chain.then(function (acc) {
                if (entry.isFile) {
                    return new Promise(function (resolve, reject) {
                        entry.file(function (f) { resolve(acc.concat(f)); }, reject);
                    });
                }
                return collectFolderFiles(entry, "").then(function (found) {
                    if (!found.length) return acc;
                    return zipFolder(entry.name, found).then(function (zip) {
                        return acc.concat(zip);
                    });
                });
            });
        });
        return chain;
    }

    function preparePickedFolders(fileListIn) {
        // <input webkitdirectory>: every file carries webkitRelativePath,
        // grouped per top-level folder and zipped as one.
        var files = Array.prototype.slice.call(fileListIn || []);
        var groups = {};
        var order = [];
        files.forEach(function (f) {
            var rel = f.webkitRelativePath || f.name;
            var slash = rel.indexOf("/");
            var top = slash >= 0 ? rel.slice(0, slash) : f.name;
            if (!groups[top]) { groups[top] = []; order.push(top); }
            groups[top].push({ name: slash >= 0 ? rel.slice(slash + 1) : f.name, file: f });
        });
        var chain = Promise.resolve([]);
        order.forEach(function (top) {
            chain = chain.then(function (acc) {
                return zipFolder(top, groups[top]).then(function (zip) {
                    return acc.concat(zip);
                });
            });
        });
        return chain;
    }

    function startPreparing(label) {
        showSendView("transfer");
        filenameEl.textContent = label;
        filesizeEl.textContent = "";
        progressBar.style.width = "0%";
        progressText.textContent = t("send.preparing");
    }

    function prepareThenSend(promise, label) {
        var epoch = ++prepareEpoch;
        startPreparing(label);
        promise.then(function (files) {
            if (epoch !== prepareEpoch) return;    // cancelled meanwhile
            enqueueFiles(files);
        }).catch(function () {
            if (epoch !== prepareEpoch) return;
            finishQueue();
            errorDetail.textContent = t("send.preparingError");
            showSendView("error");
        });
    }

    dropZone.addEventListener("click", function () {
        fileInput.click();
    });

    if (btnChooseFolder) {
        btnChooseFolder.addEventListener("click", function (e) {
            // The drop zone would open the file picker too.
            e.stopPropagation();
            folderInput.click();
        });
    }

    fileInput.addEventListener("change", function () {
        if (fileInput.files.length > 0) {
            enqueueFiles(Array.prototype.slice.call(fileInput.files));
        }
        fileInput.value = "";
    });

    if (folderInput) {
        folderInput.addEventListener("change", function () {
            if (folderInput.files.length > 0) {
                var rel = folderInput.files[0].webkitRelativePath || "";
                prepareThenSend(preparePickedFolders(folderInput.files),
                    rel ? rel.split("/")[0] : t("drop.chooseFolder"));
            }
            folderInput.value = "";
        });
    }

    dropZone.addEventListener("dragover", function (e) {
        e.preventDefault();
        dropZone.classList.add("dragover");
    });

    dropZone.addEventListener("dragleave", function () {
        dropZone.classList.remove("dragover");
    });

    dropZone.addEventListener("drop", function (e) {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        var dt = e.dataTransfer;
        var label = (dt && dt.files && dt.files.length) ? dt.files[0].name : "...";
        prepareThenSend(prepareDropped(dt), label);
    });

    btnCancel.addEventListener("click", function () {
        prepareEpoch++;     // a zip still being built must not start
        if (currentXhr) {
            currentXhr.abort();
            currentXhr = null;
        }
        finishQueue();
        showSendView("drop");
        fileInput.value = "";
        if (folderInput) folderInput.value = "";
    });

    btnNew.addEventListener("click", function () {
        showSendView("drop");
        fileInput.value = "";
        if (folderInput) folderInput.value = "";
    });

    btnRetry.addEventListener("click", function () {
        showSendView("drop");
        fileInput.value = "";
        if (folderInput) folderInput.value = "";
    });

    // --- DOWNLOAD ---
    // The list now carries a small workspace on top of the server's
    // files: a search box, a 1/2/4-per-row view switch, selection
    // checkboxes with a Download (n) button, and web-only folders to
    // sort files into (they live in localStorage - the PC's share
    // folder is never touched, and a file moved here is still the same
    // file on disk).
    var fileList = document.getElementById("file-list");
    var emptyMsg = document.getElementById("empty-msg");
    var emptyText = emptyMsg.querySelector("p");
    var emptyHint = emptyMsg.querySelector(".empty-hint");
    var btnRefresh = document.getElementById("btn-refresh");
    var searchInput = document.getElementById("search-input");
    var viewSwitch = document.getElementById("view-switch");
    var selectAllChk = document.getElementById("select-all");
    var btnDlSel = document.getElementById("btn-dl-sel");
    var dlSelCount = document.getElementById("dl-sel-count");
    var moveSelect = document.getElementById("move-select");
    var crumbRoot = document.getElementById("crumb-root");
    var crumbSep = document.getElementById("crumb-sep");
    var crumbFolder = document.getElementById("crumb-folder");
    var btnNewFolder = document.getElementById("btn-newfolder");
    var dlStatus = document.getElementById("dl-status");

    var serverFiles = [];
    var searchQuery = "";
    var selection = {};         // file name -> true

    // One level of folders; a file sits at Home or inside exactly one
    // folder, keyed by its server name. Placements of files the server
    // no longer lists are pruned on each refresh.
    var WEBFS_KEY = "opendrop.webfs.v1";
    var VIEW_KEY = "opendrop.webview";
    var webfs = { folders: {}, placements: {} };
    var currentFolder = null;   // folder id, or null for Home
    var viewMode = "list";

    function loadWebfs() {
        try {
            var parsed = JSON.parse(storeRead(WEBFS_KEY) || "{}");
            if (parsed && typeof parsed === "object") {
                if (parsed.folders && typeof parsed.folders === "object") {
                    webfs.folders = parsed.folders;
                }
                if (parsed.placements && typeof parsed.placements === "object") {
                    webfs.placements = parsed.placements;
                }
            }
        } catch (e) { /* corrupted: start from scratch */ }
        var stored = storeRead(VIEW_KEY);
        if (stored === "grid2" || stored === "grid4") viewMode = stored;
    }

    function saveWebfs() {
        storeWrite(WEBFS_KEY, JSON.stringify(webfs));
    }

    function pruneWebfs() {
        var known = {};
        serverFiles.forEach(function (f) { known[f.name] = true; });
        var changed = false;
        Object.keys(webfs.placements).forEach(function (name) {
            if (!known[name]) { delete webfs.placements[name]; changed = true; }
        });
        if (changed) saveWebfs();
    }

    function folderList() {
        return Object.keys(webfs.folders).map(function (id) {
            return { id: id, name: webfs.folders[id] };
        }).sort(function (a, b) {
            return a.name.localeCompare(b.name);
        });
    }

    function filesIn(folderId) {
        return serverFiles.filter(function (f) {
            return (webfs.placements[f.name] || null) === (folderId || null);
        });
    }

    function uniqueFolderName(base, exceptId) {
        var taken = {};
        folderList().forEach(function (f) {
            if (f.id !== exceptId) taken[f.name] = true;
        });
        if (!taken[base]) return base;
        var n = 2;
        while (taken[base + " " + n]) n++;
        return base + " " + n;
    }

    function newFolderId() {
        return "f" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
    }

    // Renaming without prompt(): one input takes the label's place, Enter
    // or a tap outside saves, Escape restores. prompt() is blocked in
    // some embedded views and reads badly on phones.
    function editNameInline(host, current, commit) {
        var input = document.createElement("input");
        input.type = "text";
        input.className = "folder-edit";
        input.value = current || "";
        input.maxLength = 40;
        input.draggable = false;
        host.textContent = "";
        host.appendChild(input);
        input.focus();
        input.select();
        var done = false;
        var finish = function (save) {
            if (done) return;
            done = true;
            var value = input.value.trim();
            if (save && value) commit(value);
            else renderList();
        };
        input.addEventListener("keydown", function (e) {
            if (e.key === "Enter") finish(true);
            else if (e.key === "Escape") finish(false);
            e.stopPropagation();
        });
        input.addEventListener("blur", function () { finish(true); });
    }

    function startRename(card) {
        var id = card.dataset.id;
        var nameEl = card.querySelector(".folder-name");
        editNameInline(nameEl, webfs.folders[id], function (value) {
            webfs.folders[id] = uniqueFolderName(value, id);
            saveWebfs();
            renderList();
        });
    }

    // Deleting a folder never touches a real file (they all go back
    // Home), but it still dissolves some organizing work - so the cross
    // arms first and deletes on the second tap. Chosen over
    // window.confirm(): a browser told to stop asking silently answers
    // "no" and the button would do nothing at all.
    var armedDelete = null;     // { id, btn, timer }

    function disarmDelete() {
        if (!armedDelete) return;
        window.clearTimeout(armedDelete.timer);
        if (armedDelete.btn) {
            armedDelete.btn.classList.remove("armed");
            armedDelete.btn.textContent = "\u2715";
        }
        armedDelete = null;
    }

    function armDelete(card) {
        var btn = card.querySelector('.folder-action[data-act="delete"]');
        if (!btn) return;
        if (armedDelete && armedDelete.btn === btn) {
            disarmDelete();
            deleteFolderNow(card.dataset.id);
            return;
        }
        disarmDelete();
        btn.classList.add("armed");
        btn.textContent = "\u2713";     // tick: "tap again to confirm"
        armedDelete = {
            id: card.dataset.id,
            btn: btn,
            timer: window.setTimeout(disarmDelete, 3500)
        };
    }

    function deleteFolderNow(id) {
        disarmDelete();
        delete webfs.folders[id];
        Object.keys(webfs.placements).forEach(function (name) {
            if (webfs.placements[name] === id) delete webfs.placements[name];
        });
        if (currentFolder === id) currentFolder = null;
        saveWebfs();
        renderList();
    }

    function downloadUrl(name) {
        return "/api/download/" + encodeURIComponent(name) +
            "?token=" + encodeURIComponent(token);
    }

    function buildFolderCard(folder, index) {
        var card = document.createElement("div");
        card.className = "folder-card";
        card.dataset.id = folder.id;
        card.dataset.drop = "folder";
        card.style.setProperty("--i", index);

        var glyph = document.createElement("span");
        glyph.className = "folder-icon";
        glyph.textContent = "\ud83d\udcc1";   // folder

        var name = document.createElement("p");
        name.className = "folder-name";
        name.textContent = folder.name;

        var count = document.createElement("span");
        count.className = "folder-count";
        count.textContent = String(filesIn(folder.id).length);

        var rename = document.createElement("button");
        rename.type = "button";
        rename.className = "folder-action";
        rename.dataset.act = "rename";
        rename.textContent = "\u270f";        // pencil
        rename.setAttribute("aria-label", t("files.rename"));

        var del = document.createElement("button");
        del.type = "button";
        del.className = "folder-action danger";
        del.dataset.act = "delete";
        del.textContent = "\u2715";           // cross
        del.setAttribute("aria-label", t("files.deleteFolder"));

        card.appendChild(glyph);
        card.appendChild(name);
        card.appendChild(count);
        card.appendChild(rename);
        card.appendChild(del);
        return card;
    }

    function buildBackCard(index) {
        var card = document.createElement("div");
        card.className = "back-card";
        card.dataset.drop = "root";
        card.style.setProperty("--i", index);

        var glyph = document.createElement("span");
        glyph.className = "folder-icon";
        glyph.textContent = "\u2b05";         // left arrow

        var name = document.createElement("span");
        name.className = "folder-name";
        name.textContent = t("files.root");

        card.appendChild(glyph);
        card.appendChild(name);
        return card;
    }

    function buildFileCard(file, index) {
        var card = document.createElement("div");
        card.className = "file-card";
        card.dataset.name = file.name;
        card.draggable = true;
        card.style.setProperty("--i", index);

        var check = document.createElement("label");
        check.className = "file-check";
        var box = document.createElement("input");
        box.type = "checkbox";
        box.checked = !!selection[file.name];
        check.appendChild(box);

        var info = document.createElement("div");
        info.className = "file-info";

        var name = document.createElement("p");
        name.className = "file-name";
        name.textContent = file.name;

        var size = document.createElement("p");
        size.className = "file-size";
        size.textContent = formatSize(file.size);

        info.appendChild(name);
        info.appendChild(size);

        var btn = document.createElement("a");
        btn.className = "btn-download";
        btn.textContent = t("files.download");
        btn.href = downloadUrl(file.name);
        // The row is what drags; the link only downloads.
        btn.draggable = false;

        card.appendChild(check);
        card.appendChild(info);
        card.appendChild(btn);
        return card;
    }

    function visibleNames() {
        var query = searchQuery.toLowerCase();
        return filesIn(currentFolder).filter(function (f) {
            return !query || f.name.toLowerCase().indexOf(query) >= 0;
        }).map(function (f) { return f.name; });
    }

    function renderCrumbs() {
        if (currentFolder) {
            crumbSep.style.display = "";
            crumbFolder.style.display = "";
            crumbFolder.textContent = webfs.folders[currentFolder] || "";
        } else {
            crumbSep.style.display = "none";
            crumbFolder.style.display = "none";
            crumbFolder.textContent = "";
        }
    }

    function renderMoveOptions() {
        while (moveSelect.options.length > 2) moveSelect.remove(2);
        folderList().forEach(function (folder) {
            if (folder.id === currentFolder) return;
            var option = document.createElement("option");
            option.value = folder.id;
            option.textContent = folder.name;
            moveSelect.appendChild(option);
        });
    }

    function renderSelectionUI() {
        var n = Object.keys(selection).length;
        dlSelCount.textContent = String(n);
        btnDlSel.disabled = n === 0;
        moveSelect.disabled = n === 0;
        var visible = visibleNames();
        var all = visible.length > 0 && visible.every(function (name) {
            return selection[name];
        });
        selectAllChk.checked = all;
        selectAllChk.disabled = visible.length === 0;
    }

    function syncVisibleChecks() {
        var boxes = fileList.querySelectorAll(".file-card .file-check input");
        boxes.forEach(function (box) {
            var card = box.closest(".file-card");
            box.checked = !!selection[card.dataset.name];
        });
    }

    function renderList() {
        var query = searchQuery.toLowerCase();
        var folders = folderList().filter(function (f) {
            return !query || f.name.toLowerCase().indexOf(query) >= 0;
        });
        var files = filesIn(currentFolder).filter(function (f) {
            return !query || f.name.toLowerCase().indexOf(query) >= 0;
        });

        fileList.className = "file-list" + (viewMode === "list" ? "" : " " + viewMode);
        fileList.innerHTML = "";
        var index = 0;
        if (currentFolder) fileList.appendChild(buildBackCard(index++));
        folders.forEach(function (folder) {
            fileList.appendChild(buildFolderCard(folder, index++));
        });
        files.forEach(function (file) {
            fileList.appendChild(buildFileCard(file, index++));
        });

        var nothing = !folders.length && !files.length;
        if (nothing) {
            emptyText.textContent = query ? t("files.noMatch") :
                (currentFolder ? t("files.emptyFolder") : t("files.empty"));
            emptyHint.style.display = (query || currentFolder) ? "none" : "";
        }
        emptyMsg.style.display = nothing ? "" : "none";
        fileList.style.display = nothing ? "none" : "";

        renderCrumbs();
        renderMoveOptions();
        renderSelectionUI();
    }

    function moveSelectionTo(folderId) {
        Object.keys(selection).forEach(function (name) {
            if (folderId) webfs.placements[name] = folderId;
            else delete webfs.placements[name];
        });
        selection = {};
        saveWebfs();
        renderList();
    }

    function flashStatus(message) {
        dlStatus.textContent = message;
        window.clearTimeout(flashStatus.timer);
        flashStatus.timer = window.setTimeout(function () {
            dlStatus.textContent = "";
        }, 3500);
    }

    function saveBlob(blob, filename) {
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.setTimeout(function () { URL.revokeObjectURL(url); }, 10000);
    }

    function downloadSelected() {
        var names = Object.keys(selection);
        if (!names.length) return;
        if (names.length === 1) {
            var a = document.createElement("a");
            a.href = downloadUrl(names[0]);
            a.click();
            return;
        }
        // Several files: fetched one by one, then handed over as a
        // single zip built on this device.
        var total = names.length;
        var done = 0;
        btnDlSel.disabled = true;
        dlSelCount.textContent = "0/" + total;
        var chain = Promise.resolve([]);
        names.forEach(function (name) {
            chain = chain.then(function (acc) {
                return fetchWithTimeout(downloadUrl(name), null, 60000)
                    .then(function (r) {
                        if (!r.ok) throw new Error("http " + r.status);
                        return r.blob();
                    })
                    .then(function (blob) {
                        done++;
                        dlSelCount.textContent = done + "/" + total;
                        return acc.concat([{ name: name, file: blob }]);
                    });
            });
        });
        chain.then(function (entries) {
            return OpenDropZip.buildZip(entries);
        }).then(function (zipBlob) {
            saveBlob(zipBlob, "OpenDrop-" + total + "-files.zip");
        }).catch(function () {
            flashStatus(t("files.downloadError"));
        }).finally(function () {
            renderSelectionUI();
        });
    }

    loadWebfs();

    searchInput.addEventListener("input", function () {
        searchQuery = searchInput.value.trim();
        renderList();
    });

    viewSwitch.addEventListener("click", function (e) {
        var btn = e.target.closest(".view-btn");
        if (!btn) return;
        viewMode = btn.dataset.view;
        storeWrite(VIEW_KEY, viewMode);
        viewSwitch.querySelectorAll(".view-btn").forEach(function (b) {
            b.classList.toggle("active", b === btn);
        });
        renderList();
    });

    viewSwitch.querySelectorAll(".view-btn").forEach(function (b) {
        b.classList.toggle("active", b.dataset.view === viewMode);
    });

    selectAllChk.addEventListener("change", function () {
        var names = visibleNames();
        if (selectAllChk.checked) {
            names.forEach(function (name) { selection[name] = true; });
        } else {
            names.forEach(function (name) { delete selection[name]; });
        }
        syncVisibleChecks();
        renderSelectionUI();
    });

    btnDlSel.addEventListener("click", downloadSelected);

    moveSelect.addEventListener("change", function () {
        var value = moveSelect.value;
        moveSelect.value = "";
        if (!value) return;
        moveSelectionTo(value === "__root__" ? null : value);
    });

    crumbRoot.addEventListener("click", function () {
        if (!currentFolder) return;
        currentFolder = null;
        selection = {};
        renderList();
    });

    btnNewFolder.addEventListener("click", function () {
        if (currentFolder) return;   // folders live at Home
        var id = newFolderId();
        webfs.folders[id] = t("files.folderDefault");
        saveWebfs();
        renderList();
        // The new folder opens straight into its inline rename.
        var card = fileList.querySelector('.folder-card[data-id="' + id + '"]');
        if (card) startRename(card);
    });

    fileList.addEventListener("click", function (e) {
        var action = e.target.closest(".folder-action");
        if (!(action && action.dataset.act === "delete")) {
            // Any other click (here or elsewhere in the list) drops the
            // armed delete back to its resting cross.
            disarmDelete();
        }
        if (action) {
            var actionCard = action.closest(".folder-card");
            if (!actionCard) return;
            if (action.dataset.act === "rename") startRename(actionCard);
            else if (action.dataset.act === "delete") armDelete(actionCard);
            return;
        }
        var folderCard = e.target.closest(".folder-card");
        if (folderCard && !e.target.closest(".folder-edit")) {
            currentFolder = folderCard.dataset.id;
            selection = {};
            searchQuery = "";
            searchInput.value = "";
            renderList();
            return;
        }
        if (e.target.closest(".back-card")) {
            currentFolder = null;
            selection = {};
            renderList();
        }
    });

    fileList.addEventListener("change", function (e) {
        var box = e.target.closest(".file-check input");
        if (!box) return;
        var card = box.closest(".file-card");
        if (box.checked) selection[card.dataset.name] = true;
        else delete selection[card.dataset.name];
        renderSelectionUI();
    });

    // Drag files into folders with a pointer; phones use the Move to
    // select instead (HTML5 drag does not exist there).
    fileList.addEventListener("dragstart", function (e) {
        var card = e.target.closest(".file-card");
        if (!card) return;
        var name = card.dataset.name;
        if (!selection[name]) {
            selection = {};
            selection[name] = true;
            syncVisibleChecks();
            renderSelectionUI();
        }
        e.dataTransfer.setData("text/plain", Object.keys(selection).join("\n"));
        e.dataTransfer.effectAllowed = "move";
        card.classList.add("dragging");
    });

    fileList.addEventListener("dragend", function () {
        fileList.querySelectorAll(".dragging, .drop-hover").forEach(function (el) {
            el.classList.remove("dragging", "drop-hover");
        });
    });

    fileList.addEventListener("dragover", function (e) {
        var target = e.target.closest("[data-drop]");
        if (!target) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = "move";
        target.classList.add("drop-hover");
    });

    fileList.addEventListener("dragleave", function (e) {
        var target = e.target.closest("[data-drop]");
        if (target) target.classList.remove("drop-hover");
    });

    fileList.addEventListener("drop", function (e) {
        var target = e.target.closest("[data-drop]");
        if (!target) return;
        e.preventDefault();
        target.classList.remove("drop-hover");
        moveSelectionTo(target.dataset.drop === "root" ? null : target.dataset.id);
    });

    function loadFiles() {
        emptyMsg.style.display = "none";
        // First load: nothing on screen yet, show the placeholder. Later
        // refreshes keep the current rows visible until the answer
        // arrives, so the list never blinks.
        if (!fileList.querySelector(".file-card, .folder-card, .back-card")) {
            fileList.innerHTML = "";
            var loading = document.createElement("p");
            loading.className = "loading";
            loading.textContent = t("files.loading");
            fileList.appendChild(loading);
            fileList.style.display = "";
        }

        fetchWithTimeout("/api/files?token=" + encodeURIComponent(token), null, 20000)
            .then(function (r) {
                if (r.status === 429) {
                    throw new Error("rate limit");
                }
                if (r.status === 401 || r.status === 403) {
                    throw new Error("session");
                }
                if (r.status >= 500) {
                    throw new Error("server");
                }
                return r.json();
            })
            .then(function (data) {
                if (data && data.error) {
                    throw new Error(data.code === 403 ? "session" : "server");
                }
                serverFiles = data.files || [];
                pruneWebfs();
                if (currentFolder && !webfs.folders[currentFolder]) {
                    currentFolder = null;
                }
                Object.keys(selection).forEach(function (name) {
                    var gone = !serverFiles.some(function (f) { return f.name === name; });
                    if (gone) delete selection[name];
                });
                renderList();
            })
            .catch(function (err) {
                fileList.innerHTML = "";
                if (err.message === "session") {
                    endSession(t("session.expired"));
                } else {
                    var msg = document.createElement("p");
                    msg.className = "loading";
                    if (err.message === "rate limit") {
                        msg.textContent = t("files.rateLimited");
                    } else if (err.message === "server") {
                        msg.textContent = t("files.serverError");
                    } else {
                        msg.textContent = t("files.loadError");
                    }
                    fileList.appendChild(msg);
                    fileList.style.display = "";
                }
            });
    }

    btnRefresh.addEventListener("click", function () {
        loadFiles();
    });
})();
