(function () {
    var TOKEN_KEY = "opendrop_token";

    function storeToken(value) {
        try {
            localStorage.setItem(TOKEN_KEY, value);
        } catch (e) {
            // stockage indisponible (mode prive) : on se contente de l'URL
        }
    }

    function clearToken() {
        try {
            localStorage.removeItem(TOKEN_KEY);
        } catch (e) {
            // stockage indisponible
        }
    }

    function getToken() {
        var fromUrl = new URLSearchParams(window.location.search).get("token");
        if (fromUrl) {
            storeToken(fromUrl);
            // Retire le secret de la barre d'adresse : il ne doit pas rester
            // dans l'historique, les captures d'ecran ni les en-tetes Referer.
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
        // N'efface le token stocke que s'il est identique a celui de cette
        // page : un QR rescanne dans un autre onglet a pu le remplacer.
        var stored = "";
        try {
            stored = localStorage.getItem(TOKEN_KEY) || "";
        } catch (e) {
            // stockage indisponible
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

    // --- Deverrouillage par code ---
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
            showUnlockError("Le code comporte 6 caracteres.");
            return;
        }
        showUnlockError("");
        btnUnlock.disabled = true;
        fetch("/api/session/unlock?code=" + encodeURIComponent(code), { method: "POST" })
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
                    showUnlockError("Trop de tentatives. Attendez une minute.");
                    return;
                }
                showUnlockError(res.data.error || "Code invalide.");
            })
            .catch(function () {
                btnUnlock.disabled = false;
                showUnlockError("Serveur injoignable.");
            });
    }

    codeInput.addEventListener("input", function () {
        codeInput.value = normalizeCode(codeInput.value);
    });
    codeInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter") unlockWithCode();
    });
    btnUnlock.addEventListener("click", unlockWithCode);

    // --- Scanner QR (mobile uniquement) ---
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
            showUnlockError("QR code non reconnu : ce n'est pas un lien OpenDrop.");
            return;
        }
        storeToken(match[1]);
        stopScanner();
        location.reload();
    }

    function startScanner() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            showUnlockError("Camera indisponible : ce navigateur bloque l'acces (contexte " +
                            "non securise). Ouvrez l'appareil photo du telephone et scannez " +
                            "le QR : le lien s'ouvre tout seul.");
            return;
        }
        if (typeof window.BarcodeDetector === "undefined") {
            showUnlockError("Lecture de QR non prise en charge par ce navigateur. Ouvrez " +
                            "l'appareil photo du telephone et scannez le QR : le lien " +
                            "s'ouvre tout seul.");
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
            scanTimer = setInterval(function () {
                detector.detect(scannerVideo).then(function (codes) {
                    if (codes && codes.length) handleScanned(codes[0].rawValue);
                }).catch(function () { /* pas de QR visible */ });
            }, 400);
        }).catch(function () {
            showUnlockError("Acces camera refuse. Ouvrez l'appareil photo et scannez le QR directement.");
        });
    }

    btnScan.addEventListener("click", startScanner);
    btnScanClose.addEventListener("click", stopScanner);

    // Bouton scanner : telephones et tablettes seulement.
    if (window.matchMedia && window.matchMedia("(pointer: coarse)").matches) {
        btnScan.style.display = "";
    }

    if (!token) {
        showSessionScreen("");
        return;
    }

    function formatSize(bytes) {
        if (bytes < 1024) return bytes + " B";
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
        if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
        return (bytes / (1024 * 1024 * 1024)).toFixed(2) + " GB";
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
            tabs.forEach(function (t) { t.classList.remove("active"); });
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
        var value, unit;
        if (bytes >= 1024 * 1024 * 1024) {
            value = (bytes / (1024 * 1024 * 1024)).toFixed(3);
            unit = " Go";
        } else if (bytes >= 1024 * 1024) {
            value = (bytes / (1024 * 1024)).toFixed(1);
            unit = " Mo";
        } else if (bytes >= 1024) {
            value = (bytes / 1024).toFixed(1);
            unit = " Ko";
        } else {
            return bytes + " o";
        }
        return parseFloat(value).toString().replace(".", ",") + unit;
    }

    function renderQuota(usage, limit) {
        quotaBar.style.display = "block";
        quotaText.className = "quota-text";
        if (limit > 0) {
            quotaText.textContent = formatQuota(usage) + " / " + formatQuota(limit);
            quotaText.classList.add(usage >= limit ? "full" : "ok");
        } else {
            quotaText.textContent = formatQuota(usage) + " recus (illimite)";
        }
    }

    function refreshQuota() {
        if (appEl.style.display === "none") return;
        fetch("/api/quota?token=" + encodeURIComponent(token))
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (typeof data.usage_bytes !== "number") return;
                renderQuota(data.usage_bytes, data.limit_bytes || 0);
            })
            .catch(function () { /* session expiree ou serveur hors ligne */ });
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
                endSession("Session expir\u00e9e ou invalide. Rescannez le QR code.");
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
                errorDetail.textContent = resp.error || "Erreur serveur (" + xhr.status + ")";
            } catch (err) {
                errorDetail.textContent = "Erreur serveur (" + xhr.status + ")";
            }
            showSendView("error");
        });

        xhr.addEventListener("error", function () {
            currentXhr = null;
            refreshQuota();
            errorDetail.textContent = "Impossible de contacter le serveur.";
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
        fileList.innerHTML = '<p class="loading">Chargement...</p>';
        emptyMsg.style.display = "none";
        fileList.style.display = "";

        fetch("/api/files?token=" + encodeURIComponent(token))
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
                    btn.textContent = "Telecharger";
                    btn.href = "/api/download/" + encodeURIComponent(file.name) + "?token=" + encodeURIComponent(token);

                    card.appendChild(info);
                    card.appendChild(btn);
                    fileList.appendChild(card);
                });
            })
            .catch(function (err) {
                if (err.message === "session") {
                    fileList.innerHTML = "";
                    endSession("Session expir\u00e9e ou invalide. Rescannez le QR code.");
                } else if (err.message === "rate limit") {
                    fileList.innerHTML = '<p class="loading">Trop de requetes. Attendez.</p>';
                } else if (err.message === "server") {
                    fileList.innerHTML = '<p class="loading">Erreur serveur. Reessayez.</p>';
                } else {
                    fileList.innerHTML = '<p class="loading">Erreur de chargement.</p>';
                }
            });
    }

    btnRefresh.addEventListener("click", function () {
        loadFiles();
    });
})();
