// UpdateToast: the bottom-right notification raised when an update was
// detected at startup. Same opaque card language as the dialogs, the
// app logo, green accept / red refuse; once accepted it stays on the
// mini download bar until the installer is ready - the Rust side then
// launches it (administrator check) by itself.
import { formatBytes, type Lang, type T } from "./strings";
import type { UpdatePhase } from "./update";
import { updatePct } from "./update";

export type ToastView =
  | "hidden"
  | "prompt"
  | "downloading"
  | "installing"
  | "error";

export function UpdateToast({
  t,
  lang,
  view,
  version,
  current,
  phase,
  errorText,
  onAccept,
  onRefuse,
}: {
  t: T;
  lang: Lang;
  view: ToastView;
  version: string;
  current: string;
  phase: UpdatePhase;
  errorText: string;
  onAccept: () => void;
  onRefuse: () => void;
}) {
  if (view === "hidden") return null;
  const pct = updatePct(phase);
  const actions = view === "prompt" || view === "error";
  return (
    <div className="update-toast" role="status" aria-label={t("Up.ToastTitle")}>
      <div className="flex items-start gap-3">
        <img className="update-logo" src="/icon.png" alt="" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <div className="text-[13px] font-semibold text-text-title">
            {t("Up.ToastTitle")}
          </div>
          {view === "prompt" ? (
            <p className="mt-1 text-[12px] leading-snug text-text-secondary">
              {t("Up.Available", version, current)}
            </p>
          ) : null}
          {view === "downloading" ? (
            <>
              <p className="mt-1 text-[12px] text-text-secondary">
                {t("Up.Downloading")}
              </p>
              <div
                className="update-bar mt-2"
                role="progressbar"
                aria-label={t("Up.Downloading")}
                aria-valuenow={pct}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <i style={{ width: `${pct}%` }} />
              </div>
              <p className="faint-text mt-1 text-[11px]">
                {formatBytes(phase.downloaded, lang)}
                {phase.total > 0 ? ` / ${formatBytes(phase.total, lang)}` : ""}
                {" · "}
                {pct}%
              </p>
            </>
          ) : null}
          {view === "installing" ? (
            <p className="mt-1 text-[12px] text-text-secondary">
              {t("Up.Launching")}
            </p>
          ) : null}
          {view === "error" ? (
            <p className="hint-danger mt-1 text-[12px] leading-snug">
              {errorText}
            </p>
          ) : null}
        </div>
      </div>
      {actions ? (
        <div className="mt-3 flex justify-end gap-2">
          <button type="button" className="dialog-btn success" onClick={onAccept}>
            {t("Btn.UpdateNow")}
          </button>
          <button type="button" id="BtnUpdateDecline" className="dialog-btn danger" onClick={onRefuse}>
            {t("Btn.Refuse")}
          </button>
        </div>
      ) : null}
    </div>
  );
}
