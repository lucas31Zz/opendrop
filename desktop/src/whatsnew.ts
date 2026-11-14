// Release notes shown once per version, in the app's own language.
// The pre-1.0 desktop shipped the same popup from a hand-written
// note file beside the changelog (its first line naming the version it
// described); here the copy for 1.0.0 was reviewed with the
// implementation plan and lives next to its version constant.
import type { Lang } from "./strings";

/** The version this note belongs to - must equal tauri.conf.json. */
export const WHATSNEW_VERSION = "1.0.5";

/** localStorage key: written once the note has been dismissed for `v`. */
export const whatsnewKey = (v: string) => `opendrop-whatsnew-${v}`;

export const WHATSNEW_TITLE: Record<Lang, string> = {
  fr: "Quoi de neuf dans OpenDrop 1.0.5",
  en: "What's new in OpenDrop 1.0.5",
};

export const WHATSNEW: Record<Lang, string[]> = {
  fr: [
    "Le panneau des fichiers partagés s'adapte à toutes les tailles de fenêtre : il n'est plus coupé sur le bord droit quand on réduit la fenêtre jusqu'à sa largeur minimale.",
    "Sous le capot, les deux colonnes du contenu sont maintenant bornées (380 à 460 px à gauche, au moins 280 px à droite) au lieu d'une largeur fixe.",
  ],
  en: [
    "The shared-files panel adapts to any window size: it is no longer clipped at the right edge when the window shrinks to its minimum width.",
    "Under the hood, the two content columns are now bounded (380-460px on the left, at least 280px on the right) instead of a fixed width.",
  ],
};

/** The single button that closes the note for good (it writes the key). */
export const WHATSNEW_ACTION: Record<Lang, string> = {
  fr: "J'ai compris",
  en: "Got it",
};
