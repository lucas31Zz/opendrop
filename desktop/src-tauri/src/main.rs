// OpenDrop desktop app (Tauri 2 + React): a frameless window and tray
// driving the real OpenDrop engine.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::collections::HashMap;
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::{Arc, Mutex};
use std::time::Duration;
mod spawn;
mod updater;
use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{Emitter, Manager, State};

#[derive(Clone, serde::Serialize)]
struct EngineInfo {
    ip: String,
    port: u16,
    token: String,
    session_code: String,
    url_upload: String,
    lang: String,
    version: String,
    download_dir: String,
    share_dir: String,
}

/// The process currently holding the configured port when the engine
/// could not bind it (PortInUseError). Surfaced to the UI so the status
/// card can name the app and offer to kill it.
#[derive(Clone, serde::Serialize)]
struct PortHolder {
    port: u16,
    pid: u32,
    name: String,
    path: String,
}

/// `Arc` fields + `Clone`: every command clones the state so it can be
/// moved into `spawn_blocking` (see `blocking`) - the blocking body then
/// owns a handle to the SAME shared mutexes the rest of the app reads.
#[derive(Clone)]
struct AppState {
    engine: Arc<Mutex<Option<Child>>>,
    info: Arc<Mutex<Option<EngineInfo>>>,
    /// Serializes start/stop/rotate: rapid repeated clicks used to
    /// interleave two respawns and leave `info` holding a dead token
    /// (the QR then got a 403 body instead of a PNG).
    control: Arc<Mutex<()>>,
    port_busy: Arc<Mutex<Option<PortHolder>>>,
    /// Live update download: mirrored to the UI by `update-progress`.
    update: Arc<Mutex<UpdatePhase>>,
    /// (tag, digest) of the release check_updates last offered; BOTH
    /// `done` gates verify the finished file against this digest before
    /// it is allowed to become an installer.
    update_meta: Arc<Mutex<Option<(String, String)>>>,
}

// Built ONCE and deliberately leaked (OnceLock): a few MB, so no request
// ever rebuilds a client. NOTE: the UI panic was NOT this client - it was
// reqwest's debug-only wait.rs::enter() shell-runtime drop, which every
// command now avoids by running on the blocking pool (see `blocking`).
static HTTP: std::sync::OnceLock<reqwest::blocking::Client> = std::sync::OnceLock::new();

fn http() -> &'static reqwest::blocking::Client {
    // The engine serves HTTPS with a self-signed cert; desktop trusts it.
    HTTP.get_or_init(|| {
        reqwest::blocking::Client::builder()
            .danger_accept_invalid_certs(true)
            .timeout(Duration::from_secs(15))
            .build()
            .expect("http client")
    })
}

/// Downloads run on their OWN client: `http()`'s 15 s total timeout
/// would abort a 116 MB installer halfway through. Only the connect
/// step is capped here.
static HTTP_DL: std::sync::OnceLock<reqwest::blocking::Client> = std::sync::OnceLock::new();

fn http_dl() -> &'static reqwest::blocking::Client {
    HTTP_DL.get_or_init(|| {
        reqwest::blocking::Client::builder()
            .connect_timeout(Duration::from_secs(15))
            .build()
            .expect("download client")
    })
}

/// Run a command body OFF the async workers, on Tauri's blocking pool.
/// Why: reqwest::blocking's debug-only sanity check (wait.rs::enter)
/// builds a shell tokio Runtime PER REQUEST and drops it on the calling
/// thread; on an async worker that drop panics tokio ("Cannot drop a
/// runtime in a context where blocking is not allowed"), the worker
/// dies, the command's JS promise never settles and React stops
/// re-rendering (live window, frozen UI). The blocking pool allows
/// runtime drops - and no blocking body (PowerShell spawn, 15s HTTPS
/// timeouts, engine respawn) can stall an async worker anymore.
async fn blocking<T, F>(f: F) -> Result<T, String>
where
    F: FnOnce() -> Result<T, String> + Send + 'static,
    T: Send + 'static,
{
    tauri::async_runtime::spawn_blocking(f)
        .await
        .map_err(|e| e.to_string())?
}

/// Kill an app-owned engine orphan (identified by its forced port) left
/// behind by a previous `tauri dev` run. Only matches OUR command line
/// (`--headless --port N`: the installed OpenDrop and the desktop app
/// never pass `--port`), so they are never touched.
fn reap_orphan() {
    let _ = Command::new("powershell")
        .args([
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | \
             Where-Object { $_.CommandLine -like '*opendrop.main*--headless*--port*' } | \
             ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }",
        ])
        .status();
}

/// The port the engine must bind: `preferred_port` from config.json, the
/// engine's own default (8080) when missing or nonsensical. Strict — the
/// engine is started WITH `--port`, so a busy port is a loud
/// PortInUseError instead of the silent walk to preferred+1 (that walk is
/// what the CLI does; the desktop UI must show the port the user typed).
fn configured_port() -> u16 {
    read_config()
        .ok()
        .and_then(|c| c.get("preferred_port").and_then(|v| v.as_i64()))
        .filter(|p| (1..=65535).contains(p))
        .unwrap_or(8080) as u16
}

/// The process listening on `port`, when someone holds it: PID, name and
/// executable path (Get-NetTCPConnection -> Get-Process). This is what the
/// status card names when the configured port is already taken.
fn port_holder(port: u16) -> Option<PortHolder> {
    let script = format!(
        "$c = Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue | \
         Select-Object -First 1; if ($c) {{ $p = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue; \
         if ($p) {{ [pscustomobject]@{{ pid=$p.Id; name=$p.ProcessName; path=$p.Path }} | ConvertTo-Json -Compress }} }}"
    );
    let out = Command::new("powershell")
        .args(["-NoProfile", "-Command", &script])
        .output()
        .ok()?;
    let text = String::from_utf8_lossy(&out.stdout);
    let v: serde_json::Value = serde_json::from_str(text.trim()).ok()?;
    Some(PortHolder {
        port,
        pid: v["pid"].as_u64().unwrap_or(0) as u32,
        name: v["name"].as_str().unwrap_or("?").to_string(),
        path: v["path"].as_str().unwrap_or("").to_string(),
    })
}

/// Spawn `python -m opendrop.main --headless` on the configured port and
/// read the JSON handshake it prints on stdout. If the port is held by an
/// orphan from a previous run, reap it and retry once instead of
/// panicking. When the port ends up held by anything else, remember WHO
/// so the UI can name it and offer to kill it.
fn spawn_engine(state: &AppState, rotate_token: bool) -> Result<EngineInfo, String> {
    let port = configured_port();
    match try_spawn(state, port, rotate_token) {
        ok @ Ok(_) => {
            *state.port_busy.lock().unwrap() = None;
            ok
        }
        Err(first) => {
            reap_orphan();
            std::thread::sleep(std::time::Duration::from_millis(700));
            match try_spawn(state, port, rotate_token) {
                ok @ Ok(_) => {
                    *state.port_busy.lock().unwrap() = None;
                    ok
                }
                Err(second) => {
                    *state.port_busy.lock().unwrap() = port_holder(port);
                    Err(format!("{first} | retry: {second}"))
                }
            }
        }
    }
}

fn try_spawn(
    state: &AppState,
    port: u16,
    rotate_token: bool,
) -> Result<EngineInfo, String> {
    // `--port <configured>`: the Settings port, honored like the desktop
    // app does (its ServerManager lets the engine read preferred_port
    // itself) - never a pinned number. The interpreter, PYTHONPATH and
    // the working directory come from `spawn`: venv first, then PATH,
    // with `<root>/src` on PYTHONPATH - the pre-1.0 Avalonia resolution.
    // Without it an installed bundle (no editable install) could never
    // `import opendrop`, and the engine would not start on a clean box.
    let root = spawn::project_root();
    let mut child = spawn::engine_command(&root, port, rotate_token)
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|e| format!("cannot spawn engine: {e}"))?;

    let stdout = child.stdout.take().ok_or("no stdout pipe")?;
    let mut reader = BufReader::new(stdout);

    // The handshake is the one line containing "__opendrop_info__".
    // read_line blocks on a pipe, so the reader runs on its own thread
    // and the wait is bounded by TIME (10 s per line): a stalled python
    // would otherwise wedge boot (window never opens) or the control
    // mutex forever.
    let (tx, rx) = std::sync::mpsc::channel::<String>();
    std::thread::spawn(move || {
        let mut line = String::new();
        loop {
            line.clear();
            match reader.read_line(&mut line) {
                Ok(0) | Err(_) => break,
                Ok(_) => {
                    if tx.send(std::mem::take(&mut line)).is_err() {
                        break;
                    }
                }
            }
        }
    });

    let mut version = String::new();
    let mut handshake: Option<String> = None;
    let deadline = std::time::Duration::from_secs(10);
    while let Ok(line) = rx.recv_timeout(deadline) {
        println!("[engine] {}", line.trim());
        // Banner line "OpenDrop v1.0.0", before the handshake JSON.
        let trimmed = line.trim();
        if trimmed.starts_with("OpenDrop v") {
            version = trimmed.trim_start_matches("OpenDrop v").to_string();
        }
        if line.contains("__opendrop_info__") {
            handshake = Some(line);
            break;
        }
    }
    let Some(handshake) = handshake else {
        let _ = child.kill();
        return Err("engine printed no __opendrop_info__ handshake".into());
    };
    let v: serde_json::Value = match serde_json::from_str(&handshake) {
        Ok(v) => v,
        Err(e) => {
            let _ = child.kill();
            return Err(format!("bad handshake: {e}"));
        }
    };
    let info = EngineInfo {
        ip: v["ip"].as_str().unwrap_or("").to_string(),
        port: v["port"].as_u64()
            .map(|p| p as u16)
            .or_else(|| v["port"].as_str().and_then(|s| s.parse().ok()))
            .unwrap_or(0),
        token: v["token"].as_str().unwrap_or("").to_string(),
        session_code: v["session_code"].as_str().unwrap_or("").to_string(),
        url_upload: v["url_upload"].as_str().unwrap_or("").to_string(),
        lang: v["lang"].as_str().unwrap_or("en").to_string(),
        version,
        download_dir: v["download_dir"].as_str().unwrap_or("").to_string(),
        share_dir: v["share_dir"].as_str().unwrap_or("").to_string(),
    };
    // Keep draining stdout (the channel stays fed) so the child never
    // blocks on a full pipe.
    std::thread::spawn(move || while rx.recv().is_ok() {});
    *state.engine.lock().unwrap() = Some(child);
    Ok(info)
}

fn base(state: &AppState) -> Result<EngineInfo, String> {
    state
        .info
        .lock()
        .unwrap()
        .clone()
        .ok_or_else(|| "engine not started".into())
}

#[tauri::command]
async fn engine_info(state: State<'_, AppState>) -> Result<EngineInfo, String> {
    let st = state.inner().clone();
    blocking(move || engine_info_impl(&st)).await
}

fn engine_info_impl(state: &AppState) -> Result<EngineInfo, String> {
    base(state)
}

/// One round-trip bundle of everything the home screen shows. While the
/// engine is stopped only {running:false} comes back, like the desktop's
/// UpdateUI("stopped") - plus `port_busy` (who holds the configured port)
/// so the status card can name the app and offer to kill it.
#[tauri::command]
async fn get_state(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    let st = state.inner().clone();
    blocking(move || get_state_impl(&st)).await
}

fn get_state_impl(state: &AppState) -> Result<serde_json::Value, String> {
    let info = match state.info.lock().unwrap().clone() {
        Some(i) => i,
        None => {
            return Ok(serde_json::json!({
                "running": false,
                "port_busy": state.port_busy.lock().unwrap().clone(),
            }))
        }
    };
    let c = http();
    let root = format!("https://{}:{}", info.ip, info.port);
    let t = &info.token;

    let get = |path: &str| -> serde_json::Value {
        let url = format!("{root}{path}?token={t}");
        match c.get(&url).send() {
            Ok(r) if r.status().is_success() => {
                r.json().unwrap_or(serde_json::Value::Null)
            }
            // A 4xx/5xx body is JSON too ({"error":...}): parsing it as
            // the payload would hand the UI an empty quota/files/status.
            Ok(r) => serde_json::json!({ "error": format!("HTTP {}", r.status()) }),
            Err(e) => serde_json::json!({ "error": e.to_string() }),
        }
    };

    Ok(serde_json::json!({
        "running": true,
        "info": info,
        "api_info": get("/api/info"),
        "quota": get("/api/quota"),
        "files": get("/api/files"),
        "device": get("/api/device/status"),
    }))
}

#[tauri::command]
async fn upload_file(
    state: State<'_, AppState>,
    name: String,
    bytes: Vec<u8>,
) -> Result<serde_json::Value, String> {
    let st = state.inner().clone();
    blocking(move || upload_file_impl(&st, name, bytes)).await
}

fn upload_file_impl(
    state: &AppState,
    name: String,
    bytes: Vec<u8>,
) -> Result<serde_json::Value, String> {
    let info = base(state)?;
    let url = format!(
        "https://{}:{}/api/upload?token={}",
        info.ip, info.port, info.token
    );
    let part = reqwest::blocking::multipart::Part::bytes(bytes).file_name(name);
    let form = reqwest::blocking::multipart::Form::new().part("file", part);
    let r = http()
        .post(&url)
        .multipart(form)
        .send()
        .map_err(|e| format!("upload failed: {e}"))?;
    r.json().map_err(|e| format!("upload response: {e}"))
}

/// QR PNG for the upload URL: the desktop app builds it locally with
/// QRCoder, the engine exposes the same image on GET /qr (token-gated).
#[tauri::command]
async fn get_qr(state: State<'_, AppState>) -> Result<Vec<u8>, String> {
    let st = state.inner().clone();
    blocking(move || get_qr_impl(&st)).await
}

fn get_qr_impl(state: &AppState) -> Result<Vec<u8>, String> {
    let info = base(state)?;
    let url = format!("https://{}:{}/qr?token={}", info.ip, info.port, info.token);
    let resp = http()
        .get(&url)
        .send()
        .map_err(|e| format!("qr fetch: {e}"))?;
    // A stale token answers 403 with a JSON body; handing that to the
    // <img> as "PNG" breaks the QR until the next restart.
    let status = resp.status();
    if !status.is_success() {
        return Err(format!("qr http {status}"));
    }
    resp.bytes()
        .map(|b| b.to_vec())
        .map_err(|e| format!("qr read: {e}"))
}

/// Start/stop/rotate the engine (bottom-bar toggle + token Reset).
/// "rotate" restarts with --rotate-token, changing token/QR/session code.
#[tauri::command]
async fn server_control(
    state: State<'_, AppState>,
    action: String,
) -> Result<Option<EngineInfo>, String> {
    let st = state.inner().clone();
    blocking(move || server_control_impl(&st, action)).await
}

fn server_control_impl(state: &AppState, action: String) -> Result<Option<EngineInfo>, String> {
    // One control at a time (see AppState::control).
    let _serial = state.control.lock().unwrap();
    let stop = |state: &AppState| {
        if let Some(mut child) = state.engine.lock().unwrap().take() {
            let _ = child.kill();
        }
    };
    match action.as_str() {
        "stop" => {
            stop(state);
            // Give the port a beat to be released before any restart.
            std::thread::sleep(Duration::from_millis(300));
            *state.info.lock().unwrap() = None;
            Ok(None)
        }
        "start" | "rotate" => {
            stop(state);
            // Clear the old info BEFORE respawning, like save_config's
            // restart: a failed start must leave {running:false} instead
            // of a stale EngineInfo pointing at the dead engine - the UI
            // would keep claiming "Server running" and the get_state poll
            // would keep hammering a dead address forever.
            *state.info.lock().unwrap() = None;
            std::thread::sleep(Duration::from_millis(400));
            let info = spawn_engine(state, action == "rotate")?;
            *state.info.lock().unwrap() = Some(info.clone());
            Ok(Some(info))
        }
        other => Err(format!("unknown action: {other}")),
    }
}

/// Kill whatever holds the configured port (the app the status card
/// named), then re-check: Ok(true) = the port is finally free. Refuses
/// PID 0/4 (idle/system) - the recorded PID could be stale.
#[tauri::command]
async fn kill_holder(state: State<'_, AppState>) -> Result<bool, String> {
    let st = state.inner().clone();
    blocking(move || kill_holder_impl(&st)).await
}

fn kill_holder_impl(state: &AppState) -> Result<bool, String> {
    let holder = state.port_busy.lock().unwrap().clone();
    let Some(h) = holder else { return Ok(false) };
    if h.pid < 5 {
        return Err("refusing to kill that process".into());
    }
    let _ = Command::new("powershell")
        .args([
            "-NoProfile",
            "-Command",
            format!("Stop-Process -Id {} -Force -ErrorAction SilentlyContinue", h.pid).as_str(),
        ])
        .status();
    // Give the socket a beat, then re-check reality instead of trusting
    // the kill: another process may have grabbed the port meanwhile.
    std::thread::sleep(Duration::from_millis(400));
    let still = port_holder(h.port);
    let freed = still.is_none();
    *state.port_busy.lock().unwrap() = still;
    Ok(freed)
}

/// Open an https URL in the browser (Discord button, settings links).
/// https only: the command would be a backdoor into the shell.
#[tauri::command]
async fn open_url(url: String) -> Result<(), String> {
    blocking(move || open_url_impl(url)).await
}

fn open_url_impl(url: String) -> Result<(), String> {
    if !url.starts_with("https://") {
        return Err("only https urls".into());
    }
    Command::new("cmd")
        .args(["/C", "start", "", &url])
        .spawn()
        .map_err(|e| format!("open url: {e}"))?;
    Ok(())
}

/// Open a path (folder or file) with the system handler, like the
/// desktop's Process.Start UseShellExecute.
#[tauri::command]
async fn open_path(path: String) -> Result<(), String> {
    blocking(move || open_path_impl(path)).await
}

fn open_path_impl(path: String) -> Result<(), String> {
    let p = PathBuf::from(&path);
    if !p.exists() {
        return Err(format!("missing: {path}"));
    }
    Command::new("cmd")
        .args(["/C", "start", "", &path])
        .spawn()
        .map_err(|e| format!("open path: {e}"))?;
    Ok(())
}

#[tauri::command]
async fn copy_text(text: String) -> Result<(), String> {
    blocking(move || copy_text_impl(text)).await
}

fn copy_text_impl(text: String) -> Result<(), String> {
    // The webview clipboard API is tried first by the frontend; this is
    // the fallback for when it is unavailable.
    Command::new("powershell")
        .args(["-NoProfile", "-Command", "Set-Clipboard -Value $env:OD_CLIP"])
        .env("OD_CLIP", &text)
        .status()
        .map_err(|e| format!("clipboard: {e}"))?;
    Ok(())
}

// ---------------------------------------------------------------- files

fn config_dir() -> PathBuf {
    let base = std::env::var("LOCALAPPDATA")
        .or_else(|_| std::env::var("APPDATA"))
        .unwrap_or_else(|_| {
            let home = std::env::var("HOME").unwrap_or_else(|_| ".".into());
            format!("{home}/.opendrop")
        });
    PathBuf::from(base).join("OpenDrop")
}

fn moves_path() -> PathBuf {
    config_dir().join("moves.json")
}

/// { "<path in the share folder>": "<original path>" }, same file the
/// desktop app writes (Services/MoveRegistry.cs).
fn load_moves() -> HashMap<String, String> {
    std::fs::read_to_string(moves_path())
        .ok()
        .and_then(|s| serde_json::from_str(&s).ok())
        .unwrap_or_default()
}

fn save_moves(map: &HashMap<String, String>) {
    let _ = std::fs::create_dir_all(config_dir());
    let _ = std::fs::write(
        moves_path(),
        serde_json::to_string_pretty(map).unwrap_or_default(),
    );
}

/// "report.pdf" then "report (2).pdf": never overwrites (UniquePath).
fn unique_path(target: &Path) -> PathBuf {
    if !target.exists() {
        return target.to_path_buf();
    }
    let stem = target
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("file")
        .to_string();
    let ext = target
        .extension()
        .and_then(|s| s.to_str())
        .map(|e| format!(".{e}"))
        .unwrap_or_default();
    let parent = target.parent().map(|p| p.to_path_buf()).unwrap_or_default();
    for i in 2..10_000 {
        let candidate = parent.join(format!("{stem} ({i}){ext}"));
        if !candidate.exists() {
            return candidate;
        }
    }
    target.to_path_buf()
}

/// The running server knows the path it serves; fall back on config.json
/// when stopped (ResolveShareDir).
fn current_share_dir(state: &AppState) -> Result<String, String> {
    if let Some(info) = state.info.lock().unwrap().clone() {
        if !info.share_dir.is_empty() {
            return Ok(info.share_dir);
        }
    }
    read_config()
        .ok()
        .and_then(|c| {
            c.get("share_directory")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string())
        })
        .ok_or_else(|| "no share dir".into())
}

fn read_config() -> Result<serde_json::Value, String> {
    let path = config_dir().join("config.json");
    let text = std::fs::read_to_string(&path)
        .map_err(|e| format!("read config {}: {e}", path.display()))?;
    serde_json::from_str(&text).map_err(|e| format!("parse config: {e}"))
}

#[tauri::command]
async fn list_files(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    let st = state.inner().clone();
    blocking(move || list_files_impl(&st)).await
}

fn list_files_impl(state: &AppState) -> Result<serde_json::Value, String> {
    let dir = current_share_dir(state)?;
    let mut files: Vec<serde_json::Value> = vec![];
    let path = PathBuf::from(&dir);

    if path.is_dir() {
        let origins = load_moves();
        let mut entries: Vec<(String, u64, String, Option<String>)> = vec![];
        for entry in std::fs::read_dir(&path).map_err(|e| e.to_string())? {
            let Ok(entry) = entry else { continue };
            let Ok(meta) = entry.metadata() else { continue };
            if !meta.is_file() {
                continue;
            }
            let full = entry.path().to_string_lossy().to_string();
            let origin = origins.get(&full).cloned();
            entries.push((
                entry.file_name().to_string_lossy().to_string(),
                meta.len(),
                full,
                origin,
            ));
        }
        entries.sort_by(|a, b| a.0.to_lowercase().cmp(&b.0.to_lowercase()));
        for (name, size, full, origin) in entries {
            files.push(serde_json::json!({
                "name": name, "size": size, "full": full,
                "origin": origin,
                "can_put_back": origin.is_some(),
            }));
        }
        Ok(serde_json::json!({ "path": dir, "missing": false, "files": files }))
    } else {
        Ok(serde_json::json!({ "path": dir, "missing": true, "files": [] }))
    }
}

#[tauri::command]
async fn rename_file(
    state: State<'_, AppState>,
    old: String,
    new: String,
) -> Result<String, String> {
    let st = state.inner().clone();
    blocking(move || rename_file_impl(&st, old, new)).await
}

fn rename_file_impl(state: &AppState, old: String, new: String) -> Result<String, String> {
    let dir = current_share_dir(state)?;
    let new = new.trim().to_string();
    const INVALID: [char; 9] = ['<', '>', '"', ':', '/', '\\', '|', '?', '*'];
    if new.is_empty() || new != new.trim() || new.chars().any(|c| INVALID.contains(&c)) {
        return Ok("invalid".into());
    }
    let src = PathBuf::from(&dir).join(&old);
    let dst = PathBuf::from(&dir).join(&new);
    if !src.exists() {
        return Ok("missing".into());
    }
    // A case-only rename (a.txt -> A.txt) is legal on Windows: the
    // case-insensitive exists() would wrongly reject it (the desktop
    // allows it too, ShareFolderOps.TargetTaken).
    if dst.exists() && !old.eq_ignore_ascii_case(&new) {
        return Ok("exists".into());
    }
    std::fs::rename(&src, &dst).map_err(|e| e.to_string())?;
    // Keep the moves.json key in step so Put back still works.
    let mut moves = load_moves();
    let src_key = src.to_string_lossy().to_string();
    if let Some(origin) = moves.remove(&src_key) {
        moves.insert(dst.to_string_lossy().to_string(), origin);
        save_moves(&moves);
    }
    Ok("ok".into())
}

#[tauri::command]
async fn delete_files(state: State<'_, AppState>, names: Vec<String>) -> Result<u32, String> {
    let st = state.inner().clone();
    blocking(move || delete_files_impl(&st, names)).await
}

fn delete_files_impl(state: &AppState, names: Vec<String>) -> Result<u32, String> {
    let dir = current_share_dir(state)?;
    let mut moves = load_moves();
    let mut failed = 0u32;
    for name in names {
        let full = PathBuf::from(&dir).join(&name);
        match std::fs::remove_file(&full) {
            Ok(_) => {
                moves.remove(&full.to_string_lossy().to_string());
            }
            Err(_) => failed += 1,
        }
    }
    save_moves(&moves);
    Ok(failed)
}

#[tauri::command]
async fn put_back(state: State<'_, AppState>, name: String) -> Result<String, String> {
    let st = state.inner().clone();
    blocking(move || put_back_impl(&st, name)).await
}

fn put_back_impl(state: &AppState, name: String) -> Result<String, String> {
    let dir = current_share_dir(state)?;
    let src = PathBuf::from(&dir).join(&name);
    let mut moves = load_moves();
    let src_key = src.to_string_lossy().to_string();
    let origin = moves
        .get(&src_key)
        .cloned()
        .ok_or_else(|| "no origin".to_string())?;
    let target = unique_path(Path::new(&origin));
    if let Some(parent) = target.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    std::fs::rename(&src, &target).map_err(|e| e.to_string())?;
    moves.remove(&src_key);
    save_moves(&moves);
    Ok(target.to_string_lossy().to_string())
}

/// Absolute path as .NET writes it in moves.json: no `\\?\` prefix, so
/// the desktop app's MoveRegistry keys and ours stay interchangeable.
fn norm_path(p: &Path) -> String {
    let abs = std::fs::canonicalize(p).unwrap_or_else(|_| p.to_path_buf());
    let s = abs.to_string_lossy().to_string();
    s.strip_prefix(r"\\?\").unwrap_or(&s).to_string()
}

/// Recurse a dropped folder down to the files it contains (ExpandToFiles).
fn expand_dir(dir: &Path, out: &mut Vec<PathBuf>) {
    if let Ok(entries) = std::fs::read_dir(dir) {
        for entry in entries.flatten() {
            let p = entry.path();
            if p.is_file() {
                out.push(p);
            } else if p.is_dir() {
                expand_dir(&p, out);
            }
        }
    }
}

/// Copy or move sources into the share folder (Add files + drop target).
/// Folders are expanded to the files they contain, like Explorer does.
#[tauri::command]
async fn import_files(
    state: State<'_, AppState>,
    sources: Vec<String>,
    mode: String,
) -> Result<serde_json::Value, String> {
    let st = state.inner().clone();
    blocking(move || import_files_impl(&st, sources, mode)).await
}

fn import_files_impl(
    state: &AppState,
    sources: Vec<String>,
    mode: String,
) -> Result<serde_json::Value, String> {
    let dir = current_share_dir(state)?;
    let move_ = mode == "move";
    if std::fs::create_dir_all(&dir).is_err() {
        return Ok(serde_json::json!({"added": 0, "skipped": 0, "failed": sources.len()}));
    }

    let mut added = 0u32;
    let mut skipped = 0u32;
    let mut failed = 0u32;
    let mut moved: Vec<(String, String)> = vec![];

    for source in &sources {
        let mut files: Vec<PathBuf> = vec![];
        let src = PathBuf::from(source);
        if src.is_file() {
            files.push(src);
        } else if src.is_dir() {
            expand_dir(&src, &mut files);
        }

        for file in files {
            let full = norm_path(&file);
            let full_ref = PathBuf::from(&full);
            let Some(name) = full_ref.file_name().map(|n| n.to_string_lossy().to_string()) else {
                failed += 1;
                continue;
            };
            let target_raw = PathBuf::from(&dir).join(&name);
            // Already in the share folder: nothing to do (same full-path
            // check as the web app's upload route, case-insensitive).
            if full.eq_ignore_ascii_case(&target_raw.to_string_lossy()) {
                skipped += 1;
                continue;
            }
            let target = unique_path(&target_raw);
            let result = if move_ {
                std::fs::rename(&full, &target)
            } else {
                std::fs::copy(&full, &target).map(|_| ())
            };
            match result {
                Ok(_) => {
                    added += 1;
                    if move_ {
                        moved.push((target.to_string_lossy().to_string(), full));
                    }
                }
                Err(_) => failed += 1,
            }
        }
    }

    // Remember where each moved file came from so it can be put back.
    if !moved.is_empty() {
        let mut moves = load_moves();
        for (target, origin) in moved {
            moves.insert(target, origin);
        }
        save_moves(&moves);
    }

    Ok(serde_json::json!({"added": added, "skipped": skipped, "failed": failed}))
}

/// Native multi-select file dialog (PowerShell WinForms, no extra crate).
#[tauri::command]
async fn pick_files() -> Result<Vec<String>, String> {
    blocking(pick_files_impl).await
}

fn pick_files_impl() -> Result<Vec<String>, String> {
    let script = "Add-Type -AssemblyName System.Windows.Forms\n\
                  $d = New-Object System.Windows.Forms.OpenFileDialog\n\
                  $d.Multiselect = $true\n\
                  if ($d.ShowDialog() -eq 'OK') { $d.FileNames }";
    let out = Command::new("powershell")
        .args(["-NoProfile", "-Command", script])
        .output()
        .map_err(|e| format!("dialog: {e}"))?;
    let text = String::from_utf8_lossy(&out.stdout);
    Ok(text
        .lines()
        .filter(|l| !l.trim().is_empty())
        .map(|l| l.to_string())
        .collect())
}

/// Native folder picker (the settings "..." buttons).
#[tauri::command]
async fn pick_folder(title: String, initial: String) -> Result<Option<String>, String> {
    blocking(move || pick_folder_impl(title, initial)).await
}

/// Native folder picker (the settings "..." buttons): rfd renders the
/// STANDARD Windows folder dialog (IFileOpenDialog + FOS_PICKFOLDERS:
/// address bar, flat places, New folder). The PowerShell
/// FolderBrowserDialog's Win11 tree render was rejected by the author
/// ("ce truc de merde"). SelectedPath equivalent = set_directory opens
/// the picker AT the folder already configured.
fn pick_folder_impl(title: String, initial: String) -> Result<Option<String>, String> {
    let mut dialog = rfd::FileDialog::new().set_title(&title);
    if !initial.is_empty() {
        dialog = dialog.set_directory(&initial);
    }
    Ok(dialog.pick_folder().map(|p| p.to_string_lossy().into_owned()))
}

// ------------------------------------------------------------- settings

#[tauri::command]
async fn get_config() -> Result<serde_json::Value, String> {
    blocking(get_config_impl).await
}

fn get_config_impl() -> Result<serde_json::Value, String> {
    Ok(read_config().unwrap_or(serde_json::json!({})))
}

/// Merge the incoming keys over the existing file, never dropping the
/// keys the window does not manage (same as the desktop's save).
#[tauri::command]
async fn save_config(
    state: State<'_, AppState>,
    config: serde_json::Value,
) -> Result<(), String> {
    let st = state.inner().clone();
    blocking(move || save_config_impl(&st, config)).await
}

fn save_config_impl(state: &AppState, config: serde_json::Value) -> Result<(), String> {
    // A language change + a running engine = restart, exactly like the
    // desktop (SettingsChanged -> RestartServerAsync): the engine reads
    // `language` from config AT BOOT ONLY, and the UI's get_state poll
    // re-adopts info.lang every round - without a restart the next poll
    // silently REVERTS the UI to the old language ("1 second of French,
    // then back to English"). The theme-only save path never sends a
    // language key, so a theme flip never restarts the server.
    let new_lang = config
        .get("language")
        .and_then(|v| v.as_str())
        .map(str::to_string);
    let mut restart = false;
    if let Some(new_lang) = &new_lang {
        let info = state.info.lock().unwrap().clone();
        if let Some(i) = info {
            restart = i.lang != *new_lang;
        }
    }

    let mut existing = read_config().unwrap_or(serde_json::json!({}));
    if let (Some(dst), Some(src)) = (existing.as_object_mut(), config.as_object()) {
        for (k, v) in src {
            dst.insert(k.clone(), v.clone());
        }
    }
    let dir = config_dir();
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    std::fs::write(
        dir.join("config.json"),
        serde_json::to_string_pretty(&existing).map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;

    if restart {
        // Same control serialization as server_control. info is cleared
        // FIRST so get_state reports running:false for the window: the
        // UI only adopts info.lang while running, so it keeps the new
        // language instead of flickering back during the respawn.
        let _serial = state.control.lock().unwrap();
        if let Some(mut child) = state.engine.lock().unwrap().take() {
            let _ = child.kill();
        }
        *state.info.lock().unwrap() = None;
        std::thread::sleep(Duration::from_millis(300));
        let info = spawn_engine(state, false)?;
        *state.info.lock().unwrap() = Some(info);
    }
    Ok(())
}

// -------------------------------------------------------------- devices

#[tauri::command]
async fn get_devices(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    let st = state.inner().clone();
    blocking(move || get_devices_impl(&st)).await
}

fn get_devices_impl(state: &AppState) -> Result<serde_json::Value, String> {
    let info = base(state)?;
    let url = format!("https://{}:{}/api/devices?token={}", info.ip, info.port, info.token);
    let r = http().get(&url).send().map_err(|e| format!("devices: {e}"))?;
    let st = r.status();
    if !st.is_success() {
        // The engine's error bodies are JSON too: parsing a 429 (rate
        // limit) or 401 as the payload would silently hand the UI an
        // empty device_token - the token field's "blink".
        return Err(format!("devices: HTTP {st}"));
    }
    r.json().map_err(|e| format!("devices json: {e}"))
}

#[tauri::command]
async fn device_action(
    state: State<'_, AppState>,
    action: String,
    ip: String,
) -> Result<serde_json::Value, String> {
    let st = state.inner().clone();
    blocking(move || device_action_impl(&st, action, ip)).await
}

fn device_action_impl(
    state: &AppState,
    action: String,
    ip: String,
) -> Result<serde_json::Value, String> {
    let info = base(state)?;
    let url = match action.as_str() {
        "reset" => format!("https://{}:{}/api/device/reset?token={}", info.ip, info.port, info.token),
        "dissociate" => format!(
            "https://{}:{}/api/device/dissociate?token={}&ip={}",
            info.ip, info.port, info.token, ip
        ),
        other => return Err(format!("unknown device action: {other}")),
    };
    let r = http().post(&url).send().map_err(|e| format!("device action: {e}"))?;
    let st = r.status();
    if !st.is_success() {
        return Err(format!("device action: HTTP {st}"));
    }
    r.json().map_err(|e| format!("device json: {e}"))
}

/// Update check against the same release feed as UpdateService.cs, plus
/// what the flow needs to jump straight to installing: the Windows setup
/// asset, the finished installer and the partial download (resume).
#[derive(serde::Serialize)]
struct UpdateCheck {
    status: String, // uptodate | available | error
    version: String,
    current: String,
    asset_url: String,
    /// GitHub's `sha256:<hex>` for the chosen asset: the UI shows it and
    /// the install is refused without it.
    digest: String,
    installer: String, // path when the setup is already downloaded
    part_bytes: u64,   // bytes already on disk (the bar starts here)
}

/// Live state of the update download, mirrored to the UI by the
/// `update-progress` event (and read back by update_status on reload).
#[derive(Clone, Default, serde::Serialize)]
struct UpdatePhase {
    phase: String, // idle | downloading | done | error
    tag: String,
    downloaded: u64,
    total: u64,
    error: String,
    installer: String,
}

#[tauri::command]
async fn check_updates(
    current: String,
    state: State<'_, AppState>,
) -> Result<UpdateCheck, String> {
    let st = state.inner().clone();
    blocking(move || check_updates_impl(st, current)).await
}

fn check_updates_impl(st: AppState, current: String) -> Result<UpdateCheck, String> {
    let r = http()
        .get("https://api.github.com/repos/lucas31Zz/opendrop/releases/latest")
        .header("User-Agent", "opendrop")
        .send()
        .map_err(|e| format!("updates: {e}"))?;
    let v: serde_json::Value = r.json().map_err(|e| format!("updates json: {e}"))?;
    // Only `vX.Y.Z` is installable: a draft, prerelease or otherwise odd
    // tag must never reach the download-and-run path.
    let raw = v["tag_name"].as_str().unwrap_or("").trim();
    if !updater::is_release_tag(raw) {
        return Err("release tag is not vX.Y.Z".into());
    }
    let tag = raw.trim_start_matches('v').to_string();
    // The asset for THIS OS - .exe (then .msi) on Windows, the tarball on
    // Linux - never "first asset wins": the release also ships a zip.
    let (asset_url, ext) =
        updater::pick_asset(&v["assets"].to_string(), cfg!(target_os = "linux"))
            .map_err(|e| format!("updates: {e}"))?;
    // Its digest, looked up on the chosen asset: a release without one is
    // refused (Avalonia parity) because the download could never be
    // verified before being executed.
    let digest = v["assets"]
        .as_array()
        .and_then(|list| {
            list.iter()
                .find(|a| a["browser_download_url"].as_str() == Some(asset_url.as_str()))
        })
        .and_then(|a| a["digest"].as_str())
        .unwrap_or("")
        .to_string();
    if digest.is_empty() {
        return Err("release asset has no sha256 digest".into());
    }
    // Remembered for both `done` gates (start_update shortcut and the
    // download worker): the file is only ever handed over after hashing
    // to exactly this value.
    *st.update_meta.lock().unwrap() = Some((tag.clone(), digest.clone()));
    let (installer, part) = installer_paths(&tag, ext.trim_start_matches('.'));
    Ok(UpdateCheck {
        status: if tag == current { "uptodate".into() } else { "available".into() },
        version: tag.clone(),
        current,
        asset_url,
        digest,
        installer: if installer.is_file() {
            installer.display().to_string()
        } else {
            String::new()
        },
        part_bytes: std::fs::metadata(&part).map(|m| m.len()).unwrap_or(0),
    })
}

/// %TEMP%\opendrop-update-{tag}.{ext}: the finished installer and its
/// `.part` (kept across sessions - a resumed download restarts the bar
/// at whatever was already fetched).
fn installer_paths(tag: &str, ext: &str) -> (PathBuf, PathBuf) {
    let base = std::env::temp_dir().join(format!("opendrop-update-{tag}.{ext}"));
    let mut part = base.as_os_str().to_owned();
    part.push(".part");
    (base, PathBuf::from(part))
}

/// Extension for the download file name, from the URL's last segment.
/// The Linux tarball is a compound extension (`.tar.gz`), which a plain
/// "after the last dot" split would cut down to `gz`.
fn asset_ext(url: &str) -> String {
    let seg = url.rsplit('/').next().unwrap_or("").to_ascii_lowercase();
    if seg.ends_with(".tar.gz") {
        return "tar.gz".into();
    }
    let ext = seg.rsplit('.').next().unwrap_or("");
    if !ext.is_empty() && ext.len() <= 6 && ext.chars().all(|c| c.is_ascii_alphanumeric()) {
        ext.to_string()
    } else {
        "exe".into()
    }
}

/// Begin (or join) the installer download. It streams on a plain thread
/// - one long body would sit on the blocking pool forever - and emits
/// `update-progress` every ~120 ms.
#[tauri::command]
async fn start_update_download(
    tag: String,
    url: String,
    state: State<'_, AppState>,
    app: tauri::AppHandle,
) -> Result<UpdatePhase, String> {
    let st = state.inner().clone();
    blocking(move || start_update_impl(st, app, tag, url)).await
}

fn start_update_impl(
    st: AppState,
    app: tauri::AppHandle,
    tag: String,
    url: String,
) -> Result<UpdatePhase, String> {
    if url.trim().is_empty() {
        return Err("no installer asset in this release".into());
    }
    let (final_path, part_path) = installer_paths(&tag, &asset_ext(&url));
    // The digest check_updates recorded for this release. Both `done`
    // gates below hash the file against it before it may run.
    let digest = st
        .update_meta
        .lock()
        .unwrap()
        .as_ref()
        .map(|(_, d)| d.clone())
        .unwrap_or_default();
    if final_path.is_file() {
        // Already downloaded (previous session or earlier attempt): it
        // still has to match the release digest - a file left behind by
        // an interrupted or tampered download must not be executed.
        if let Err(e) = updater::verify_sha256(&final_path, &digest) {
            let _ = std::fs::remove_file(&final_path);
            let mut p = st.update.lock().unwrap();
            p.phase = "error".into();
            p.tag = tag;
            p.error = e;
            p.installer = String::new();
            return Ok(p.clone());
        }
        // Verified: the UI goes straight to the administrator check.
        let mut p = st.update.lock().unwrap();
        p.phase = "done".into();
        p.tag = tag;
        p.installer = final_path.display().to_string();
        return Ok(p.clone());
    }
    {
        let mut p = st.update.lock().unwrap();
        if p.phase == "downloading" && p.tag == tag {
            return Ok(p.clone()); // a download is already running: join it
        }
        p.phase = "downloading".into();
        p.tag = tag.clone();
        p.downloaded = std::fs::metadata(&part_path).map(|m| m.len()).unwrap_or(0);
        p.total = 0;
        p.error = String::new();
        p.installer = String::new();
    }
    let phase = st.update.clone();
    std::thread::spawn(move || download_worker(app, phase, url, final_path, part_path, digest));
    Ok(st.update.lock().unwrap().clone())
}

/// The download's thread: stream to the `.part`, rename it when whole,
/// verify it against the release digest, and only then call it done.
fn download_worker(
    app: tauri::AppHandle,
    phase: Arc<Mutex<UpdatePhase>>,
    url: String,
    final_path: PathBuf,
    part_path: PathBuf,
    digest: String,
) {
    let emit = |phase: &Arc<Mutex<UpdatePhase>>| {
        let snapshot = phase.lock().unwrap().clone();
        let _ = app.emit("update-progress", snapshot);
    };
    match download_body(&app, &phase, &url, &part_path) {
        Ok(()) => match std::fs::rename(&part_path, &final_path) {
            // Second `done` gate: the bytes on disk must hash to the
            // digest GitHub published for this asset. A mismatch deletes
            // the file, so a truncated or tampered download can never be
            // handed to the installer.
            Ok(()) => match updater::verify_sha256(&final_path, &digest) {
                Ok(()) => {
                    let mut p = phase.lock().unwrap();
                    p.phase = "done".into();
                    p.installer = final_path.display().to_string();
                    drop(p);
                    emit(&phase);
                }
                Err(e) => {
                    let _ = std::fs::remove_file(&final_path);
                    let mut p = phase.lock().unwrap();
                    p.phase = "error".into();
                    p.error = e;
                    p.installer = String::new();
                    drop(p);
                    emit(&phase);
                }
            },
            Err(e) => {
                let mut p = phase.lock().unwrap();
                p.phase = "error".into();
                p.error = format!("finalize: {e}");
                drop(p);
                emit(&phase);
            }
        },
        Err(e) => {
            let mut p = phase.lock().unwrap();
            p.phase = "error".into();
            p.error = e;
            drop(p);
            emit(&phase);
        }
    }
}

fn download_body(
    app: &tauri::AppHandle,
    phase: &Arc<Mutex<UpdatePhase>>,
    url: &str,
    part_path: &Path,
) -> Result<(), String> {
    use std::io::{Read, Write};
    let existing = std::fs::metadata(part_path).map(|m| m.len()).unwrap_or(0);
    let mut req = http_dl().get(url);
    if existing > 0 {
        req = req.header("Range", format!("bytes={existing}-"));
    }
    let mut resp = req.send().map_err(|e| format!("download: {e}"))?;
    let status = resp.status();
    // 206 = our bytes are still good (resume); a plain 200 restarts the
    // file from scratch even when a stale `.part` is lying around.
    let resumed = if status.as_u16() == 206 {
        true
    } else if status.is_success() {
        if existing > 0 {
            let _ = std::fs::remove_file(part_path);
        }
        false
    } else {
        return Err(format!("download: HTTP {status}"));
    };
    let base = if resumed { existing } else { 0 };
    let content = resp.content_length().unwrap_or(0);
    {
        let mut p = phase.lock().unwrap();
        p.downloaded = base;
        p.total = if resumed { base + content } else { content };
    }
    let snapshot = phase.lock().unwrap().clone();
    let _ = app.emit("update-progress", snapshot);

    let mut file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(part_path)
        .map_err(|e| format!("download open: {e}"))?;
    let mut buf = vec![0u8; 64 * 1024];
    let mut last = std::time::Instant::now();
    loop {
        let n = resp.read(&mut buf).map_err(|e| format!("download read: {e}"))?;
        if n == 0 {
            break;
        }
        file.write_all(&buf[..n]).map_err(|e| format!("download write: {e}"))?;
        phase.lock().unwrap().downloaded += n as u64;
        if last.elapsed() >= Duration::from_millis(120) {
            last = std::time::Instant::now();
            let snapshot = phase.lock().unwrap().clone();
            let _ = app.emit("update-progress", snapshot);
        }
    }
    file.flush().map_err(|e| format!("download flush: {e}"))?;
    let snapshot = phase.lock().unwrap().clone();
    let _ = app.emit("update-progress", snapshot);
    Ok(())
}

/// Phase for the UI to re-sync with after a reload (the download thread
/// lives in Rust, not in the page).
#[tauri::command]
async fn update_status(state: State<'_, AppState>) -> Result<UpdatePhase, String> {
    Ok(state.update.lock().unwrap().clone())
}

/// Hand the finished package to the OS installer: Windows elevates via
/// `runas` (declining comes back as a non-zero exit), Linux unpacks the
/// tarball and runs its install.sh under pkexec.
#[tauri::command]
async fn launch_installer(path: String, state: State<'_, AppState>) -> Result<(), String> {
    let st = state.inner().clone();
    blocking(move || launch_installer_impl(st, path)).await
}

/// THE last gate. The UI has two ways to reach an installer - a finished
/// download, or the "already on disk" path check_updates reported - and
/// the second one used to jump straight here, past the download gates.
/// Whatever route brought us to this path, the bytes must hash to the
/// digest of the release being installed before anything is executed.
fn launch_installer_impl(st: AppState, path: String) -> Result<(), String> {
    if !Path::new(&path).is_file() {
        return Err("installer not found".into());
    }
    let digest = st
        .update_meta
        .lock()
        .unwrap()
        .as_ref()
        .map(|(_, d)| d.clone())
        .unwrap_or_default();
    if let Err(e) = updater::verify_sha256(Path::new(&path), &digest) {
        let _ = std::fs::remove_file(&path);
        return Err(e);
    }
    run_installer(&path)
}

/// Windows: `runas` raises the administrator check; declining it comes
/// back as a non-zero exit.
#[cfg(not(target_os = "linux"))]
fn run_installer(path: &str) -> Result<(), String> {
    let quoted = path.replace('\'', "''");
    let out = Command::new("powershell")
        .args([
            "-NoProfile",
            "-Command",
            &format!("Start-Process -FilePath '{quoted}' -Verb runas"),
        ])
        .output()
        .map_err(|e| format!("launch: {e}"))?;
    if out.status.success() {
        Ok(())
    } else {
        let err = String::from_utf8_lossy(&out.stderr);
        Err(if err.trim().is_empty() {
            "launch: elevation was declined".into()
        } else {
            format!("launch: {}", err.trim())
        })
    }
}

/// Linux install: unpack the release tarball into a temp dir, then run
/// the bundle's own `OpenDrop/install.sh` through pkexec (it writes the
/// system locations, so it needs the admin prompt - the same hand-off the
/// pre-1.0 app made). A missing tool, a failed extract or a non-zero
/// exit is an `Err`, never a panic.
#[cfg(target_os = "linux")]
fn run_installer(path: &str) -> Result<(), String> {
    let archive = Path::new(path);
    let dir = std::env::temp_dir().join(format!("opendrop-update-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).map_err(|e| format!("extract: {e}"))?;
    // `tar` missing (minimal distros) surfaces as a spawn error, not a
    // crash; build-tarball.sh stages the payload as `OpenDrop/...`.
    let status = Command::new("tar")
        .arg("-xzf")
        .arg(archive)
        .arg("-C")
        .arg(&dir)
        .status()
        .map_err(|e| format!("tar: {e}"))?;
    if !status.success() {
        return Err(format!("tar: {status}"));
    }
    let script = dir.join("OpenDrop").join("install.sh");
    if !script.is_file() {
        return Err(format!("install.sh missing from {}", archive.display()));
    }
    let status = Command::new("pkexec")
        .arg(&script)
        .status()
        .map_err(|e| format!("pkexec: {e}"))?;
    if status.success() {
        Ok(())
    } else {
        Err(format!("install.sh: {status}"))
    }
}

// --------------------------------------------------------------- storage

/// Recurse a folder and sum the file sizes (QuotaUsage.ScanDirectory).
fn dir_size(dir: &Path) -> u64 {
    let mut total = 0u64;
    if let Ok(entries) = std::fs::read_dir(dir) {
        for entry in entries.flatten() {
            let Ok(meta) = entry.metadata() else { continue };
            if meta.is_file() {
                total += meta.len();
            } else if meta.is_dir() {
                total += dir_size(&entry.path());
            }
        }
    }
    total
}

/// The quota card data while the engine is stopped: the desktop scans the
/// download folder itself (QuotaUsage.ScanDirectory + ReadLimit), so the
/// numbers stay real with no server behind them. An optional `dir` lets
/// the settings window preview any folder without saving it first.
#[tauri::command]
async fn local_quota(dir: Option<String>) -> Result<serde_json::Value, String> {
    blocking(move || local_quota_impl(dir)).await
}

fn local_quota_impl(dir: Option<String>) -> Result<serde_json::Value, String> {
    let config = read_config().unwrap_or_else(|_| serde_json::json!({}));
    let dir = dir
        .filter(|d| !d.trim().is_empty())
        .or_else(|| {
            config
                .get("download_directory")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string())
        });
    let limit = config
        .get("global_quota_bytes")
        .and_then(|v| v.as_i64())
        .unwrap_or(0);
    let usage = dir.as_deref().map(|d| dir_size(Path::new(d))).unwrap_or(0);
    Ok(serde_json::json!({ "usage_bytes": usage, "limit_bytes": limit }))
}

/// Free bytes on the drive that holds `path` (DriveInfo.AvailableFreeSpace,
/// the settings quota warning: above 20% of the free space the desktop
/// asks before saving). Unknown = 0 = no warning.
#[tauri::command]
async fn free_space(path: String) -> Result<u64, String> {
    blocking(move || free_space_impl(path)).await
}

fn free_space_impl(path: String) -> Result<u64, String> {
    let root = Path::new(&path)
        .components()
        .next()
        .map(|c| c.as_os_str().to_string_lossy().to_string())
        .unwrap_or_else(|| "C:\\".into());
    let script = format!(
        "$r = [System.IO.Path]::GetPathRoot('{}'); \
         if ([string]::IsNullOrEmpty($r)) {{ '0' }} \
         else {{ (New-Object System.IO.DriveInfo $r).AvailableFreeSpace }}",
        root.replace('\'', "''")
    );
    let out = Command::new("powershell")
        .args(["-NoProfile", "-Command", &script])
        .output()
        .map_err(|e| format!("free space: {e}"))?;
    String::from_utf8_lossy(&out.stdout)
        .trim()
        .parse::<u64>()
        .map_err(|e| format!("free space parse: {e}"))
}

// -------------------------------------------------------- tray + quit

/// Tray icon id. With a tray icon, closing the window only HIDES it and
/// the engine keeps running (the desktop's cancelled `Closing`); if tray
/// creation failed this stays false and close falls back to a real close
/// (the desktop's `_trayIcon == null` case).
static TRAY_OK: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);

const TRAY_ID: &str = "main-tray";

/// Bring the (possibly hidden) main window back to the front: tray click,
/// tray "Show" item, and the hand-off of a second launch (the desktop's
/// `ShowFromTray`).
fn show_main_window(app: &tauri::AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.show();
        let _ = w.unminimize();
        let _ = w.set_focus();
    }
}

fn build_tray_menu(
    app: &tauri::AppHandle,
    show: &str,
    quit: &str,
) -> tauri::Result<Menu<tauri::Wry>> {
    let show_i = MenuItem::with_id(app, "tray-show", show, true, None::<&str>)?;
    let quit_i = MenuItem::with_id(app, "tray-quit", quit, true, None::<&str>)?;
    Menu::with_items(app, &[&show_i, &PredefinedMenuItem::separator(app)?, &quit_i])
}

/// Menu labels come from the frontend (`strings.ts` via the
/// `set_tray_labels` command, pushed on mount and on every language
/// change). The tray exposes no menu getter, so rebuild the menu with the
/// new text - tray-level event handlers stay attached.
fn apply_tray_labels(app: &tauri::AppHandle, show: &str, quit: &str) {
    let Some(tray) = app.tray_by_id(TRAY_ID) else { return };
    if let Ok(menu) = build_tray_menu(app, show, quit) {
        let _ = tray.set_menu(Some(menu));
    }
}

/// Frontend -> tray menu language. Menus are main-thread objects: queue
/// the rebuild there.
#[tauri::command]
async fn set_tray_labels(app: tauri::AppHandle, show: String, quit: String) -> Result<(), String> {
    let handle = app.clone();
    app.run_on_main_thread(move || apply_tray_labels(&handle, &show, &quit))
        .map_err(|e| e.to_string())
}

/// Labels used until React pushes the real ones (a few hundred ms): FR
/// unless config.json explicitly asks for EN, like the desktop default.
fn boot_tray_labels() -> (String, String) {
    let fr = read_config()
        .ok()
        .and_then(|c| {
            c.get("language")
                .and_then(|v| v.as_str())
                .map(str::to_string)
        })
        .map(|l| l != "en")
        .unwrap_or(true);
    if fr {
        ("Afficher OpenDrop".into(), "Quitter OpenDrop".into())
    } else {
        ("Show OpenDrop".into(), "Quit OpenDrop".into())
    }
}

/// Real quit (tray menu "Quit"): kill the child engine first - the
/// desktop's `Closed -> _serverManager.Stop()` - then leave. Closing the
/// window never reaches this: it only hides.
fn quit_app(app: &tauri::AppHandle) {
    if let Some(state) = app.try_state::<AppState>() {
        if let Ok(mut engine) = state.engine.lock() {
            if let Some(mut child) = engine.take() {
                let _ = child.kill();
            }
        }
    }
    app.exit(0);
}

/// Tray icon + menu. Left click / "Show" reopens the window, right click
/// opens the menu, "Quit" is the only path that stops the server.
fn setup_tray(app: &tauri::AppHandle) -> tauri::Result<()> {
    let (show_label, quit_label) = boot_tray_labels();
    let menu = build_tray_menu(app, &show_label, &quit_label)?;
    let Some(icon) = app.default_window_icon().cloned() else {
        // No icon to draw (the desktop's try/catch around SetupTray):
        // close stays a real close.
        return Ok(());
    };
    TrayIconBuilder::with_id(TRAY_ID)
        .icon(icon)
        .tooltip("OpenDrop")
        .menu(&menu)
        // Right click opens the menu, left click shows the window.
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id().as_ref() {
            "tray-show" => show_main_window(app),
            "tray-quit" => quit_app(app),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if matches!(
                event,
                TrayIconEvent::Click {
                    button: MouseButton::Left,
                    button_state: MouseButtonState::Up,
                    ..
                }
            ) {
                show_main_window(tray.app_handle());
            }
        })
        .build(app)?;
    TRAY_OK.store(true, std::sync::atomic::Ordering::Relaxed);
    Ok(())
}

fn main() {
    let state = AppState {
        engine: Arc::new(Mutex::new(None)),
        info: Arc::new(Mutex::new(None)),
        control: Arc::new(Mutex::new(())),
        port_busy: Arc::new(Mutex::new(None)),
        update: Arc::new(Mutex::new(UpdatePhase::default())),
        update_meta: Arc::new(Mutex::new(None)),
    };
    let boot_state = state.clone();

    tauri::Builder::default()
        // FIRST plugin: a second launch on this machine is detected during
        // plugin init and exits there - before the engine boot below (which
        // would otherwise reap_orphan() the FIRST instance's engine) and
        // before any window exists. Its hand-off re-shows our window.
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            show_main_window(app);
        }))
        .manage(state)
        .on_window_event(|window, event| {
            // Close button = hide to tray, the engine keeps running (the
            // desktop's cancelled `Closing`). Real quit = tray "Quit".
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                if TRAY_OK.load(std::sync::atomic::Ordering::Relaxed) {
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            engine_info, get_state, upload_file, open_url, get_qr,
            server_control, open_path, copy_text, list_files, rename_file,
            delete_files, put_back, import_files, pick_files, pick_folder,
            get_config, save_config, get_devices, device_action, check_updates,
            local_quota, free_space, kill_holder,
            start_update_download, update_status, launch_installer,
            set_tray_labels
        ])
        .setup(move |app| {
            // Start the real engine BEFORE the window is created so the UI
            // has data on first paint. A busy configured port must NOT
            // panic the app: spawn_engine already recorded who holds the
            // port, so the window opens on {running:false, port_busy:...}.
            // This runs inside setup (not before the Builder) so a second
            // instance - already gone by plugin init - never reaps or
            // spawns an engine of its own.
            reap_orphan(); // any engine orphaned by the previous app run
            std::thread::sleep(Duration::from_millis(300));
            match spawn_engine(&boot_state, false) {
                Ok(info) => *boot_state.info.lock().unwrap() = Some(info),
                Err(e) => eprintln!("[engine] boot failed: {e}"),
            }

            let handle = app.handle();
            setup_tray(handle)?;

            // The window is kept out of the auto-create pass
            // (tauri.conf.json: create:false) so it only appears once the
            // engine is up, exactly like the boot order this had before.
            let window_config = app
                .config()
                .app
                .windows
                .iter()
                .find(|w| w.label == "main")
                .cloned()
                .ok_or("main window config missing")?;
            tauri::WebviewWindowBuilder::from_config(handle, &window_config)?.build()?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
