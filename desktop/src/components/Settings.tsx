// Block 9: the settings window, transcribed from the pre-1.0 desktop
// app's SettingsWindow.axaml
// (420x560, aurora, "?" header, seven sidebar tabs, accent save button)
// and its code-behind. Rendered as an overlay of the single window.
// Every field drives the REAL config.json and the REAL engine.
import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import QRCode from "qrcode";
import { Msg } from "../Msg";
import { copyToClipboard } from "../clipboard";
import {
  formatBytes,
  formatQuotaInput,
  parseQuota,
  type Lang,
  type StringKey,
  type T,
} from "../strings";
import Combo from "./Combo";
import { type UpdateCheckR, type UpdatePhase, updatePct } from "../update";

export type SettingsConfig = {
  language?: string;
  download_directory?: string;
  share_directory?: string;
  preferred_port?: number;
  generate_new_token?: boolean;
  theme?: string;
  global_quota_bytes?: number;
};

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

type DeviceRow = { ip: string; details: string };

const TABS = [
  "general",
  "storage",
  "security",
  "network",
  "devices",
  "appearance",
  "updates",
] as const;
type TabId = (typeof TABS)[number];

// Literal keys instead of a template-literal cast: the T function only
// accepts keys that exist in BOTH string tables.
const TAB_LABEL_KEYS = {
  general: "Tab.General",
  storage: "Tab.Storage",
  security: "Tab.Security",
  network: "Tab.Network",
  devices: "Tab.Devices",
  appearance: "Tab.Appearance",
  updates: "Tab.Updates",
} as const satisfies Record<TabId, StringKey>;

// Best-effort browser/OS breakdown, mirroring the ordered keyword scan
// of src/opendrop/security/devices.py (parse_user_agent) — never a
// User-Agent library.
function uaSummary(ua: string): string {
  if (!ua.trim()) return "";
  const device = ua.includes("iPhone")
    ? "iPhone"
    : ua.includes("iPad")
      ? "iPad"
      : ua.includes("Android")
        ? "Android"
        : "";
  const os = ua.includes("Windows")
    ? "Windows"
    : ua.includes("Android")
      ? "Android"
      : ua.includes("Mac OS X")
        ? "macOS"
        : ua.includes("Linux")
          ? "Linux"
          : "";
  const browser = ua.includes("Edg/")
    ? "Edge"
    : ua.includes("OPR/")
      ? "Opera"
      : ua.includes("Chrome/")
        ? "Chrome"
        : ua.includes("Firefox/")
          ? "Firefox"
          : ua.includes("Safari/")
            ? "Safari"
            : "";
  return [device, os, browser].filter((p, i, a) => p && a.indexOf(p) === i).join(" · ");
}

// added_at is an ISO-8601 UTC stamp from the server; shown as the local
// short date. Unparseable = no date line at all.
function formatAddedAt(addedAt: string): string {
  const moment = new Date(addedAt);
  return Number.isNaN(moment.getTime())
    ? ""
    : moment.toLocaleDateString(undefined, {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      });
}

/** Copy to the clipboard: see src/clipboard.ts (webview API, Rust fallback). */

export function Settings({
  t,
  lang,
  config,
  info,
  running,
  onSaved,
  onThemeChange,
  onClose,
  update,
  onStartUpdate,
}: {
  t: T;
  lang: Lang;
  config: SettingsConfig;
  info: EngineInfo | null;
  running: boolean;
  onSaved: (next: SettingsConfig, newLang: Lang) => void;
  // The theme combo flips the window LIVE but only the save button
  // persists it and marks the settings dirty (ThemeCombo_SelectionChanged
  // touches ThemeManager only, never SettingsChanged).
  onThemeChange: (theme: "dark" | "light") => void;
  onClose: () => void;
  /** Live download state: the toast carries the progress bar. */
  update: UpdatePhase;
  /** One acceptance: start the stream or launch the setup on disk. */
  onStartUpdate: () => Promise<void>;
}) {
  const [tab, setTab] = useState<TabId>("general");
  const [langIdx, setLangIdx] = useState(config.language === "fr" ? 1 : 0);
  const [downloadDir, setDownloadDir] = useState(config.download_directory ?? "");
  const [shareDir, setShareDir] = useState(config.share_directory ?? "");
  const [portText, setPortText] = useState(String(config.preferred_port ?? 8080));
  const [quotaText, setQuotaText] = useState(
    formatQuotaInput(config.global_quota_bytes ?? 0),
  );
  const [newToken, setNewToken] = useState(!!config.generate_new_token);
  const [themeIdx, setThemeIdx] = useState(config.theme === "light" ? 0 : 1);
  const [saved, setSaved] = useState(false);
  const [savedTimer, setSavedTimer] = useState<ReturnType<typeof setTimeout> | null>(null);
  const [usageBytes, setUsageBytes] = useState(0);

  // Devices tab: token, pair card and the registered rows, refreshed
  // every 3 s while the tab is open (LoadDevicesAsync's 3 s tick).
  const [deviceToken, setDeviceToken] = useState("");
  const [pairLink, setPairLink] = useState("");
  const [pairQr, setPairQr] = useState("");
  const [deviceRows, setDeviceRows] = useState<DeviceRow[]>([]);
  const [devicesHint, setDevicesHint] = useState("");
  const rowsSignature = useRef<string | null>(null);

  const activeRef = useRef<HTMLButtonElement>(null);
  const [pill, setPill] = useState({ top: 0, height: 0 });
  const [updating, setUpdating] = useState<string | null>(null);
  // The updates tab's own check reply: the setup on disk flips the
  // button to green "Update now" - but only while the check still says
  // a NEWER release exists (see the card below).
  const [updCheck, setUpdCheck] = useState<UpdateCheckR | null>(null);

  // ------------------------------------------------------------- devices
  // Latest info in a ref: the get_state poll hands out a FRESH info
  // object every round, and a changing identity used to re-create
  // loadDevices every poll - restarting its effect and firing an extra
  // /api/devices request each time (the engine's limiter_general is
  // 120 req/min per IP; the blink's real budget enemy).
  const infoRef = useRef(info);
  useEffect(() => {
    infoRef.current = info;
  });

  const loadDevices = useCallback(async () => {
    if (!running) {
      setDeviceToken("");
      setPairLink("");
      setPairQr("");
      setDeviceRows([]);
      rowsSignature.current = null;
      setDevicesHint(t("Devices.Stopped"));
      return;
    }
    try {
      const root = await invoke<{
        device_token?: string;
        devices?: Array<{
          ip?: string;
          ua?: string;
          share_info?: boolean;
          added_at?: string;
        }>;
      }>("get_devices");
      const inf = infoRef.current;
      const token = root.device_token ?? "";
      // A 200 WITHOUT the token (engine mid-restart, payload raced) is
      // not a "no token" answer: keep the last known token/link/QR and
      // let the next tick refill - never blank the card on a partial
      // payload (the "disparait puis reaparait" bug).
      if (token) {
        setDeviceToken(token);
        setPairLink(inf ? `https://${inf.ip}:${inf.port}/#pair=${token}` : "");
        if (inf) {
          try {
            setPairQr(await QRCode.toDataURL(pairLinkFor(inf, token)));
          } catch {
            setPairQr("");
          }
        }
      }
      if (Array.isArray(root.devices)) {
        const rows: DeviceRow[] = root.devices.map((d) => {
          const ip = d.ip ?? "";
          const parts: string[] = [];
          if (d.share_info) {
            const summary = uaSummary(d.ua ?? "");
            if (summary) parts.push(summary);
          }
          const date = formatAddedAt(d.added_at ?? "");
          if (date) parts.push(date);
          return { ip, details: parts.join(" · ") };
        });
        // Skip the rebuild when the set did not change: the 3 s refresh
        // would otherwise tear every row down under a resting pointer.
        const signature = rows.map((r) => `${r.ip}|${r.details}`).join("§");
        if (signature !== rowsSignature.current) {
          rowsSignature.current = signature;
          setDeviceRows(rows);
        }
      }
      setDevicesHint("");
    } catch {
      setDevicesHint(t("Err.Prefix"));
    }
  }, [running, t]);

  useEffect(() => {
    if (tab !== "devices") return;
    void loadDevices();
    const id = setInterval(() => void loadDevices(), 3000);
    return () => clearInterval(id);
  }, [tab, loadDevices]);

  // The storage line reads the folder's REAL usage (the desktop scans
  // the download folder when the tab becomes visible); only on entry,
  // so typing a path never rescans on every key.
  useEffect(() => {
    if (tab !== "storage") return;
    void (async () => {
      try {
        const q = await invoke<{ usage_bytes?: number }>("local_quota", {
          dir: downloadDir || null,
        });
        setUsageBytes(q.usage_bytes ?? 0);
      } catch {
        /* keep the last known number */
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  // The pill springs from tab to tab (TabPill, SpringEasing).
  useEffect(() => {
    if (activeRef.current) {
      setPill({
        top: activeRef.current.offsetTop,
        height: activeRef.current.offsetHeight,
      });
    }
  }, [tab]);

  // Escape closes, like the window's own close button.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => () => {
    if (savedTimer) clearTimeout(savedTimer);
  }, [savedTimer]);

  // -------------------------------------------------------------- browse
  const browse = async (which: "download" | "share") => {
    const title = which === "download" ? t("Browse.ReceiveTitle") : t("Browse.ShareTitle");
    try {
      const folder = await invoke<string | null>("pick_folder", {
        title,
        initial: which === "download" ? downloadDir : shareDir,
      });
      if (folder == null) return;
      if (which === "download") setDownloadDir(folder);
      else setShareDir(folder);
    } catch {
      /* dialog failure: keep the current value */
    }
  };

  // --------------------------------------------------------------- save
  const save = async () => {
    try {
      // int.TryParse falls back to the engine's default port.
      const parsedPort = Number.parseInt(portText, 10);
      const preferredPort = Number.isFinite(parsedPort) ? parsedPort : 8080;

      const quotaBytes = parseQuota(quotaText);
      if (quotaBytes == null) {
        await Msg.show(t("Field.GlobalQuota"), t("Quota.Invalid", quotaText), t);
        return;
      }
      // Warn when the requested quota exceeds 20% of the disk's free
      // space: the user may still choose it, but knowingly.
      let freeBytes = 0;
      try {
        freeBytes = await invoke<number>("free_space", { path: downloadDir });
      } catch {
        /* unknown free space = no warning */
      }
      if (quotaBytes > 0 && freeBytes > 0 && quotaBytes > freeBytes * 0.2) {
        const answer = await Msg.confirm(
          t("Quota.BigTitle"),
          t("Quota.BigBody", formatBytes(quotaBytes, lang), formatBytes(freeBytes, lang)),
          t,
        );
        if (!answer) return;
      }

      const next: SettingsConfig = {
        language: langIdx === 1 ? "fr" : "en",
        download_directory: downloadDir,
        share_directory: shareDir,
        preferred_port: preferredPort,
        generate_new_token: newToken,
        theme: themeIdx === 0 ? "light" : "dark",
        global_quota_bytes: quotaBytes,
      };
      await invoke("save_config", { config: next });

      // The accent behind the button is captured before turning green.
      setSaved(true);
      if (savedTimer) clearTimeout(savedTimer);
      setSavedTimer(
        setTimeout(() => {
          setSaved(false);
        }, 2000),
      );

      onSaved(next, next.language === "fr" ? "fr" : "en");
    } catch (e) {
      await Msg.show(t("Err.Settings"), String(e), t);
    }
  };

  // ------------------------------------------------------------ actions
  const resetPairing = async () => {
    if (!running) return;
    // Confirm only when it costs something: with no device registered
    // the reset is a plain rotation behind the scenes.
    if (deviceRows.length > 0) {
      const answer = await Msg.confirm(t("Devices.Reset"), t("Devices.ResetConfirm"), t);
      if (!answer) return;
    }
    try {
      const r = await invoke<{ device_token?: string }>("device_action", {
        action: "reset",
        ip: "",
      });
      if (r.device_token) setDeviceToken(r.device_token);
      await loadDevices();
    } catch {
      setDevicesHint(t("Err.Prefix"));
    }
  };

  const dissociate = async (ip: string) => {
    const answer = await Msg.confirm(t("Devices.Dissociate"), t("Devices.DissociateConfirm"), t);
    if (!answer) return;
    try {
      await invoke("device_action", { action: "dissociate", ip });
      await loadDevices();
    } catch {
      setDevicesHint(t("Err.Prefix"));
    }
  };

  // Opening the tab checks once (`info?.version` is a stable string
  // dependency, unlike the fresh `info` object the poll hands out). A
  // downloaded setup for a newer release replaces "Check for updates"
  // with the green "Update now" - the refused-at-startup, do-it-later
  // path (and the only place the button can come from now).
  useEffect(() => {
    if (tab !== "updates") return;
    let alive = true;
    void (async () => {
      try {
        const r = await invoke<UpdateCheckR>("check_updates", {
          current: info?.version ?? "",
        });
        if (!alive) return;
        setUpdCheck(r);
        if (r.status === "uptodate" && !r.installer) {
          setUpdating(t("Up.UpToDate", r.version));
        } else if (r.status === "error") {
          setUpdating(t("Up.Error", ""));
        }
      } catch (e) {
        if (alive) setUpdating(t("Up.Error", String(e)));
      }
    })();
    return () => {
      alive = false;
    };
    // t is derived from lang; lang is the real dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, info?.version, lang]);

  const checkUpdates = async () => {
    setUpdating(t("Up.Checking"));
    try {
      const r = await invoke<UpdateCheckR>("check_updates", {
        current: info?.version ?? "",
      });
      setUpdCheck(r);
      if (r.status === "uptodate") {
        setUpdating(t("Up.UpToDate", r.version));
      } else if (r.status === "available") {
        setUpdating(null);
        // The detection moment gets the FULL dialog language (shadowed
        // backdrop + opaque card), not the old inline line.
        const answer = await Msg.choice(
          t("Up.DialogTitle"),
          t("Up.DialogBody", r.version, r.current),
          [
            { label: t("Btn.UpdateNow"), value: "go", kind: "success" },
            { label: t("Btn.Later"), value: "later" },
          ],
        );
        if (answer === "go") await onStartUpdate();
      } else {
        setUpdating(t("Up.Error", ""));
      }
    } catch (e) {
      setUpdating(t("Up.Error", String(e)));
    }
  };

  // ------------------------------------------------------------ render
  const tabLabel = (id: TabId) => t(TAB_LABEL_KEYS[id]);

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center"
      style={{ background: "rgb(0 0 0 / 0.45)" }}
      onClick={onClose}
      role="presentation"
    >
      {/* The window itself: same aurora and glass as the main one.
          The id is how the screenshot tool recognises that the pane is
          open: pre-1.0 this was a second native window, now Settings is
          an overlay inside the single Tauri window. */}
      <div
        id="SettingsPane"
        className="settings-window settle relative"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="aurora aurora-1" />
        <div className="aurora aurora-2" />
        <div className="aurora aurora-3" />

        <div className="settings-grid relative z-10">
          {/* Header: the "?" glyph and the title, as in the XAML. */}
          <div className="mb-5 flex items-center">
            <span className="mr-2 text-lg accent-text">?</span>
            <span className="text-base font-semibold text-text-title">
              {t("Settings.Header")}
            </span>
          </div>

          {/* Content: tab list on the left, one visible page on the right. */}
          <div className="min-h-0 flex-1 overflow-hidden">
            <div className="settings-content flex min-h-0">
              <div className="relative mr-3.5">
                {/* The highlight that springs from tab to tab. */}
                <div
                  className="tab-pill absolute left-0 right-0"
                  style={{ top: pill.top, height: pill.height }}
                />
                <div className="relative flex flex-col">
                  {TABS.map((id) => (
                    <button
                      key={id}
                      type="button"
                      ref={tab === id ? activeRef : undefined}
                      className={`tab ${tab === id ? "active" : ""}`}
                      onClick={() => setTab(id)}
                    >
                      {tabLabel(id)}
                    </button>
                  ))}
                </div>
              </div>

              {/* Uniform breathing room in every tab: side margins, top pad,
                  and a generous bottom pad so the content scrolls cleanly and
                  never crowds the Save pill. */}
              <div className="min-h-0 flex-1 overflow-y-auto">
                <div className="px-1 pt-1 pb-8">
                {/* ------------------------------------------------ General */}
                {tab === "general" ? (
                  <div className="settle-450">
                    <div className="card mb-3">
                      <div className="field">{t("Field.Language")}</div>
                      <Combo
                        value={langIdx}
                        options={["English", "Français"]}
                        onChange={setLangIdx}
                      />
                    </div>

                    <div className="card mb-3">
                      <div className="field">{t("Field.ReceiveFolder")}</div>
                      <div className="flex items-center">
                        <input
                          className="input flex-1"
                          value={downloadDir}
                          onChange={(e) => setDownloadDir(e.target.value)}
                        />
                        <button
                          type="button"
                          className="browse ml-2"
                          onClick={() => void browse("download")}
                        >
                          ...
                        </button>
                      </div>
                    </div>

                    <div className="card mb-3">
                      <div className="field">{t("Field.ShareFolder")}</div>
                      <div className="flex items-center">
                        <input
                          className="input flex-1"
                          value={shareDir}
                          onChange={(e) => setShareDir(e.target.value)}
                        />
                        <button
                          type="button"
                          className="browse ml-2"
                          onClick={() => void browse("share")}
                        >
                          ...
                        </button>
                      </div>
                    </div>

                    <div className="card mb-4">
                      <div className="field">{t("Field.Port")}</div>
                      <input
                        className="input"
                        value={portText}
                        onChange={(e) => setPortText(e.target.value)}
                      />
                    </div>
                  </div>
                ) : null}

                {/* ------------------------------------------------ Storage */}
                {tab === "storage" ? (
                  <div className="settle-450">
                    <div className="card mb-4">
                      <div className="field">{t("Field.GlobalQuota")}</div>
                      <div className="flex items-center">
                        <input
                          className="input flex-1"
                          value={quotaText}
                          onChange={(e) => setQuotaText(e.target.value)}
                        />
                        <span className="ml-2 faint-text text-xs">{t("Quota.UnitHint")}</span>
                      </div>
                      <p className="mt-1.5 text-[11px] text-text-dim">
                        {t("Quota.NoUnitHint")}
                      </p>
                      <p className="mt-1.5 faint-text text-[11px]">
                        {usageBytes > 0
                          ? t("Quota.Usage", formatBytes(usageBytes, lang))
                          : t("Quota.NoFiles")}
                      </p>
                      <p className="mt-1 text-[11px] text-text-dim">
                        {t("Quota.CumulativeHint")}
                      </p>
                    </div>
                  </div>
                ) : null}

                {/* ------------------------------------------------ Security */}
                {tab === "security" ? (
                  <div className="settle-450">
                    <div className="card mb-4 flex items-center justify-between">
                      <span className="text-[13px] text-text-secondary">
                        {t("Field.NewToken")}
                      </span>
                      <label className="checkbox-wrap">
                        <input
                          type="checkbox"
                          checked={newToken}
                          onChange={(e) => setNewToken(e.target.checked)}
                        />
                        <span className="checkbox" />
                      </label>
                    </div>
                  </div>
                ) : null}

                {/* ------------------------------------------------- Network */}
                {tab === "network" ? (
                  <div className="settle-450">
                    <div className="card mb-4">
                      <div className="field">{t("Field.NetworkInterface")}</div>
                      <p className="muted-text text-xs">{t("Interface.Auto")}</p>
                    </div>
                  </div>
                ) : null}

                {/* -------------------------------------------------- Devices */}
                {tab === "devices" ? (
                  <div className="settle-450">
                    <div className="card mb-3">
                      <div className="field">{t("Devices.Token")}</div>
                      <div className="flex items-center">
                        <span className="input flex-1 ellipsis muted-text text-xs">
                          {deviceToken ? `${deviceToken.slice(0, 8)}…` : ""}
                        </span>
                        <button
                          type="button"
                          className="browse ml-2"
                          disabled={!deviceToken}
                          onClick={() => void copyToClipboard(deviceToken)}
                        >
                          {t("Btn.Copy")}
                        </button>
                      </div>
                    </div>

                    {pairLink ? (
                      <div className="card mb-3">
                        <div className="field">{t("Devices.PourParrainer")}</div>
                        {pairQr ? (
                          <img
                            src={pairQr}
                            alt={t("Devices.PourParrainer")}
                            width={160}
                            height={160}
                            className="mx-auto my-1 mb-2 block h-40 w-40"
                          />
                        ) : null}
                        <p
                          className="muted-text mb-2.5 break-all text-xs"
                          title={pairLink}
                        >
                          {pairLink}
                        </p>
                        <div className="mb-2 flex">
                          <button
                            type="button"
                            className="browse flex-1"
                            onClick={() => void copyToClipboard(pairLink)}
                          >
                            {t("Btn.Copy")}
                          </button>
                          <button
                            type="button"
                            className="browse ml-2 flex-1"
                            onClick={() =>
                              void invoke("open_url", { url: pairLink }).catch(() =>
                                Msg.show(t("Status.Error"), t("Err.OpenBrowser"), t),
                              )
                            }
                          >
                            {t("Devices.OpenBrowser")}
                          </button>
                        </div>
                        <button
                          type="button"
                          className="browse w-full"
                          onClick={() => void resetPairing()}
                        >
                          {t("Devices.Reset")}
                        </button>
                      </div>
                    ) : null}

                    <div className="card mb-4">
                      <div className="field">{t("Tab.Devices")}</div>
                      {deviceRows.length === 0 ? (
                        <p className="muted-text text-xs">{t("Devices.None")}</p>
                      ) : null}
                      {deviceRows.map((row) => (
                        <div
                          key={row.ip}
                          className="device-row mb-2 flex items-center justify-between"
                        >
                          <div className="min-w-0">
                            <div className="text-[13px] text-text-secondary">{row.ip}</div>
                            {row.details ? (
                              <div className="faint-text text-[11px]">{row.details}</div>
                            ) : null}
                          </div>
                          <button
                            type="button"
                            className="browse ml-2"
                            onClick={() => void dissociate(row.ip)}
                          >
                            {t("Devices.Dissociate")}
                          </button>
                        </div>
                      ))}
                      <button
                        type="button"
                        className="browse mt-2.5 w-full"
                        onClick={() => void loadDevices()}
                      >
                        {t("Btn.Refresh")}
                      </button>
                      <p className="faint-text mt-2 text-[11px]">{devicesHint}</p>
                    </div>
                  </div>
                ) : null}

                {/* ------------------------------------------------ Appearance */}
                {tab === "appearance" ? (
                  <div className="settle-450">
                    <div className="card mb-4">
                      <div className="field">{t("Field.Theme")}</div>
                      {/* The theme flips the whole app live, like the
                          main window's lens button (ThemeManager). */}
                      <Combo
                        className="mt-1"
                        value={themeIdx}
                        options={[t("Theme.Light"), t("Theme.Dark")]}
                        onChange={(idx) => {
                          setThemeIdx(idx);
                          onThemeChange(idx === 0 ? "light" : "dark");
                        }}
                      />
                    </div>
                  </div>
                ) : null}

                {/* --------------------------------------------------- Updates */}
                {tab === "updates" ? (
                  <div className="settle-450">
                    <div className="card mb-5">
                      <div className="flex items-center justify-between">
                        <span className="text-[13px] text-text-secondary">
                          {t("Field.Version")}
                        </span>
                        <span className="muted-text text-[13px]">{info?.version ?? ""}</span>
                      </div>
                      {(updCheck?.status === "available" && updCheck.installer) ||
                      (update.phase === "done" && update.installer) ? (
                        /* Setup already downloaded AND a newer release
                           really available: green "Update now" with the
                           logo - press = straight to the admin check.
                           The status gate matters: once this release IS
                           the running one, a leftover setup must not
                           keep offering to reinstall the present. */
                        <button
                          type="button"
                          className="browse update-now mt-2.5 w-full"
                          onClick={() => void onStartUpdate()}
                        >
                          <img
                            className="update-now-logo"
                            src="/icon.png"
                            alt=""
                            aria-hidden="true"
                          />
                          {t("Btn.UpdateNow")}
                        </button>
                      ) : update.phase === "downloading" ? (
                        <button type="button" className="browse mt-2.5 w-full" disabled>
                          {t("Up.Downloading")} {updatePct(update)}%
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="browse mt-2.5 w-full"
                          onClick={() => void checkUpdates()}
                        >
                          {t("Btn.CheckUpdates")}
                        </button>
                      )}
                      <p className="faint-text mt-2 text-[11px]">{updating ?? ""}</p>
                    </div>
                  </div>
                ) : null}
                </div>
              </div>
            </div>
          </div>

          {/* Save: the accent glass pill. No top margin — the XAML Grid
              gives it its own Auto row. */}
          <button
            type="button"
            className={`save ${saved ? "saved" : ""}`}
            onClick={() => void save()}
          >
            {saved ? t("Btn.Saved") : t("Btn.Save")}
          </button>
        </div>
      </div>
    </div>
  );
}

function pairLinkFor(info: EngineInfo, token: string): string {
  return `https://${info.ip}:${info.port}/#pair=${token}`;
}
