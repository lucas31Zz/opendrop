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
            "upload.unreachable": "Could not reach the server."
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
            "upload.unreachable": "Impossible de contacter le serveur."
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
        if (meta) meta.setAttribute("content", theme === "dark" ? "#0f0f0f" : "#f4f5f7");
    }

    function toggleTheme() {
        storeWrite(THEME_KEY, theme === "dark" ? "light" : "dark");
        storeWrite(THEME_BASE_KEY, normalizeTheme(serverTheme));
        applyTheme();
    }

    var themeButton = document.getElementById("theme-toggle");
    if (themeButton) themeButton.addEventListener("click", toggleTheme);
    applyTheme();

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

    function startScanner() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            showUnlockError(t("camera.blocked"));
            return;
        }
        if (typeof window.BarcodeDetector === "undefined") {
            showUnlockError(t("camera.unsupported"));
            return;
        }
        navigator.mediaDevices.getUserMedia({
            video: { facingMode: { ideal: "environment" } },
            audio: false
        }).then(function (stream) {
            scanStream = stream;
            scanner.style.display = "";
            scannerVideo.srcObject = stream;
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
        }).catch(function () {
            showUnlockError(t("camera.denied"));
        });
    }

    btnScan.addEventListener("click", startScanner);
    btnScanClose.addEventListener("click", stopScanner);

    // Scanner button: phones and tablets only.
    if (window.matchMedia && window.matchMedia("(pointer: coarse)").matches) {
        btnScan.style.display = "";
    }

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

    // --- TABS ---
    var tabs = document.querySelectorAll(".tab");
    var tabSend = document.getElementById("tab-send");
    var tabReceive = document.getElementById("tab-receive");

    tabs.forEach(function (tab) {
        tab.addEventListener("click", function () {
            tabs.forEach(function (t2) { t2.classList.remove("active"); });
            tab.classList.add("active");
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
        } else {
            quotaText.textContent = t("quota.unlimited", formatQuota(usage));
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
    var transferInfo = document.getElementById("transfer-info");
    var successMsg = document.getElementById("success-msg");
    var errorMsg = document.getElementById("error-msg");

    var filenameEl = document.getElementById("filename");
    var filesizeEl = document.getElementById("filesize");
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
            refreshQuota();
            if (xhr.status === 401 || xhr.status === 403) {
                endSession(t("session.expired"));
                return;
            }
            try {
                var resp = JSON.parse(xhr.responseText);
                if (xhr.status === 200 && resp.success) {
                    successFilename.textContent = resp.filename;
                    successSize.textContent = formatSize(resp.size);
                    if (resp.sha256) {
                        successHash.textContent = "SHA-256: " + resp.sha256;
                        successHash.style.display = "";
                    } else {
                        successHash.style.display = "none";
                    }
                    showSendView("success");
                    return;
                }
                errorDetail.textContent = resp.error || t("upload.serverError", xhr.status);
            } catch (err) {
                errorDetail.textContent = t("upload.serverError", xhr.status);
            }
            showSendView("error");
        });

        xhr.addEventListener("error", function () {
            currentXhr = null;
            refreshQuota();
            errorDetail.textContent = t("upload.unreachable");
            showSendView("error");
        });

        xhr.open("POST", "/api/upload?token=" + encodeURIComponent(token));
        xhr.send(formData);
    }

    dropZone.addEventListener("click", function () {
        fileInput.click();
    });

    fileInput.addEventListener("change", function () {
        if (fileInput.files.length > 0) {
            uploadFile(fileInput.files[0]);
        }
    });

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
        if (e.dataTransfer.files.length > 0) {
            uploadFile(e.dataTransfer.files[0]);
        }
    });

    btnCancel.addEventListener("click", function () {
        if (currentXhr) {
            currentXhr.abort();
            currentXhr = null;
        }
        showSendView("drop");
        fileInput.value = "";
    });

    btnNew.addEventListener("click", function () {
        showSendView("drop");
        fileInput.value = "";
    });

    btnRetry.addEventListener("click", function () {
        showSendView("drop");
        fileInput.value = "";
    });

    // --- DOWNLOAD ---
    var fileList = document.getElementById("file-list");
    var emptyMsg = document.getElementById("empty-msg");
    var btnRefresh = document.getElementById("btn-refresh");

    function loadFiles() {
        fileList.innerHTML = "";
        var loading = document.createElement("p");
        loading.className = "loading";
        loading.textContent = t("files.loading");
        fileList.appendChild(loading);
        emptyMsg.style.display = "none";
        fileList.style.display = "";

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
                fileList.innerHTML = "";
                if (!data.files || data.files.length === 0) {
                    emptyMsg.style.display = "";
                    fileList.style.display = "none";
                    return;
                }
                emptyMsg.style.display = "none";
                fileList.style.display = "";
                data.files.forEach(function (file) {
                    var card = document.createElement("div");
                    card.className = "file-card";

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
                    btn.href = "/api/download/" + encodeURIComponent(file.name) + "?token=" + encodeURIComponent(token);

                    card.appendChild(info);
                    card.appendChild(btn);
                    fileList.appendChild(card);
                });
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
                }
            });
    }

    btnRefresh.addEventListener("click", function () {
        loadFiles();
    });
})();
