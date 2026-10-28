// Release notes shown once per version, in the app's own language.
// The pre-1.0 desktop shipped the same popup from a hand-written
// note file beside the changelog (its first line naming the version it
// described); here the copy for 1.0.0 was reviewed with the
// implementation plan and lives next to its version constant.
import type { Lang } from "./strings";

/** The version this note belongs to - must equal tauri.conf.json. */
export const WHATSNEW_VERSION = "1.0.1";

/** localStorage key: written once the note has been dismissed for `v`. */
export const whatsnewKey = (v: string) => `opendrop-whatsnew-${v}`;

export const WHATSNEW_TITLE: Record<Lang, string> = {
  fr: "Quoi de neuf dans OpenDrop 1.0.1",
  en: "What's new in OpenDrop 1.0.1",
};

export const WHATSNEW: Record<Lang, string[]> = {
  fr: [
    "La fenêtre de console vide qui s'ouvrait au lancement a disparu.",
    "Le serveur s'arrête maintenant à la fermeture de l'application : plus de processus Python qui reste en arrière-plan.",
  ],
  en: [
    "The empty console window that opened at launch is gone.",
    "The server now stops when the app closes: no Python process left running in the background.",
  ],
};

/** The single button that closes the note for good (it writes the key). */
export const WHATSNEW_ACTION: Record<Lang, string> = {
  fr: "J'ai compris",
  en: "Got it",
};
