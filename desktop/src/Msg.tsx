// Msg: the desktop's message boxes (Msg.ShowAsync / ConfirmAsync /
// InputAsync / ChoiceAsync) as a promise-based overlay. Same title/body
// strings, same button sets (Msg.Ok / Msg.Yes-No / Msg.Cancel).
import { useCallback, useEffect, useRef, useState } from "react";
import type { T } from "./strings";

type Button = {
  label: string;
  value: string;
  kind?: "accent" | "danger" | "success";
};

type DialogState = {
  title: string;
  body: string;
  buttons: Button[];
  input?: { value: string; placeholder?: string };
  resolve: (value: string | null) => void;
};

let push: ((d: DialogState) => void) | null = null;
// True while a dialog is on screen: the Settings window listens for a
// window-level Escape and must not close on the dialog's own Escape.
let msgOpen = false;

function ask(
  title: string,
  body: string,
  buttons: Button[],
  input?: { value: string; placeholder?: string },
): Promise<string | null> {
  return new Promise((resolve) => {
    if (!push) {
      // No host mounted: fail open rather than hanging the caller.
      resolve(null);
      return;
    }
    push({ title, body, buttons, input, resolve });
  });
}

export const Msg = {
  show: (title: string, body: string, t: T) =>
    ask(title, body, [{ label: t("Msg.Ok"), value: "ok", kind: "accent" }]),
  confirm: (title: string, body: string, t: T) =>
    ask(title, body, [
      { label: t("Msg.Yes"), value: "yes", kind: "accent" },
      { label: t("Msg.No"), value: "no" },
    ]),
  input: (title: string, body: string, initial: string, t: T) =>
    ask(
      title,
      `${body}\n`,
      [
        { label: t("Msg.Ok"), value: "ok", kind: "accent" },
        { label: t("Msg.Cancel"), value: "cancel" },
      ],
      { value: initial },
    ),
  choice: (
    title: string,
    body: string,
    buttons: { label: string; value: string; kind?: Button["kind"] }[],
  ) => ask(title, body, buttons),
  isOpen: () => msgOpen,
};

/** Mounted once by App; renders the topmost dialog. */
export function MsgHost({ t }: { t: T }) {
  const [dialog, setDialog] = useState<DialogState | null>(null);
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);

  const settle = useCallback((d: DialogState | null, value: string | null) => {
    if (d) d.resolve(value);
    setDialog(null);
  }, []);

  useEffect(() => {
    push = (d) => {
      // A second ask() while one is open would strand the first
      // promise forever: settle it as cancelled before replacing it.
      setDialog((current) => {
        current?.resolve(null);
        return d;
      });
      setDraft(d.input?.value ?? "");
    };
    return () => {
      push = null;
    };
  }, []);

  useEffect(() => {
    msgOpen = dialog != null;
    // Focus lives INSIDE the dialog: with focus left on the trigger,
    // Enter/Space re-activate the underlying button behind the modal.
    if (dialog?.input) inputRef.current?.select();
    else cardRef.current?.focus();
  }, [dialog]);

  if (!dialog) return null;

  const ok = () => settle(dialog, dialog.input ? draft : "ok");
  const cancel = () => settle(dialog, null);

  return (
    <div
      className="dialog-backdrop"
      onClick={cancel}
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          // Stop here: Settings listens for a window-level Escape and
          // must not close together with the dialog.
          e.stopPropagation();
          cancel();
        }
        if (e.key === "Enter") ok();
      }}
      role="presentation"
    >
      <div
        ref={cardRef}
        tabIndex={-1}
        className="card dialog-card"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={dialog.title}
      >
        <div className="text-[15px] font-semibold text-text-title">
          {dialog.title}
        </div>
        <p className="mt-2 whitespace-pre-line text-[13px] leading-relaxed text-text-secondary">
          {dialog.body}
        </p>
        {dialog.input ? (
          <input
            ref={inputRef}
            className="input mt-3 w-full"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") ok();
            }}
          />
        ) : null}
        <div className="mt-4 flex justify-end gap-2">
          {dialog.buttons.map((b) => (
            <button
              key={b.value}
              type="button"
              className={
                b.kind === "accent"
                  ? "dialog-btn accent"
                  : b.kind === "danger"
                    ? "dialog-btn danger"
                    : b.kind === "success"
                      ? "dialog-btn success"
                      : "dialog-btn"
              }
              onClick={() => settle(dialog, b.value)}
            >
              {b.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
