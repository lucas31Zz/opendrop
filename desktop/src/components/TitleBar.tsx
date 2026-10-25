// The window has NO OS chrome (decorations: false in tauri.conf.json):
// the header IS the title bar, like the ChatGPT desktop shell. The
// drag itself lives on the header (data-tauri-drag-region="deep",
// injected by Tauri: drag to move, double-click to maximize). These
// three quiet controls answer minimize, maximize/restore and close -
// close still just hides to the tray, the Rust side owns
// CloseRequested and only the tray's Quit really exits.
import { useEffect, useState } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { Copy, Minus, Square, X } from "lucide-react";
import type { T } from "../strings";

const appWindow = getCurrentWindow();

export default function TitleBar({ t }: { t: T }) {
  // The maximize glyph follows the real window state: one square while
  // restored, the overlapping pair while maximized - kept fresh on
  // every resize (the OS can maximize without our button: Win+Up,
  // drag to top edge, the taskbar menu...).
  const [maximized, setMaximized] = useState(false);
  useEffect(() => {
    let alive = true;
    void appWindow.isMaximized().then((m) => {
      if (alive) setMaximized(m);
    }).catch(() => {});
    const unlisten = appWindow.onResized(async () => {
      try {
        const m = await appWindow.isMaximized();
        if (alive) setMaximized(m);
      } catch {
        /* window gone */
      }
    });
    return () => {
      alive = false;
      void unlisten.then((u) => u());
    };
  }, []);

  const maxTitle = maximized ? t("Win.Restore") : t("Win.Maximize");

  return (
    <div className="win-controls">
      <button
        type="button"
        className="win-btn"
        title={t("Win.Minimize")}
        aria-label={t("Win.Minimize")}
        onClick={() => void appWindow.minimize().catch(() => {})}
      >
        <Minus size={15} strokeWidth={1.6} aria-hidden />
      </button>
      <button
        type="button"
        className="win-btn"
        title={maxTitle}
        aria-label={maxTitle}
        onClick={() => void appWindow.toggleMaximize().catch(() => {})}
      >
        {maximized ? (
          <Copy size={13} strokeWidth={1.6} aria-hidden />
        ) : (
          <Square size={13} strokeWidth={1.6} aria-hidden />
        )}
      </button>
      <button
        type="button"
        className="win-btn close"
        title={t("Win.Close")}
        aria-label={t("Win.Close")}
        onClick={() => void appWindow.close().catch(() => {})}
      >
        <X size={16} strokeWidth={1.6} aria-hidden />
      </button>
    </div>
  );
}
