(function () {
    var TOKEN_KEY = "opendrop_token";
    var DEVICE_KEY = "opendrop_device";
    var DID_KEY = "opendrop_did";

    // --- Internationalization ---------------------------------------
    // English is the default (static HTML); French is applied at startup
    // when the server reports "language": "fr" in /api/info.
    var LANG = "en";

    var T = {
        en: {
            "tab.send": "Send",
            "tab.receive": "Download",
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
            "device.paste": "Pair",
            "device.pastePlaceholder": "Paste the device token",
            "device.invalid": "Invalid device token.",
            "device.token": "Device token",
            "device.myIp": "My IP",
            "device.copy": "Copy",
            "device.copied": "Copied!",
            "device.copyFailed": "Copy failed.",
            "device.showInfo": "Share this device's info with the PC",
            "device.dissociate": "Dissociate",
            "device.needPair": "This device is not paired yet. Paste the device token below.",
            "settings.open": "Settings",
            "settings.title": "Settings",
            "settings.close": "Close",
            "settings.device": "Device",
            "settings.appearance": "Appearance",
            "settings.language": "Language",
            "settings.forbidden": "Not allowed for this session. Pair this device first.",
            "pair.title": "Pair this device",
            "pair.hint": "Your PC just opened a pairing window. Paste the device token it displays to register this device (valid for one minute).",
            "pair.submit": "Pair",
            "pair.banner": "Pairing available \u2014 tap to pair",
            "pair.showInfo": "Share this device's info with the PC",
            "appearance.light": "Light",
            "appearance.dark": "Dark",
            "lang.fr": "Fran\u00e7ais",
            "lang.en": "English",
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
            "upload.finalizing": "Finalizing…",
            "drop.chooseFiles": "Choose files",
            "drop.folderHint": "folders arrive zipped",
            "send.preparing": "Preparing...",
            "send.preparingError": "Could not read the folder.",
            "send.optionsTitle": "Before sending",
            "send.zipPassword": "Protect the zips with a password",
            "send.zipPasswordPlaceholder": "Password",
            "send.compression": "Compression",
            "send.modeStandard": "Standard",
            "send.modeFast": "Fast",
            "send.start": "Start",
            "send.zipping": "Compressing\u2026 {0} ({1} / {2})",
            "send.tooBig": "Too big for the space left: {0} to send, {1} available ({2} over).",
            "send.zipFailed": "Could not compress the folder.",
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
            "drop.hint": "ou d\u00e9posez ici",
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
            "device.paste": "Associer",
            "device.pastePlaceholder": "Collez le jeton d'appareil",
            "device.invalid": "Jeton d'appareil invalide.",
            "device.token": "Jeton d'appareil",
            "device.myIp": "Mon IP",
            "device.copy": "Copier",
            "device.copied": "Copi\u00e9 !",
            "device.copyFailed": "La copie a \u00e9chou\u00e9.",
            "device.showInfo": "Partager les informations de cet appareil avec le PC",
            "device.dissociate": "Dissocier",
            "device.needPair": "Cet appareil n'est pas encore associ\u00e9. Collez le jeton d'appareil ci-dessous.",
            "settings.open": "Param\u00e8tres",
            "settings.title": "Param\u00e8tres",
            "settings.close": "Fermer",
            "settings.device": "Appareil",
            "settings.appearance": "Apparence",
            "settings.language": "Langue",
            "settings.forbidden": "Refus\u00e9 pour cette session. Associez d'abord cet appareil.",
            "pair.title": "Associer cet appareil",
            "pair.hint": "Votre PC vient d'ouvrir une fen\u00eatre d'association. Collez le jeton d'appareil qu'il affiche pour enregistrer cet appareil (valable une minute).",
            "pair.submit": "Associer",
            "pair.banner": "Association disponible \u2014 appuyez pour associer",
            "pair.showInfo": "Partager les informations de cet appareil avec le PC",
            "appearance.light": "Clair",
            "appearance.dark": "Sombre",
            "lang.fr": "Fran\u00e7ais",
            "lang.en": "English",
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
            "upload.finalizing": "Finalisation\u2026",
            "drop.chooseFiles": "Choisir des fichiers",
            "drop.folderHint": "les dossiers arrivent compress\u00e9s en zip",
            "send.preparing": "Pr\u00e9paration...",
            "send.preparingError": "Impossible de lire le dossier.",
            "send.optionsTitle": "Avant d'envoyer",
            "send.zipPassword": "Prot\u00e9ger les zip par un mot de passe",
            "send.zipPasswordPlaceholder": "Mot de passe",
            "send.compression": "Compression",
            "send.modeStandard": "Standard",
            "send.modeFast": "Rapide",
            "send.start": "Commencer",
            "send.zipping": "Compression\u2026 {0} ({1} / {2})",
            "send.tooBig": "Trop grand pour l'espace restant : {0} \u00e0 envoyer, {1} disponible(s) ({2} de trop).",
            "send.zipFailed": "Impossible de compresser le dossier.",
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

    // Variadic: t("key", a, b, ...) replaces {0}, {1}, ... in order.
    function t(key) {
        var dict = T[LANG] || T.en;
        var text = dict[key];
        if (text === undefined) text = T.en[key];
        if (text === undefined) text = key;
        for (var i = 1; i < arguments.length; i++) {
            text = text.replace("{" + (i - 1) + "}", arguments[i]);
        }
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
            // Comma-separated pairs: "aria-label:key.one,title:key.two".
            // A single pair (the original form) still works.
            var pairs = attrs[j].getAttribute("data-i18n-attr").split(",");
            for (var k = 0; k < pairs.length; k++) {
                var spec = pairs[k].split(":");
                if (spec.length === 2) attrs[j].setAttribute(spec[0], t(spec[1]));
            }
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
            // Settings overlay (defined below, hoisted): refresh the
            // active light/dark + lang buttons if it is already open.
            syncSettingsChoices();
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

    // --- Device plumbing ---------------------------------------------
    // A paired phone keeps the long-lived device token in localStorage
    // and sends it (plus a stable per-browser id) on every request: the
    // server trusts a registered IP outright and re-registers a healed
    // one, which is how pairing survives restarts and token rotations.

    // One 32-char alnum id per browser, generated once and persisted.
    function getDid() {
        var did = storeRead(DID_KEY);
        if (did) return did;
        var alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
        var out = "";
        var rnd = new Uint8Array(1);
        while (out.length < 32) {
            if (window.crypto && window.crypto.getRandomValues) {
                window.crypto.getRandomValues(rnd);
            } else {
                // Old-browser fallback: not a secret, only an identifier.
                rnd[0] = Math.floor(Math.random() * 256);
            }
            // 62 does not divide 256: drop the tail so every character
            // of the alphabet stays equally likely.
            if (rnd[0] >= 248) continue;
            out += alphabet.charAt(rnd[0] % 62);
        }
        storeWrite(DID_KEY, out);
        return out;
    }

    // Query string for every authenticated request: the session token,
    // the device token when this browser has one (heals/registers the
    // caller's IP), and the stable per-browser id the server stores on
    // the record. `extra` must bring its own leading "&" when present.
    function authQuery(extra) {
        var dev = storeRead(DEVICE_KEY) || "";
        return "token=" + encodeURIComponent(token) +
            (dev ? "&device=" + encodeURIComponent(dev) : "") +
            "&did=" + encodeURIComponent(getDid()) +
            (extra || "");
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

    // --- Pairing by pasting the device token --------------------------
    // The desktop shows its device token (Settings > Devices). Pasting
    // it here registers this IP with the server and hands back a fresh
    // session token, so the page reloads straight into the app - no
    // code, no QR, from then on this IP opens unlocked.
    var pasteInput = document.getElementById("paste-input");
    var btnPaste = document.getElementById("btn-paste");
    var pasteError = document.getElementById("paste-error");

    function showPasteError(message) {
        pasteError.textContent = message;
        pasteError.style.display = message ? "" : "none";
    }

    // `ctx` routes the in-flight button and the error line: the settings
    // overlay passes its own pair (`btn-settings-paste` /
    // `#settings-paste-error`); without it the lock-screen field is used.
    function pairWithToken(value, shareInfo, ctx) {
        var btn = (ctx && ctx.btn) || btnPaste;
        var report = (ctx && ctx.report) || showPasteError;
        var device = (value || "").trim();
        // Obvious garbage never reaches the server: the pair endpoint is
        // rate-limited to 5/min per IP.
        if (!/^[A-Za-z0-9]{32}$/.test(device)) {
            report(t("device.invalid"));
            return;
        }
        report("");
        btn.disabled = true;
        fetchWithTimeout("/api/device/pair?device=" + encodeURIComponent(device) +
            "&did=" + encodeURIComponent(getDid()) +
            "&share_info=" + (shareInfo ? "1" : "0"),
            { method: "POST" }, 10000)
            .then(function (r) {
                return r.json().then(function (data) { return { status: r.status, data: data }; });
            })
            .then(function (res) {
                if (res.status === 200 && res.data.token) {
                    storeToken(res.data.token);
                    if (res.data.device) storeWrite(DEVICE_KEY, res.data.device);
                    location.reload();
                    return;
                }
                btn.disabled = false;
                if (res.status === 429) {
                    report(t("unlock.tooMany"));
                } else {
                    report(t("device.invalid"));
                }
            })
            .catch(function () {
                btn.disabled = false;
                report(t("unlock.offline"));
            });
    }

    btnPaste.addEventListener("click", function () {
        pairWithToken(pasteInput.value, false);
    });
    pasteInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter") pairWithToken(pasteInput.value, false);
    });

    // --- Settings overlay (the gear) ----------------------------------
    // The gear lives inside #app, so the lock/unlock display toggle
    // hides it with the rest of the app. The overlay sits at body level:
    // a self-dissociate leaves it open over the lock screen, where its
    // paste field is how this device pairs again.
    // Opening fires ONE GET /api/device/status - a single render
    // request, never a poll.
    var settingsScreen = document.getElementById("settings-screen");
    var settingsBtn = document.getElementById("settings-btn");
    var settingsError = document.getElementById("settings-error");
    var settingsAssociated = document.getElementById("settings-associated");
    var settingsUnpaired = document.getElementById("settings-unpaired");
    var deviceTokenEl = document.getElementById("device-token");
    var settingsMyIp = document.getElementById("settings-my-ip");
    var btnCopyToken = document.getElementById("btn-copy-token");
    var chkShareInfo = document.getElementById("chk-share-info");
    var btnDissociate = document.getElementById("btn-dissociate");
    var settingsPaste = document.getElementById("settings-paste");
    var btnSettingsPaste = document.getElementById("btn-settings-paste");
    var settingsPasteError = document.getElementById("settings-paste-error");
    var settingsClose = document.getElementById("settings-close");
    var copyTimer = 0;
    var statusEpoch = 0;       // a re-open ignores the previous answer
    var armedDissociate = 0;   // timer id: first tap arms, second acts

    function showSettingsError(message) {
        settingsError.textContent = message;
        settingsError.style.display = message ? "" : "none";
    }

    function showSettingsPasteError(message) {
        settingsPasteError.textContent = message;
        settingsPasteError.style.display = message ? "" : "none";
    }

    // Active state on the theme/language choices. Called on open and
    // from the /api/info handler (hoisted), so a late answer cannot
    // leave stale buttons highlighted behind the overlay.
    function syncSettingsChoices() {
        var light = document.getElementById("set-theme-light");
        var dark = document.getElementById("set-theme-dark");
        if (light) light.classList.toggle("active", serverTheme === "light");
        if (dark) dark.classList.toggle("active", serverTheme === "dark");
        var fr = document.getElementById("set-lang-fr");
        var en = document.getElementById("set-lang-en");
        if (fr) fr.classList.toggle("active", LANG === "fr");
        if (en) en.classList.toggle("active", LANG === "en");
    }

    function disarmDissociate() {
        if (!armedDissociate) return;
        window.clearTimeout(armedDissociate);
        armedDissociate = 0;
        btnDissociate.classList.remove("armed");
        btnDissociate.textContent = t("device.dissociate");
    }

    function renderDeviceStatus(data) {
        var associated = !!(data && data.associated);
        disarmDissociate();
        settingsAssociated.style.display = associated ? "" : "none";
        settingsUnpaired.style.display = associated ? "none" : "";
        if (!associated) return;
        deviceTokenEl.textContent = data.device_token || "";
        settingsMyIp.textContent = data.my_ip || "";
        chkShareInfo.checked = !!data.share_info;
    }

    function openSettings() {
        showSettingsError("");
        showSettingsPasteError("");
        settingsScreen.style.display = "flex";
        syncSettingsChoices();
        var epoch = ++statusEpoch;
        fetchWithTimeout("/api/device/status?" + authQuery(), null, 10000)
            .then(function (r) {
                if (r.status === 401 || r.status === 403) return { forbidden: true };
                if (!r.ok) throw new Error("http " + r.status);
                return r.json();
            })
            .then(function (data) {
                if (epoch !== statusEpoch) return;      // reopened meanwhile
                if (data && data.forbidden) {
                    // Stale session: pasting the device token re-pairs.
                    renderDeviceStatus(null);
                    showSettingsError(t("settings.forbidden"));
                    return;
                }
                renderDeviceStatus(data);
            })
            .catch(function () {
                if (epoch !== statusEpoch) return;
                showSettingsError(t("quota.offline"));
            });
    }

    function closeSettings() {
        statusEpoch++;      // an in-flight answer must not repaint us
        settingsScreen.style.display = "none";
        disarmDissociate();
        showSettingsError("");
    }

    // Every settings POST carries BOTH keys: the server normalizes a
    // missing one to its default, so sending only what changed would
    // silently reset the sibling setting (lang -> en, theme -> dark).
    function postSettings(query, onOk) {
        showSettingsError("");
        fetchWithTimeout("/api/settings?" + query + "&" + authQuery(),
            { method: "POST" }, 10000)
            .then(function (r) {
                return r.json().then(function (data) { return { status: r.status, data: data }; });
            })
            .then(function (res) {
                if (res.status === 200) { onOk(res.data); return; }
                if (res.status === 401 || res.status === 403) {
                    showSettingsError(t("settings.forbidden"));
                } else if (res.status === 429) {
                    showSettingsError(t("unlock.tooMany"));
                } else {
                    showSettingsError(t("files.serverError"));
                }
            })
            .catch(function () {
                showSettingsError(t("quota.offline"));
            });
    }

    // Apparence: live apply - no reload (the local override keys are
    // dropped so the server's new choice is what the page resolves).
    document.getElementById("set-theme-light").addEventListener("click", function () {
        postSettings("lang=" + encodeURIComponent(LANG) + "&theme=light",
            function (data) {
                storeForget(THEME_KEY);
                storeForget(THEME_BASE_KEY);
                serverTheme = (data && data.theme) || "light";
                applyTheme();
                syncSettingsChoices();
            });
    });
    document.getElementById("set-theme-dark").addEventListener("click", function () {
        postSettings("lang=" + encodeURIComponent(LANG) + "&theme=dark",
            function (data) {
                storeForget(THEME_KEY);
                storeForget(THEME_BASE_KEY);
                serverTheme = (data && data.theme) || "dark";
                applyTheme();
                syncSettingsChoices();
            });
    });

    // Langue: the server-side change only shows after a reload, so the
    // page reloads right away and re-reads /api/info.
    document.getElementById("set-lang-fr").addEventListener("click", function () {
        postSettings("lang=fr&theme=" + encodeURIComponent(serverTheme),
            function () { location.reload(); });
    });
    document.getElementById("set-lang-en").addEventListener("click", function () {
        postSettings("lang=en&theme=" + encodeURIComponent(serverTheme),
            function () { location.reload(); });
    });

    // Appareil / share_info: the checkbox posts the new preference; a
    // refused write is rolled back so the box never lies.
    chkShareInfo.addEventListener("change", function () {
        var want = chkShareInfo.checked;
        showSettingsError("");
        fetchWithTimeout("/api/device/prefs?share_info=" + (want ? "1" : "0") +
            "&" + authQuery(), { method: "POST" }, 10000)
            .then(function (r) {
                if (r.status === 200) return true;
                if (r.status === 401 || r.status === 403) {
                    showSettingsError(t("settings.forbidden"));
                } else if (r.status === 429) {
                    showSettingsError(t("unlock.tooMany"));
                } else {
                    showSettingsError(t("files.serverError"));
                }
                return false;
            })
            .then(function (ok) {
                if (!ok) chkShareInfo.checked = !want;
            })
            .catch(function () {
                chkShareInfo.checked = !want;
                showSettingsError(t("quota.offline"));
            });
    });

    // Appareil / dissociate: same two-tap arm as the folder delete -
    // the first tap turns the label into a tick, the second one (within
    // 3.5 s) posts. window.confirm() was rejected for folders and is
    // equally wrong here.
    function dissociateNow() {
        disarmDissociate();
        showSettingsError("");
        fetchWithTimeout("/api/device/dissociate?" + authQuery(),
            { method: "POST" }, 10000)
            .then(function (r) {
                if (r.status === 200) return true;
                if (r.status === 401 || r.status === 403) {
                    showSettingsError(t("settings.forbidden"));
                } else if (r.status === 429) {
                    showSettingsError(t("unlock.tooMany"));
                } else {
                    showSettingsError(t("files.serverError"));
                }
                return false;
            })
            .then(function (ok) {
                if (!ok) return;
                // The server killed this browser's credentials: drop
                // them all and land on the lock screen. The overlay
                // stays open on purpose - its paste field is the way
                // back in.
                storeForget(TOKEN_KEY);
                storeForget(DEVICE_KEY);
                storeForget(DID_KEY);
                showSessionScreen("");
                renderDeviceStatus(null);
            })
            .catch(function () {
                showSettingsError(t("quota.offline"));
            });
    }

    btnDissociate.addEventListener("click", function () {
        if (armedDissociate) { dissociateNow(); return; }
        btnDissociate.classList.add("armed");
        btnDissociate.textContent = "\u2713";     // tick: "tap again"
        armedDissociate = window.setTimeout(disarmDissociate, 3500);
    });

    // Appareil / copy: clipboard API first, execCommand fallback for
    // browsers (or contexts) where the async API refuses.
    function copyFeedback(message) {
        window.clearTimeout(copyTimer);
        btnCopyToken.textContent = message;
        copyTimer = window.setTimeout(function () {
            btnCopyToken.textContent = t("device.copy");
        }, 1600);
    }

    function copyTokenFallback(text) {
        try {
            var ta = document.createElement("textarea");
            ta.value = text;
            ta.setAttribute("readonly", "");
            ta.style.position = "fixed";
            ta.style.opacity = "0";
            document.body.appendChild(ta);
            ta.select();
            var ok = document.execCommand("copy");
            document.body.removeChild(ta);
            return ok;
        } catch (e) {
            return false;
        }
    }

    btnCopyToken.addEventListener("click", function () {
        var text = deviceTokenEl.textContent;
        if (!text) return;
        function ok() { copyFeedback(t("device.copied")); }
        function fail() { showSettingsError(t("device.copyFailed")); }
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(ok, function () {
                if (copyTokenFallback(text)) ok();
                else fail();
            });
        } else if (copyTokenFallback(text)) {
            ok();
        } else {
            fail();
        }
    });

    // Appareil / re-pair field (not-associated state).
    var settingsPairCtx = {
        btn: btnSettingsPaste,
        report: showSettingsPasteError
    };
    btnSettingsPaste.addEventListener("click", function () {
        pairWithToken(settingsPaste.value, false, settingsPairCtx);
    });
    settingsPaste.addEventListener("keydown", function (e) {
        if (e.key === "Enter") pairWithToken(settingsPaste.value, false, settingsPairCtx);
    });

    settingsBtn.addEventListener("click", openSettings);
    settingsClose.addEventListener("click", closeSettings);
    // Tap the dimmed backdrop (the overlay itself) to dismiss.
    settingsScreen.addEventListener("click", function (e) {
        if (e.target === settingsScreen) closeSettings();
    });
    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && settingsScreen.style.display !== "none") closeSettings();
    });

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

    // --- Pairing push: overlay + busy banner -------------------------
    // Every quota tick reports the desktop's pairing window and whether
    // this IP is registered. An unregistered page gets the pairing
    // overlay pushed once per window - unless a transfer is running,
    // where only the banner pill shows (a tap on it opens the overlay
    // by hand: the only way in while busy). Closing the overlay by any
    // path is a "not now" for the rest of the window; the flag resets
    // when the window expires, so the NEXT window can push again.
    var pairScreen = document.getElementById("pair-screen");
    var pairBanner = document.getElementById("pair-banner");
    var pairToken = document.getElementById("pair-token");
    var btnPair = document.getElementById("btn-pair");
    var btnPairClose = document.getElementById("btn-pair-close");
    var chkPairShowInfo = document.getElementById("chk-pair-showinfo");
    var pairError = document.getElementById("pair-error");
    var PAIR_DISMISSED_KEY = "opendrop_pair_dismissed";
    var pairManuallyOpened = false;   // banner-tap open: survives busy
                                      // ticks (the only way in while busy)

    // sessionStorage, not localStorage: the dismissal belongs to this
    // tab's pairing window, not to the device's whole pairing life.
    function pairDismissed() {
        try { return sessionStorage.getItem(PAIR_DISMISSED_KEY) === "1"; }
        catch (e) { return false; }
    }

    function setPairDismissed(value) {
        try {
            if (value) sessionStorage.setItem(PAIR_DISMISSED_KEY, "1");
            else sessionStorage.removeItem(PAIR_DISMISSED_KEY);
        } catch (e) { /* private mode: dismissal is per-page then */ }
    }

    function showPairError(message) {
        pairError.textContent = message;
        pairError.style.display = message ? "" : "none";
    }

    // `manual` marks a deliberate open (the banner tap): while the
    // transfer runs, quota ticks must not step THAT overlay down -
    // only an auto-pushed one yields to the busy guard.
    function openPairScreen(manual) {
        showPairError("");
        pairToken.value = "";              // never prefill a secret
        chkPairShowInfo.checked = false;   // share_info=0 unless opted in
        pairManuallyOpened = !!manual;
        pairScreen.style.display = "flex";
    }

    // Any manual close (Close pill, backdrop tap, Escape) is a "not
    // now": the quota tick must not push the overlay again this window.
    function closePairScreen() {
        setPairDismissed(true);
        pairManuallyOpened = false;
        pairScreen.style.display = "none";
    }

    var pairPairCtx = {
        btn: btnPair,
        report: showPairError
    };
    btnPair.addEventListener("click", function () {
        // Boolean, not "1"/"0": pairWithToken does its own ternary and
        // the string "0" is truthy.
        pairWithToken(pairToken.value, chkPairShowInfo.checked, pairPairCtx);
    });
    pairToken.addEventListener("keydown", function (e) {
        if (e.key === "Enter") btnPair.click();
    });
    btnPairClose.addEventListener("click", closePairScreen);
    // The banner is the only way into the overlay while busy.
    pairBanner.addEventListener("click", function () {
        openPairScreen(true);
    });
    // Tap the dimmed backdrop (the overlay itself) to dismiss.
    pairScreen.addEventListener("click", function (e) {
        if (e.target === pairScreen) closePairScreen();
    });
    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape" && pairScreen.style.display !== "none") closePairScreen();
    });

    // Reads the pairing link/QR hash (desktop "Pour parrainer" section); nothing auto-submits.
    (function () {
        var m = /^#pair=([A-Za-z0-9]{32})$/.exec(location.hash || "");
        if (!m) return;
        var tok = m[1];
        history.replaceState(null, "", location.pathname + location.search);
        if (storeRead(DEVICE_KEY) === tok) return; // already paired with this token
        openPairScreen(true);
        var input = document.getElementById("pair-token");
        if (input) input.value = tok; // after openPairScreen: it clears the field
    })();

    // The overlay wiring runs above the no-token gate below: the #pair=
    // QR link opens this overlay on a locked page, Pair button included.
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

    // Runs on every quota tick (no new poll of its own).
    function handlePairing(pairing, associated) {
        if (!pairing) {
            // Window expired: hide everything (manual open or not -
            // expiry wins), arm the next window.
            setPairDismissed(false);
            pairManuallyOpened = false;
            pairScreen.style.display = "none";
            pairBanner.style.display = "none";
            return;
        }
        if (associated) {
            // Already registered: pairing is not this page's business.
            // (Defensive hide - a successful pair reloads the page.)
            pairScreen.style.display = "none";
            pairBanner.style.display = "none";
            return;
        }
        if (currentXhr !== null || sendQueue.length > 0) {
            // Busy guard: a transfer runs - never cover its progress.
            // An overlay AUTO-pushed before the upload started steps
            // down; one the user opened from the banner stays up (the
            // banner is the door in while busy, not a ≤5 s glimpse).
            if (!pairManuallyOpened) pairScreen.style.display = "none";
            pairBanner.style.display = "";
            return;
        }
        pairBanner.style.display = "none";
        if (!pairDismissed() && pairScreen.style.display === "none") {
            openPairScreen();   // once per window: a close sets dismissed
        }
    }

    function refreshQuota() {
        if (appEl.style.display === "none") return;
        if (quotaBusy) return;
        quotaBusy = true;

        fetchWithTimeout("/api/quota?" + authQuery(), null, 8000)
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
                if (data.device) storeWrite(DEVICE_KEY, data.device);
                handlePairing(!!data.pairing, !!data.device);
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
    var btnChooseFiles = document.getElementById("btn-choose-files");
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

    // Options panel: one pre-flight screen per batch that needs zipping.
    var sendOptions = document.getElementById("send-options");
    var sendOptionsList = document.getElementById("send-options-list");
    var chkZipPassword = document.getElementById("chk-zip-password");
    var zipPasswordInput = document.getElementById("zip-password-input");
    var zipMode = document.getElementById("zip-mode");
    var btnStart = document.getElementById("btn-start");
    var progressWrap = document.getElementById("progress-wrap");

    var currentXhr = null;
    var currentZip = null;     // AbortController of the zip run in flight
    var pendingBatch = null;   // batch waiting behind the options panel
    var pendingEpoch = 0;      // epoch the pending batch was prepared at

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
            // The panel is a pre-flight screen: only showOptionsPanel
            // brings it back up; every upload view starts without it,
            // with the progress elements back to their default state.
            sendOptions.style.display = "none";
            progressWrap.style.display = "";
            progressText.style.display = "";
            transferInfo.style.display = "";
        } else if (view === "success") {
            dropZone.style.display = "none";
            successMsg.style.display = "";
        } else if (view === "error") {
            dropZone.style.display = "none";
            errorMsg.style.display = "";
        }
    }

    // One send travels as a sequence of small multipart slices (128 MiB):
    // a giant composed Blob in a single request is what Gecko refuses to
    // drain (the user's Zen shows 100% and the server never sees the end
    // of the body), while small requests are proven to work everywhere.
    // The server appends the slices in order into a staging file and
    // answers with the byte count it has committed; that count is the
    // only thing that advances our offset, which is what makes a retry
    // after a lost response safe (the server truncates any stale tail
    // back to our offset before appending).
    var SLICE_SIZE = 128 * 1024 * 1024;

    function makeUploadId() {
        var bytes = new Uint8Array(8);
        if (window.crypto && window.crypto.getRandomValues) {
            window.crypto.getRandomValues(bytes);
        } else {
            for (var i = 0; i < 8; i++) bytes[i] = Math.floor(Math.random() * 256);
        }
        var id = "";
        for (var j = 0; j < 8; j++) id += ("0" + bytes[j].toString(16)).slice(-2);
        return id;
    }

    // The send currently in flight ({id, name}) so cancel and terminal
    // failures can tell the server to drop the staging file it may have
    // left behind.
    var currentSend = null;

    function sendCleanup() {
        if (!currentSend) return;
        var url = "/api/upload?" + authQuery() +
            "&cancel=1&upload=" + currentSend.id +
            "&name=" + encodeURIComponent(currentSend.name);
        currentSend = null;
        // Best-effort: the page stays open, a plain fetch is enough.
        fetch(url, { method: "POST", keepalive: true }).catch(function () {});
    }

    function uploadFile(file) {
        filenameEl.textContent = file.name;
        filesizeEl.textContent = formatSize(file.size);
        progressBar.style.width = "0%";
        progressText.textContent = "0%";
        showSendView("transfer");

        var uploadId = makeUploadId();
        var committed = 0;   // bytes the server has confirmed
        var attempts = 0;    // retries of the current slice
        var resyncs = 0;     // consecutive 409s that made no progress
        var uploadStart = performance.now();
        currentSend = { id: uploadId, name: file.name };

        function failTerminal(msg) {
            sendCleanup();
            currentXhr = null;
            sendQueue = [];
            finishQueue();
            errorDetail.textContent = msg;
            showSendView("error");
        }

        function sendSlice() {
            // A cancelled or superseded send must not resume from a
            // retry still waiting on its timer.
            if (!currentSend || currentSend.id !== uploadId) return;

            var end = Math.min(committed + SLICE_SIZE, file.size);
            var isLast = end === file.size ? 1 : 0;
            var slice = file.slice(committed, end);

            var formData = new FormData();
            // The explicit name matters: Blob.slice drops the name, and
            // the server keys the staging file off it.
            formData.append("file", slice, file.name);

            var xhr = new XMLHttpRequest();
            currentXhr = xhr;

            xhr.upload.addEventListener("progress", function (e) {
                if (!e.lengthComputable) return;
                var overall = committed + e.loaded;
                // A 0-byte file has no denominator (0/0 is NaN): it goes
                // out as a single empty slice, so report it as complete.
                var pct = file.size > 0
                    ? Math.min(100, Math.round((overall / file.size) * 100))
                    : 100;
                progressBar.style.width = pct + "%";
                var txt = pct + "%";
                var elapsed = (performance.now() - uploadStart) / 1000;
                var speed = formatSpeed(overall / elapsed);
                var remaining = file.size > 0
                    ? (file.size - overall) / (overall / elapsed) : 0;
                if (speed) txt += " - " + speed;
                if (remaining > 0 && remaining < 86400) txt += " - " + formatEta(Math.round(remaining));
                // The last slice's answer carries a whole-file hash read
                // back from disk; say so while that is computed.
                if (pct === 100 && isLast) txt = t("upload.finalizing");
                progressText.textContent = txt;
            });

            xhr.addEventListener("load", function () {
                currentXhr = null;
                if (!currentSend || currentSend.id !== uploadId) return; // cancelled
                if (xhr.status === 401 || xhr.status === 403) {
                    sendQueue = [];
                    currentSend = null;
                    endSession(t("session.expired"));
                    return;
                }

                var resp = null;
                try { resp = JSON.parse(xhr.responseText); } catch (err) { resp = null; }

                if (xhr.status === 409) {
                    // Resync, not a failure: the server reports how much
                    // of the staging file survived; continue from there.
                    resyncs++;
                    if (resyncs >= 3) {
                        failTerminal(t("upload.serverError", 409));
                        return;
                    }
                    committed = (resp && resp.size) || 0;
                    sendSlice();
                    return;
                }

                if (xhr.status === 200 && resp && resp.success) {
                    attempts = 0;
                    resyncs = 0;
                    if (isLast) {
                        currentSend = null;
                        queueDone++;
                        if (sendQueue.length) {
                            pumpQueue();    // next file, badge follows along
                            return;
                        }
                        showBatchSuccess(resp);
                        finishQueue();
                        return;
                    }
                    // The committed count comes only from the server: a
                    // success that omits it is a protocol violation, and
                    // guessing forward with our own arithmetic would
                    // desync the staging file.
                    if (typeof resp.size !== "number") {
                        failTerminal(t("upload.serverError", xhr.status));
                        return;
                    }
                    committed = resp.size;
                    sendSlice();
                    return;
                }

                // An honest stall (400), a hiccup (408/5xx) or the part
                // limiter (429) are recoverable: same slice, same offset.
                var retryable = xhr.status === 400 || xhr.status === 408 ||
                    xhr.status === 429 || xhr.status >= 500;
                if (retryable && attempts < 3) {
                    attempts++;
                    setTimeout(sendSlice, xhr.status === 429 ? 3000 : 1000);
                    return;
                }
                failTerminal((resp && resp.error) || t("upload.serverError", xhr.status));
            });

            xhr.addEventListener("error", function () {
                currentXhr = null;
                if (!currentSend || currentSend.id !== uploadId) return; // cancelled
                if (attempts < 3) {
                    attempts++;
                    setTimeout(sendSlice, 1000);
                    return;
                }
                failTerminal(t("upload.unreachable"));
            });

            xhr.open("POST", "/api/upload?" + authQuery() +
                "&upload=" + uploadId +
                "&name=" + encodeURIComponent(file.name) +
                "&offset=" + committed +
                "&total=" + file.size +
                "&last=" + isLast);
            xhr.send(formData);
        }

        sendSlice();
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

    // --- Folder support: a dropped or picked folder travels as one
    // .zip built here, in the browser - the PC's share folder only ever
    // receives a plain .zip. Entry walking is async and batched:
    // readEntries hands out chunks, so it loops until a chunk comes
    // back empty. Preparing only WALKS metadata and builds a batch
    // descriptor; nothing is zipped until the user starts.
    // batch = { items: [{kind:"file", file} | {kind:"folder", name,
    // entries: [{name, file}], rawSize}], totalRaw }; items keep the
    // original drop order end to end.
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

    function addFolderItem(batch, name, entries) {
        var rawSize = 0;
        entries.forEach(function (e) { rawSize += (e.file && e.file.size) || 0; });
        batch.items.push({ kind: "folder", name: name, entries: entries, rawSize: rawSize });
        batch.totalRaw += rawSize;
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
        var batch = { items: [], totalRaw: 0 };
        if (!entries.length) {
            // No entry API, or a plain file drop: the files go as they are.
            var plain = dataTransfer && dataTransfer.files ?
                Array.prototype.slice.call(dataTransfer.files) : [];
            plain.forEach(function (f) {
                batch.items.push({ kind: "file", file: f });
                batch.totalRaw += f.size || 0;
            });
            return Promise.resolve(batch);
        }
        var chain = Promise.resolve(batch);
        entries.forEach(function (entry) {
            chain = chain.then(function (b) {
                if (entry.isFile) {
                    return new Promise(function (resolve, reject) {
                        entry.file(function (f) {
                            b.items.push({ kind: "file", file: f });
                            b.totalRaw += f.size || 0;
                            resolve(b);
                        }, reject);
                    });
                }
                return collectFolderFiles(entry, "").then(function (found) {
                    // An empty folder still travels nowhere (as before).
                    if (found.length) addFolderItem(b, entry.name, found);
                    return b;
                });
            });
        });
        return chain;
    }

    function preparePickedFolders(fileListIn) {
        // <input webkitdirectory>: every file carries webkitRelativePath,
        // grouped per top-level folder and zipped as one on Start.
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
        var batch = { items: [], totalRaw: 0 };
        order.forEach(function (top) { addFolderItem(batch, top, groups[top]); });
        return Promise.resolve(batch);
    }

    function startPreparing(label) {
        showSendView("transfer");
        filenameEl.textContent = label;
        filesizeEl.textContent = "";
        progressBar.style.width = "0%";
        progressText.textContent = t("send.preparing");
    }

    // --- Batch pre-flight: quota check first (fail-open: a flaky
    // usage fetch must never block a send - the server enforces the
    // exact quota at reservation anyway), then ONE options panel for
    // the whole batch when at least one folder needs zipping. A
    // folderless batch travels exactly as before: straight into the
    // upload queue, no panel, no pre-check.

    // Same endpoint and payload shape as the header gauge.
    function fetchQuotaNow() {
        return fetchWithTimeout("/api/quota?" + authQuery(), null, 8000)
            .then(function (r) {
                if (!r.ok) throw new Error("http " + r.status);
                return r.json();
            })
            .then(function (data) {
                if (!data || typeof data.usage_bytes !== "number") {
                    throw new Error("bad quota payload");
                }
                return { usage: data.usage_bytes, limit: data.limit_bytes || 0 };
            });
    }

    // limit 0 = unlimited; a batch exactly filling the remaining space
    // passes (the server refuses only past the line).
    function quotaAllows(totalRaw, usage, limit) {
        if (!limit) return true;
        return totalRaw <= limit - usage;
    }

    // One refusal covers the whole batch: nothing zipped, nothing sent.
    function refuseBatch(totalRaw, quota) {
        var remaining = Math.max(0, quota.limit - quota.usage);
        finishQueue();
        errorDetail.textContent = t("send.tooBig",
            formatSize(totalRaw), formatSize(remaining), formatSize(totalRaw - remaining));
        showSendView("error");
    }

    function prepareThenSend(promise, label) {
        var epoch = ++prepareEpoch;
        startPreparing(label);
        promise.then(function (batch) {
            if (epoch !== prepareEpoch) return;    // cancelled meanwhile
            var hasFolder = false;
            batch.items.forEach(function (it) { if (it.kind === "folder") hasFolder = true; });
            if (!hasFolder) {
                enqueueFiles(batch.items.map(function (it) { return it.file; }));
                return;
            }
            fetchQuotaNow().then(function (quota) {
                if (epoch !== prepareEpoch) return;
                if (!quotaAllows(batch.totalRaw, quota.usage, quota.limit)) {
                    refuseBatch(batch.totalRaw, quota);
                    return;
                }
                showOptionsPanel(batch, epoch);
            }).catch(function (err) {
                // Fail open: log and show the panel anyway.
                console.warn("quota pre-check failed, proceeding", err);
                if (epoch === prepareEpoch) showOptionsPanel(batch, epoch);
            });
        }).catch(function () {
            if (epoch !== prepareEpoch) return;
            finishQueue();
            errorDetail.textContent = t("send.preparingError");
            showSendView("error");
        });
    }

    // The panel lists what the batch carries: loose files by name,
    // folders with name + raw size (metadata only - nothing read yet).
    function renderOptionsList(batch) {
        sendOptionsList.textContent = "";
        batch.items.forEach(function (it) {
            var li = document.createElement("li");
            var name = document.createElement("span");
            name.textContent = it.kind === "folder" ? "\ud83d\udcc1 " + it.name : it.name;
            li.appendChild(name);
            if (it.kind === "folder") {
                var size = document.createElement("span");
                size.className = "send-options-size";
                size.textContent = formatSize(it.rawSize);
                li.appendChild(size);
            }
            sendOptionsList.appendChild(li);
        });
    }

    function updateStartButton() {
        // Box checked with an empty password keeps Start disabled: a
        // forgotten password would mean a lost zip.
        btnStart.disabled = !!(chkZipPassword.checked && !zipPasswordInput.value);
    }

    function showOptionsPanel(batch, epoch) {
        pendingBatch = batch;
        pendingEpoch = epoch;
        renderOptionsList(batch);
        chkZipPassword.checked = false;
        zipPasswordInput.value = "";
        zipPasswordInput.style.display = "none";
        zipMode.value = "deflate";
        updateStartButton();
        showSendView("transfer");   // hides the panel...
        progressWrap.style.display = "none";   // ...and the bar: no work yet
        progressText.style.display = "none";
        sendOptions.style.display = "";
    }

    if (chkZipPassword) {
        chkZipPassword.addEventListener("change", function () {
            zipPasswordInput.style.display = chkZipPassword.checked ? "" : "none";
            updateStartButton();
            if (chkZipPassword.checked) zipPasswordInput.focus();
        });
    }

    if (zipPasswordInput) {
        zipPasswordInput.addEventListener("input", updateStartButton);
    }

    // Commencer: build the folder zips one after the other under one
    // shared AbortController; the bar counts RAW bytes consumed over
    // the folders' raw totals (same denominator in both modes). Each
    // finished zip takes its folder's place in the batch, so the queue
    // uploads the batch in its original drop order.
    function startZipping() {
        var batch = pendingBatch;
        var epoch = pendingEpoch;
        if (!batch || epoch !== prepareEpoch) return;
        var password = chkZipPassword.checked ? zipPasswordInput.value : "";
        var mode = zipMode.value === "store" ? "store" : "deflate";
        pendingBatch = null;

        var folderIdx = [];
        var totalZipRaw = 0;
        batch.items.forEach(function (it, i) {
            if (it.kind === "folder") { folderIdx.push(i); totalZipRaw += it.rawSize; }
        });

        var controller = typeof AbortController !== "undefined" ?
            new AbortController() : null;
        currentZip = controller;

        showSendView("transfer");   // hides the panel
        filesizeEl.textContent = formatSize(batch.totalRaw);
        progressWrap.style.display = "";
        progressText.style.display = "";
        progressBar.style.width = "0%";
        progressText.textContent = t("send.zipping", "0%",
            formatSize(0), formatSize(totalZipRaw));

        var doneBefore = 0;
        var chain = Promise.resolve();
        folderIdx.forEach(function (idx) {
            chain = chain.then(function () {
                var item = batch.items[idx];
                var base = doneBefore;
                return OpenDropZip.buildZip(item.entries, {
                    mode: mode,
                    password: password || undefined,
                    signal: controller ? controller.signal : undefined,
                    onProgress: function (doneRaw) {
                        if (epoch !== prepareEpoch) return;
                        var done = Math.min(base + doneRaw, totalZipRaw);
                        var pct = totalZipRaw ? Math.round((done / totalZipRaw) * 100) : 100;
                        progressBar.style.width = pct + "%";
                        progressText.textContent = t("send.zipping",
                            pct + "%", formatSize(done), formatSize(totalZipRaw));
                    }
                }).then(function (blob) {
                    doneBefore = base + item.rawSize;
                    batch.items[idx] = { kind: "file", file:
                        new File([blob], item.name + ".zip", { type: "application/zip" }) };
                });
            });
        });
        chain.then(function () {
            if (epoch !== prepareEpoch) return;
            currentZip = null;
            enqueueFiles(batch.items.map(function (it) { return it.file; }));
        }).catch(function (err) {
            currentZip = null;
            if (err && err.cancelled) return;   // btnCancel already reset the view
            if (epoch !== prepareEpoch) return;
            finishQueue();
            errorDetail.textContent = t("send.zipFailed");
            showSendView("error");
        });
    }

    if (btnStart) {
        btnStart.addEventListener("click", startZipping);
    }

    dropZone.addEventListener("click", function () {
        fileInput.click();
    });

    if (btnChooseFiles) {
        btnChooseFiles.addEventListener("click", function (e) {
            // The drop zone would open the file picker too.
            e.stopPropagation();
            fileInput.click();
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
                // webkitRelativePath is set for every folder pick; the
                // "..." fallback mirrors the drop handler's label.
                prepareThenSend(preparePickedFolders(folderInput.files),
                    rel ? rel.split("/")[0] : "...");
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
        pendingBatch = null;
        if (currentZip) {
            currentZip.abort();     // buildZip rejects with cancelled
            currentZip = null;
        }
        if (currentXhr) {
            currentXhr.abort();
            currentXhr = null;
        }
        // Tell the server to drop the staging file this send left, so a
        // cancelled multi-gigabyte send does not park its bytes on disk.
        sendCleanup();
        finishQueue();
        showSendView("drop");
        fileInput.value = "";
        if (folderInput) folderInput.value = "";
    });

    btnNew.addEventListener("click", function () {
        pendingBatch = null;
        showSendView("drop");
        fileInput.value = "";
        if (folderInput) folderInput.value = "";
    });

    btnRetry.addEventListener("click", function () {
        pendingBatch = null;
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
        return "/api/download/" + encodeURIComponent(name) + "?" + authQuery();
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

        fetchWithTimeout("/api/files?" + authQuery(), null, 20000)
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
