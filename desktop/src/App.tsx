// The app shell rebuilt as a local web app: the desktop's
// MainWindow layout (blocks 1-8), driven by the REAL Python engine that
// the Rust side spawns. Every button acts on the real thing.
import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { Msg, MsgHost } from "./Msg";
import { SharedFiles } from "./components/SharedFiles";
import { Settings, type SettingsConfig } from "./components/Settings";
import { WhatsNew } from "./components/WhatsNew";
import Combo from "./components/Combo";
import TitleBar from "./components/TitleBar";
import { copyToClipboard } from "./clipboard";
import { Copy, ExternalLink, FolderOpen, Play, RotateCcw, Settings as SettingsIcon, Square } from "lucide-react";
import { formatBytes, makeT, type Lang, type StringKey, type T } from "./strings";
import { listen } from "@tauri-apps/api/event";
import { UpdateToast, type ToastView } from "./UpdateToast";
import {
  IDLE_UPDATE,
  dismissedKey,
  type UpdateCheckR,
  type UpdatePhase,
} from "./update";

// Real invite from the pre-1.0 Avalonia app (DiscordInviteUrl).
const DISCORD_INVITE = "https://discord.gg/vREBPZuvhV";

// The Discord path, verbatim from the pre-1.0 Avalonia app (Path Data).
const DISCORD_PATH =
  "M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.157 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189Z";

const WORDMARK = "OPENDROP".split("");

// The desktop's TokenIntervalCombo values, in seconds.
const TOKEN_INTERVALS = [0, 300, 900, 1800, 3600];
const TOKEN_LABELS: StringKey[] = [
  "Token.Never",
  "Token.5m",
  "Token.15m",
  "Token.30m",
  "Token.1h",
];

type EngineInfo = {
  ip: string;
  port: number;
  token: string;
  session_code: string;
  url_upload: string;
  lang: string;
  version: string;
  download_dir: string;
  share_dir: string;
};

type Bundle = {
  running: boolean;
  info?: EngineInfo;
  api_info?: Record<string, unknown>;
  quota?: { usage_bytes?: number; limit_bytes?: number };
  files?: unknown;
  device?: Record<string, unknown>;
  /** Set while stopped: who holds the configured port (spawn failed). */
  port_busy?: { port: number; pid: number; name: string; path: string } | null;
};

type QuotaInfo = { usage_bytes?: number; limit_bytes?: number };

/** Token.Refresh countdown: "1h00min" from an hour, "5min00s" below. */
function formatCountdown(total: number, t: T): string {
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const body =
    h >= 1
      ? `${h}h${String(m).padStart(2, "0")}min`
      : `${m}min${String(s).padStart(2, "0")}s`;
  return `${t("Token.NextRefresh")} ${body}`;
}

export default function App() {
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [err, setErr] = useState("");
  const [qrDataUrl, setQrDataUrl] = useState("");
  const [qrGenerating, setQrGenerating] = useState(false);
  const [lang, setLang] = useState<Lang>("en");
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [tokenIdx, setTokenIdx] = useState(0);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsChanged, setSettingsChanged] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [copied, setCopied] = useState(false);
  const [quota, setQuota] = useState<QuotaInfo | null>(null);
  // Update flow: the check reply, the download mirror and which face of
  // the bottom-right toast is showing (UpdateToast's state machine).
  const [updCheck, setUpdCheck] = useState<UpdateCheckR | null>(null);
  const [updPhase, setUpdPhase] = useState<UpdatePhase>(IDLE_UPDATE);
  const [toast, setToast] = useState<ToastView>("hidden");
  const [toastErr, setToastErr] = useState("");

  const t = makeT(lang);
  const copiedTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const rotating = useRef(false);
  const settingsConfig = useRef<SettingsConfig>({});
  const qrUrl = useRef("");
  const bootChecked = useRef(false);
  const toastRef = useRef<ToastView>("hidden");
  const launchedRef = useRef("");
  const setToastView = (v: ToastView) => {
    toastRef.current = v;
    setToast(v);
  };

  // The wordmark and the aurora belong to the window, not to a card.
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  // The tray menu is native (Rust), its labels live in strings.ts: push
  // them on mount and on every language change, like the desktop's
  // ApplyTrayStrings. No tray (or a failed rebuild) just no-ops.
  useEffect(() => {
    const tt = makeT(lang);
    invoke("set_tray_labels", { show: tt("Tray.Show"), quit: tt("Tray.Quit") }).catch(() => {});
  }, [lang]);

  // No browser context menu: this is an app, not a page. Right-click
  // answers nothing anywhere except in text fields, which keep the
  // native edit menu (cut/copy/paste), like a real desktop app.
  useEffect(() => {
    const block = (e: MouseEvent) => {
      const el = e.target as HTMLElement | null;
      if (el?.closest("input, textarea, [contenteditable='true']")) return;
      e.preventDefault();
    };
    window.addEventListener("contextmenu", block);
    return () => window.removeEventListener("contextmenu", block);
  }, []);

  const load = useCallback(async () => {
    try {
      const s = await invoke<Bundle>("get_state");
      setBundle(s);
      setErr("");
      if (s.running && s.info) {
        if (s.info.lang === "fr" || s.info.lang === "en") setLang(s.info.lang);
        // QR for the upload URL: the same image the engine hands to the
        // phone page (GET /qr), cached while the URL does not change.
        const url = s.info.url_upload;
        if (url && url !== qrUrl.current) {
          try {
            const bytes = await invoke<number[]>("get_qr");
            const bin = new Uint8Array(bytes);
            let raw = "";
            for (let i = 0; i < bin.length; i += 0x8000) {
              raw += String.fromCharCode(...bin.subarray(i, i + 0x8000));
            }
            qrUrl.current = url;
            setQrDataUrl(`data:image/png;base64,${btoa(raw)}`);
          } catch {
            setQrDataUrl("");
          }
        }
      } else {
        qrUrl.current = "";
        setQrDataUrl("");
      }
    } catch (e) {
      setErr(String(e));
    }
  }, []);

  // The desktop polls every 2 s and re-reads the quota on the same tick;
  // the quota card is a local disk scan there (QuotaUsage), so it stays
  // real even with the engine stopped.
  const loadQuota = useCallback(async () => {
    try {
      const q = await invoke<QuotaInfo>("local_quota", { dir: null });
      setQuota(q);
    } catch {
      /* keep the last known numbers */
    }
  }, []);

  useEffect(() => {
    void load();
    void loadQuota();
  }, [load, loadQuota]);

  // 4 s, not 2 s: this poll costs FOUR /api requests (info, quota,
  // files, device status) and the engine allows 120 req/min per IP
  // (limiter_general). 2 s sat exactly AT the budget before any other
  // call - bursts tipped it into 429s the UI used to swallow.
  useEffect(() => {
    const id = setInterval(() => {
      void load();
      void loadQuota();
    }, 4000);
    return () => clearInterval(id);
  }, [load, loadQuota]);

  // Language and theme also come from config while the engine is down.
  useEffect(() => {
    void (async () => {
      try {
        const c = await invoke<SettingsConfig>("get_config");
        settingsConfig.current = c;
        if (c.language === "fr" || c.language === "en") setLang(c.language);
        if (c.theme === "light" || c.theme === "dark") setTheme(c.theme);
      } catch {
        /* defaults stay */
      }
    })();
  }, []);

  const running = !!bundle?.running;
  const info = bundle?.info ?? null;
  // Who holds the configured port while the engine could not start it.
  const portBusy = running ? null : bundle?.port_busy ?? null;

  // Boot update check: one shot after the first get_state, so `current`
  // is the engine's real version (empty while stopped - the known P3-3
  // shortcut is also what makes the flow triggerable on demand). An
  // already refused tag stays silent; a fresh update raises the
  // bottom-right toast.
  useEffect(() => {
    if (!bundle || bootChecked.current) return;
    bootChecked.current = true;
    void (async () => {
      try {
        const st = await invoke<UpdatePhase>("update_status");
        if (st.phase === "downloading") {
          // A download survived a reload: the toast goes back on its bar.
          setUpdPhase(st);
          setToastView("downloading");
        }
      } catch {
        /* no update thread yet: fall through to the check */
      }
      try {
        const r = await invoke<UpdateCheckR>("check_updates", {
          current: bundle?.info?.version ?? "",
        });
        setUpdCheck(r);
        if (
          r.status === "available" &&
          toastRef.current === "hidden" &&
          localStorage.getItem(dismissedKey(r.version)) !== "1"
        ) {
          setToastView("prompt");
        }
      } catch {
        /* offline: the update flow stays quiet */
      }
    })();
  }, [bundle]);

  // The download's events: every state flip of the flow, and the ONE
  // auto-install - a download accepted this session launches the setup
  // as soon as it is whole (no second question, per the spec).
  useEffect(() => {
    let unbind: (() => void) | undefined;
    void listen<UpdatePhase>("update-progress", (ev) => {
      const p = ev.payload;
      setUpdPhase(p);
      if (p.phase === "downloading" && toastRef.current === "hidden") {
        setToastView("downloading");
      }
      if (p.phase === "done") {
        if (
          toastRef.current === "downloading" &&
          launchedRef.current !== p.installer
        ) {
          launchedRef.current = p.installer;
          setToastView("installing");
          void (async () => {
            try {
              await invoke("launch_installer", { path: p.installer });
            } catch (e) {
              setToastErr(t("Up.InstallError", String(e)));
              setToastView("error");
            }
          })();
        } else if (toastRef.current === "downloading") {
          setToastView("installing");
        }
      }
      if (p.phase === "error") {
        setToastErr(t("Up.DownloadError", p.error || "?"));
        setToastView("error");
      }
    }).then((u) => {
      unbind = u;
    });
    return () => unbind?.();
    // t only feeds the error labels; the listener itself never changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // One acceptance = start the stream (or launch a setup already on
  // disk); the toast follows from there. Shared by the boot toast and
  // the settings dialog.
  const acceptUpdate = useCallback(async () => {
    const c = updCheck;
    if (!c) return;
    try {
      if (c.installer) {
        launchedRef.current = c.installer;
        setToastView("installing");
        await invoke("launch_installer", { path: c.installer });
        return;
      }
      await invoke("start_update_download", { tag: c.version, url: c.asset_url });
      setToastView("downloading");
    } catch (e) {
      setToastErr(String(e));
      setToastView("error");
    }
  }, [updCheck]);

  const refuseUpdate = useCallback(() => {
    if (updCheck) {
      localStorage.setItem(dismissedKey(updCheck.version), "1");
    }
    setToastView("hidden");
  }, [updCheck]);

  // Token countdown: cleared by a stop, restarted on every start.
  useEffect(() => {
    if (!running) {
      setSecondsLeft(0);
      return;
    }
    const interval = TOKEN_INTERVALS[tokenIdx];
    if (interval <= 0) return;
    setSecondsLeft(interval);
    const id = setInterval(() => {
      setSecondsLeft((s) => {
        if (s <= 1) {
          // At zero: the only thing that changes the token, the QR and
          // the session code (RefreshTokenAsync, rotate).
          void rotate();
          return interval;
        }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [running, tokenIdx]);

  const rotate = useCallback(async () => {
    // Ignore a second click while a rotation is in flight: two racing
    // respawns are what left the QR on a stale token (see AppState).
    if (!running || rotating.current) return;
    rotating.current = true;
    setQrGenerating(true);
    try {
      const info2 = await invoke<EngineInfo | null>("server_control", {
        action: "rotate",
      });
      if (info2) qrUrl.current = "";
      await load();
      setRefreshKey((k) => k + 1);
      // A manual reset restarts the countdown, like the desktop
      // (BtnRefreshToken_Click sets _tokenSecondsLeft).
      setSecondsLeft(TOKEN_INTERVALS[tokenIdx]);
    } finally {
      rotating.current = false;
      setQrGenerating(false);
    }
  }, [load, running, tokenIdx]);

  const toggleServer = useCallback(async () => {
    try {
      if (running) {
        await invoke("server_control", { action: "stop" });
      } else {
        const info2 = await invoke<EngineInfo | null>("server_control", {
          action: "start",
        });
        if (!info2) {
          await Msg.show(t("Status.Error"), t("Err.CannotStart"), t);
        }
        qrUrl.current = "";
      }
      await load();
      setRefreshKey((k) => k + 1);
    } catch (e) {
      setErr(String(e));
      // The failing action was a stop when the server was running.
      await Msg.show(
        t("Status.Error"),
        running ? t("Err.CannotStop") : t("Err.CannotStart"),
        t,
      );
    }
  }, [load, running, t]);

  /// The configured port is held by another app: name it, then kill it
  /// and start the engine on the now-free port.
  const killAndStart = useCallback(async () => {
    if (!portBusy) return;
    const answer = await Msg.confirm(
      t("Port.KillTitle"),
      t("Port.KillBody", portBusy.name, String(portBusy.pid), String(portBusy.port)),
      t,
    );
    if (!answer) return;
    try {
      const freed = await invoke<boolean>("kill_holder");
      if (!freed) {
        await Msg.show(t("Status.Error"), t("Port.KillFailed", String(portBusy.port)), t);
        await load();
        return;
      }
      await invoke("server_control", { action: "start" });
      qrUrl.current = "";
    } catch (e) {
      setErr(String(e));
      await Msg.show(t("Status.Error"), t("Err.CannotStart"), t);
    }
    await load();
    setRefreshKey((k) => k + 1);
  }, [load, portBusy, t]);

  const flipTheme = useCallback(() => {
    setTheme((prev) => {
      const next = prev === "dark" ? "light" : "dark";
      // The desktop persists the lens flip as soon as it happens.
      void invoke("save_config", { config: { theme: next } }).catch(() => {});
      return next;
    });
  }, []);

  const copyCode = useCallback(async () => {
    if (!info?.session_code) return;
    await copyToClipboard(info.session_code);
    setCopied(true);
    if (copiedTimer.current) clearTimeout(copiedTimer.current);
    copiedTimer.current = setTimeout(() => setCopied(false), 1500);
  }, [info]);

  const openFolder = useCallback(
    async (dir: string) => {
      if (!dir) return;
      try {
        await invoke("open_path", { path: dir });
      } catch {
        await Msg.show(t("Label.Folders"), t("Folders.Missing", dir), t);
      }
    },
    [t],
  );

  // Re-read config at each open: a settings window must not show the
  // defaults just because it was opened before the first read returned.
  const openSettings = useCallback(async () => {
    try {
      settingsConfig.current = await invoke<SettingsConfig>("get_config");
    } catch {
      /* keep whatever we already hold */
    }
    setSettingsOpen(true);
  }, []);

  const closeSettings = useCallback(async () => {
    setSettingsOpen(false);
    if (settingsChanged) {
      // Save/quit: refresh everything, restart the server if it runs.
      if (running) {
        setQrGenerating(true);
        try {
          await invoke("server_control", { action: "start" });
          qrUrl.current = "";
        } catch {
          await Msg.show(t("Status.Error"), t("Err.CannotRestart"), t);
        } finally {
          setQrGenerating(false);
        }
      }
      setSettingsChanged(false);
      await load();
      await loadQuota();
      setRefreshKey((k) => k + 1);
    }
  }, [load, loadQuota, running, settingsChanged, t]);

  // ---------------------------------------------------------- quota card
  const usage = quota?.usage_bytes ?? 0;
  const limit = quota?.limit_bytes ?? 0;
  const unlimited = limit <= 0;
  const full = !unlimited && usage >= limit;
  const fillPct = unlimited ? 0 : Math.min(100, (usage / limit) * 100);
  const quotaText = unlimited
    ? t("Quota.Unlimited", formatBytes(usage, lang))
    : full
      ? t("Quota.UsageInFolder", formatBytes(usage, lang))
      : t("Quota.UsageInFolder", formatBytes(usage, lang));
  const quotaHint = full ? "hint-error" : "hint-muted";

  const statusClass = err
    ? "state-error"
    : running
      ? "state-running"
      : portBusy
        ? "state-error"
        : "state-stopped";
  const statusText = err
    ? t("Status.Error")
    : running
      ? t("Status.Running")
      : portBusy
        ? t("Status.PortBusy", String(portBusy.port))
        : t("Status.Stopped");

  return (
    <div className="relative h-full overflow-hidden">
      {/* Aurora: three soft blobs drifting behind everything, pure
          decoration (Brush.Aurora1/2/3 + the 12/14/13s drift). */}
      <div className="aurora aurora-1" />
      <div className="aurora aurora-2" />
      <div className="aurora aurora-3" />

      <div className="app-grid settle relative z-10 h-full">
        {/* ------------------------------------------------------ header */}
        {/* The header IS the title bar (no OS chrome, decorations:false):
            "deep" makes the whole band a drag region - buttons and
            inputs still block it (injected by Tauri, double-click
            maximizes). Air kept: the XAML strip is Marged 28,16,28,12
            above a content grid padded 24 on top. */}
        <header
          className="flex items-center justify-between px-7 pt-5 pb-3"
          data-tauri-drag-region="deep"
        >
          {/* Wordmark: one hover target per letter, each letter on its own
              blurred accent copy (the halo) - as in the pre-1.0 Avalonia
              app. */}
          <div className="flex select-none">
            {WORDMARK.map((ch, i) => (
              <span key={i} className="brand-letter">
                <span className="glow" aria-hidden>
                  {ch}
                </span>
                <span className="text">{ch}</span>
              </span>
            ))}
          </div>

          <div className="flex items-center gap-2">
            {/* Theme lens: flips dark <-> light (real, data-theme swap). */}
            <button
              type="button"
              className="btn-icon"
              title={t("Btn.Theme")}
              aria-label={t("Btn.Theme")}
              onClick={flipTheme}
            >
              <span className="text-[15px] leading-none">
                {theme === "dark" ? "☀" : "☾"}
              </span>
            </button>

            {/* Discord lens: opens the real invite in the system browser. */}
            <button
              type="button"
              className="btn-icon"
              title={t("Btn.Discord")}
              aria-label={t("Btn.Discord")}
              onClick={() => void invoke("open_url", { url: DISCORD_INVITE })}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden>
                <path fill="#5865F2" d={DISCORD_PATH} />
              </svg>
            </button>

            {/* The window's own caption controls, drawn by the app. */}
            <TitleBar t={t} />
          </div>
        </header>

        {/* --------------------------------------------------- content */}
        <div className="grid min-h-0 px-7" style={{ gridTemplateColumns: "460px 16px 1fr" }}>
          {/* Left column: the cards, scrollable like the ScrollViewer. */}
          <div className="min-h-0 overflow-y-auto pr-1">
            {/* Status */}
            <div className="card">
              <div className="flex items-center">
                <span className={`dot ${statusClass}`} />
                <span className={`text-sm font-semibold ${statusClass}`}>{statusText}</span>
              </div>
              {/* The configured port is taken by another app: name it
                  (exe + path + PID) and offer to kill it, like the
                  author asked - the engine cannot start until it's free. */}
              {portBusy ? (
                <div className="mt-2">
                  <p className="faint-text text-[11px]">
                    {t("Port.UsedBy", portBusy.name, String(portBusy.pid))}
                  </p>
                  <p className="ellipsis mt-0.5 text-[10px] text-text-secondary">
                    {portBusy.path}
                  </p>
                  <button
                    type="button"
                    className="btn-danger mt-2 w-full"
                    onClick={() => void killAndStart()}
                  >
                    {t("Btn.KillAndStart", portBusy.name)}
                  </button>
                </div>
              ) : null}
            </div>

            {/* Server address */}
            <div className="card text-center">
              <div className="label mb-2">{t("Label.ServerAddress")}</div>
              {/* The address itself is the affordance: one click opens
                  the engine's site (same url the QR encodes). */}
              <button
                type="button"
                className="address-link"
                disabled={!running || !info}
                title={t("Devices.OpenBrowser")}
                onClick={() => {
                  if (info) void invoke("open_url", { url: info.url_upload });
                }}
              >
                {running && info ? `${info.ip}:${info.port}` : "---"}
                {running && info ? <ExternalLink size={14} aria-hidden /> : null}
              </button>
            </div>

            {/* QR code */}
            <div className="card text-center">
              <div className="label mb-3">{t("Label.QrCode")}</div>
              {running && qrDataUrl ? (
                <div className="qr-card inline-block">
                  <img
                    src={qrDataUrl}
                    alt={t("Label.QrCode")}
                    width={220}
                    height={220}
                    className="block h-[220px] w-[220px]"
                  />
                </div>
              ) : null}
              <p className="faint-text mx-auto mt-2 max-w-[260px] text-xs">
                {qrGenerating
                  ? t("Qr.Generating")
                  : running
                    ? qrDataUrl
                      ? ""
                      : t("Qr.Unavailable")
                    : t("Qr.HintStart")}
              </p>
            </div>

            {/* Session code */}
            <div className="card text-center">
              <div className="label mb-1">{t("Label.SessionCode")}</div>
              <div className="text-[22px] font-semibold text-text-title">
                {running && info ? info.session_code : "---"}
              </div>
              <button
                type="button"
                className="btn-small mx-auto mt-2"
                disabled={!running}
                onClick={() => void copyCode()}
              >
                <Copy size={14} aria-hidden />
                {copied ? t("Btn.Copied") : t("Btn.Copy")}
              </button>
              <p className="faint-text mx-auto mt-1.5 max-w-[300px] text-[11px]">
                {t("Session.Hint")}
              </p>
            </div>

            {/* Token refresh */}
            <div className="card">
              <div className="label mb-2">{t("Label.TokenRefresh")}</div>
              <div className="flex items-center">
                <Combo
                  className="flex-1"
                  value={tokenIdx}
                  options={TOKEN_LABELS.map((key) => t(key))}
                  onChange={setTokenIdx}
                />
                <button
                  type="button"
                  className="btn-subtle ml-2"
                  disabled={!running || qrGenerating}
                  onClick={() => void rotate()}
                >
                  <RotateCcw size={14} aria-hidden />
                  {t("Btn.Reset")}
                </button>
              </div>
              <p className="faint-text mt-1.5 text-[11px]">
                {running && TOKEN_INTERVALS[tokenIdx] > 0
                  ? formatCountdown(secondsLeft, t)
                  : ""}
              </p>
            </div>

            {/* Folders */}
            <div className="card">
              <div className="label mb-2">{t("Label.Folders")}</div>
              <div className="flex items-center">
                <span className="faint-text text-xs">{t("Folders.Received")}</span>
                <span className="ellipsis mx-2 flex-1 text-xs text-text-secondary">
                  {running && info ? info.download_dir : "---"}
                </span>
                <button
                  type="button"
                  className="btn-small px-2 py-1 text-[11px]"
                  onClick={() => void openFolder(info?.download_dir ?? "")}
                >
                  <FolderOpen size={12} aria-hidden />
                  {t("Btn.Open")}
                </button>
              </div>
              <div className="mt-1 flex items-center">
                <span className="faint-text text-xs">{t("Folders.Shared")}</span>
                <span className="ellipsis mx-2 flex-1 text-xs text-text-secondary">
                  {running && info ? info.share_dir : "---"}
                </span>
                <button
                  type="button"
                  className="btn-small px-2 py-1 text-[11px]"
                  onClick={() => void openFolder(info?.share_dir ?? "")}
                >
                  <FolderOpen size={12} aria-hidden />
                  {t("Btn.Open")}
                </button>
              </div>
            </div>

            {/* Receive quota */}
            <div className="card text-center">
              <div className="label mb-3">{t("Label.ReceiveQuota")}</div>
              <div className={`text-base font-semibold ${quotaHint}`}>{quotaText}</div>
              {/* The fill eases to its new value whenever the usage
                  changes (see .quota-fill); no limit = it sweeps. */}
              <div className="quota-track">
                <div
                  className={`quota-fill ${full ? "full" : ""} ${unlimited ? "indeterminate" : ""}`}
                  style={{ width: unlimited ? 70 : `${fillPct}%` }}
                />
              </div>
              <p className="faint-text mx-auto mt-1.5 max-w-[300px] text-[11px]">
                {t("Quota.Description")}
              </p>
            </div>
          </div>

          <div />

          {/* Right column: the shared-files panel, the drop target. */}
          <SharedFiles t={t} lang={lang} refreshKey={refreshKey} />
        </div>

        {/* ------------------------------------------------- bottom bar */}
        {/* One floating capsule of glass carrying the two actions: it
            hovers above the window plane instead of being glued to the
            bottom edge (pre-1.0 Avalonia app, Width 460). */}
        <div className="capsule relative z-10">
          <button
            type="button"
            /* AutomationId for tools/screenshots/capture.py: together with
               BtnSettings it marks where the floating capsule ends, so the
               tool can crop the left column above it. */
            id="BtnToggleServer"
            className={running ? "btn-danger mb-2 w-full" : "btn-accent mb-2 w-full"}
            onClick={() => void toggleServer()}
          >
            {running ? <Square size={14} aria-hidden /> : <Play size={14} aria-hidden />}
            {running ? t("Btn.StopServer") : t("Btn.StartServer")}
          </button>
          <button
            type="button"
            /* AutomationId for tools/screenshots/capture.py: WebView2
               surfaces a DOM id as the UIA AutomationId (the pre-1.0
               Avalonia control carried the same name). */
            id="BtnSettings"
            className="btn-subtle w-full"
            onClick={() => void openSettings()}
          >
            <SettingsIcon size={14} aria-hidden />
            {t("Btn.Settings")}
          </button>
        </div>
      </div>

      {settingsOpen ? (
        <Settings
          t={t}
          lang={lang}
          config={settingsConfig.current}
          info={info}
          running={running}
          onSaved={(next, newLang) => {
            settingsConfig.current = { ...settingsConfig.current, ...next };
            setSettingsChanged(true);
            setLang(newLang);
            if (next.theme === "light" || next.theme === "dark") setTheme(next.theme);
            void loadQuota();
          }}
          onThemeChange={(th) => setTheme(th)}
          onClose={() => void closeSettings()}
          update={updPhase}
          onStartUpdate={() => acceptUpdate()}
        />
      ) : null}

      <UpdateToast
        t={t}
        lang={lang}
        view={toast}
        version={updCheck?.version ?? ""}
        current={updCheck?.current ?? ""}
        phase={updPhase}
        errorText={toastErr}
        onAccept={() => void acceptUpdate()}
        onRefuse={() => refuseUpdate()}
      />

      {/* Once per version: the same `current` the update check passes -
          no second getVersion() call, and nothing while the engine has
          not reported its version yet. */}
      <WhatsNew lang={lang} version={bundle?.info?.version ?? ""} />

      <MsgHost t={t} />
    </div>
  );
}
