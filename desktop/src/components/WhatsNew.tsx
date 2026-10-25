// WhatsNew: the one-time release note for WHATSNEW_VERSION, in the same
// dialog language as the message boxes (backdrop + settled card).
// It stays out of the way until the engine reports exactly that version
// (`version` is empty while the server is stopped, and a running 0.16.x
// must never see 1.0.0's note), and it is gone for good once its key
// sits in localStorage: one popup per version, never again on a restart.
import { useState } from "react";
import type { Lang } from "../strings";
import {
  WHATSNEW,
  WHATSNEW_ACTION,
  WHATSNEW_TITLE,
  WHATSNEW_VERSION,
  whatsnewKey,
} from "../whatsnew";

export function WhatsNew({ lang, version }: { lang: Lang; version: string }) {
  // Local, because writing localStorage alone re-renders nothing: without
  // this the note would sit on screen until the next launch even though
  // it had already been dismissed.
  const [open, setOpen] = useState(true);

  if (!open) return null;
  if (version !== WHATSNEW_VERSION) return null;
  if (localStorage.getItem(whatsnewKey(version))) return null;

  const dismiss = () => {
    // Written on dismissal: the next launch finds the key and renders
    // nothing, so the note cannot nag twice for the same release.
    localStorage.setItem(whatsnewKey(version), "1");
    setOpen(false);
  };

  return (
    <div className="dialog-backdrop">
      <div
        className="card dialog-card"
        role="dialog"
        aria-modal="true"
        aria-label={WHATSNEW_TITLE[lang]}
      >
        <h2 className="text-[14px] font-semibold text-text-title">
          {WHATSNEW_TITLE[lang]}
        </h2>
        <div className="mt-3 space-y-2 text-[12px] leading-snug text-text-secondary">
          {WHATSNEW[lang].map((p, i) => (
            <p key={i}>{p}</p>
          ))}
        </div>
        <div className="mt-4 flex justify-end">
          <button type="button" id="BtnWhatsNewDismiss" className="dialog-btn success" onClick={dismiss}>
            {WHATSNEW_ACTION[lang]}
          </button>
        </div>
      </div>
    </div>
  );
}
