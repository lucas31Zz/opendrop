// Release notes shown once per version, in the app's own language.
// The pre-1.0 desktop shipped the same popup from a hand-written
// note file beside the changelog (its first line naming the version it
// described); here the copy for 1.0.0 was reviewed with the
// implementation plan and lives next to its version constant.
import type { Lang } from "./strings";

/** The version this note belongs to - must equal tauri.conf.json. */
export const WHATSNEW_VERSION = "1.0.4";

/** localStorage key: written once the note has been dismissed for `v`. */
export const whatsnewKey = (v: string) => `opendrop-whatsnew-${v}`;

export const WHATSNEW_TITLE: Record<Lang, string> = {
  fr: "Quoi de neuf dans OpenDrop 1.0.4",
  en: "What's new in OpenDrop 1.0.4",
};

export const WHATSNEW: Record<Lang, string[]> = {
  fr: [
    "La version affichée dans les réglages vient maintenant du binaire : plus de champ vide quand le moteur est arrêté, et plus de mise à jour proposée à chaque lancement.",
    "Quitter l'application tue maintenant tous les processus du moteur (fini l'orphelin qui garde le port) et la mise à jour redémarre l'app sans droits administrateur.",
  ],
  en: [
    "The version shown in Settings now comes from the app itself: no more empty field while the engine is stopped, and no more update offered on every launch.",
    "Quitting now stops every engine process (no more orphan holding the port), and an update restarts the app without administrator rights.",
  ],
};

/** The single button that closes the note for good (it writes the key). */
export const WHATSNEW_ACTION: Record<Lang, string> = {
  fr: "J'ai compris",
  en: "Got it",
};
