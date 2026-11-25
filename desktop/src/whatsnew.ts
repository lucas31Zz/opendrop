// Release notes shown once per version, in the app's own language.
// The pre-1.0 desktop shipped the same popup from a hand-written
// note file beside the changelog (its first line naming the version it
// described); here the copy for 1.0.0 was reviewed with the
// implementation plan and lives next to its version constant.
import type { Lang } from "./strings";

/** The version this note belongs to - must equal tauri.conf.json. */
export const WHATSNEW_VERSION = "1.0.10";

/** localStorage key: written once the note has been dismissed for `v`. */
export const whatsnewKey = (v: string) => `opendrop-whatsnew-${v}`;

export const WHATSNEW_TITLE: Record<Lang, string> = {
  fr: "Quoi de neuf dans OpenDrop 1.0.10",
  en: "What's new in OpenDrop 1.0.10",
};

export const WHATSNEW: Record<Lang, string[]> = {
  fr: [
    "Envois et scan plus fluides sur iPhone : les animations d'entrée ne re-floutent plus le verre, le défilement est plus régulier et le zoom accidentel au double-tap est désactivé.",
    "La liaison d'appareil ne se perd plus au rechargement de la page, et un appareil révoqué reste révoqué jusqu'à une nouvelle liaison (ou une réinitialisation).",
  ],
  en: [
    "Smoother sending and scanning on iPhone: entrances no longer re-blur the glass, scrolling is steadier and the accidental double-tap zoom is disabled.",
    "Pairing no longer resets when the page reloads, and a revoked device stays revoked until it pairs again (or the list is reset).",
  ],
};

/** The single button that closes the note for good (it writes the key). */
export const WHATSNEW_ACTION: Record<Lang, string> = {
  fr: "J'ai compris",
  en: "Got it",
};
