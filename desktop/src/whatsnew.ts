// Release notes shown once per version, in the app's own language.
// The pre-1.0 desktop shipped the same popup from a hand-written
// `whatsnew.fr.md` beside the changelog (its first line naming the
// version it described); here the copy for 1.0.0 was reviewed with the
// implementation plan and lives next to its version constant.
import type { Lang } from "./strings";

/** The version this note belongs to - must equal tauri.conf.json. */
export const WHATSNEW_VERSION = "1.0.0";

/** localStorage key: written once the note has been dismissed for `v`. */
export const whatsnewKey = (v: string) => `opendrop-whatsnew-${v}`;

export const WHATSNEW_TITLE: Record<Lang, string> = {
  fr: "Quoi de neuf dans OpenDrop 1.0.0",
  en: "What's new in OpenDrop 1.0.0",
};

export const WHATSNEW: Record<Lang, string[]> = {
  fr: [
    "OpenDrop passe à une nouvelle interface : barre de titre intégrée, icône en rond, une seule fenêtre par appareil et le serveur démarre tout seul.",
    "Les mises à jour sont maintenant téléchargées et vérifiées (SHA-256) directement dans l'application.",
    "Correction des icônes de thème ☀/☾ qui s'affichaient mal.",
  ],
  en: [
    "OpenDrop has a new look: an integrated title bar, a round icon, one window per machine, and the server starts on its own.",
    "Updates are now downloaded and verified (SHA-256) right inside the app.",
    "Fixed the sun/moon theme icons that displayed incorrectly.",
  ],
};

/** The single button that closes the note for good (it writes the key). */
export const WHATSNEW_ACTION: Record<Lang, string> = {
  fr: "J'ai compris",
  en: "Got it",
};
