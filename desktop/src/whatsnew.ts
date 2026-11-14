// Release notes shown once per version, in the app's own language.
// The pre-1.0 desktop shipped the same popup from a hand-written
// note file beside the changelog (its first line naming the version it
// described); here the copy for 1.0.0 was reviewed with the
// implementation plan and lives next to its version constant.
import type { Lang } from "./strings";

/** The version this note belongs to - must equal tauri.conf.json. */
export const WHATSNEW_VERSION = "1.0.7";

/** localStorage key: written once the note has been dismissed for `v`. */
export const whatsnewKey = (v: string) => `opendrop-whatsnew-${v}`;

export const WHATSNEW_TITLE: Record<Lang, string> = {
  fr: "Quoi de neuf dans OpenDrop 1.0.7",
  en: "What's new in OpenDrop 1.0.7",
};

export const WHATSNEW: Record<Lang, string[]> = {
  fr: [
    "Fini l'assistant d'installation de certificat : le bureau détecte l'absence de la CA locale et propose un bouton Installer en un clic dans la carte d'état, à côté de « Serveur actif ».",
    "L'installation se fait dans les certificats de l'utilisateur actuel (sans droits administrateur ni fenêtre Windows) et l'application vérifie le résultat avant de l'afficher.",
  ],
  en: [
    "No more certificate wizard: the desktop detects a missing local CA and offers a one-click Install in the status card, right next to \"Server running\".",
    "The install goes into the current user's certificate store (no admin rights, no Windows dialog) and the app verifies the result before reporting it.",
  ],
};

/** The single button that closes the note for good (it writes the key). */
export const WHATSNEW_ACTION: Record<Lang, string> = {
  fr: "J'ai compris",
  en: "Got it",
};
