// Release notes shown once per version, in the app's own language.
// The pre-1.0 desktop shipped the same popup from a hand-written
// note file beside the changelog (its first line naming the version it
// described); here the copy for 1.0.0 was reviewed with the
// implementation plan and lives next to its version constant.
import type { Lang } from "./strings";

/** The version this note belongs to - must equal tauri.conf.json. */
export const WHATSNEW_VERSION = "1.0.2";

/** localStorage key: written once the note has been dismissed for `v`. */
export const whatsnewKey = (v: string) => `opendrop-whatsnew-${v}`;

export const WHATSNEW_TITLE: Record<Lang, string> = {
  fr: "Quoi de neuf dans OpenDrop 1.0.2",
  en: "What's new in OpenDrop 1.0.2",
};

export const WHATSNEW: Record<Lang, string[]> = {
  fr: [
    "La mise à jour s'applique maintenant en silence : plus d'assistant qui s'ouvre par-dessus l'application, et OpenDrop redémarre tout seul à la fin.",
    "Une fois le téléchargement terminé, l'application demande « Mettre à jour » ou « Refuser » au lieu d'installer automatiquement.",
    "Le bouton « Mettre à jour » ne reste plus affiché quand vous êtes déjà à jour.",
  ],
  en: [
    "Updates now apply silently: no more wizard opening on top of the app, and OpenDrop restarts itself when it finishes.",
    "Once the download is finished, the app asks \"Update now\" or \"Decline\" instead of installing on its own.",
    "The \"Update now\" button no longer stays when you are already up to date.",
  ],
};

/** The single button that closes the note for good (it writes the key). */
export const WHATSNEW_ACTION: Record<Lang, string> = {
  fr: "J'ai compris",
  en: "Got it",
};
