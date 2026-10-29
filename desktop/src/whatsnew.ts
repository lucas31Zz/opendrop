// Release notes shown once per version, in the app's own language.
// The pre-1.0 desktop shipped the same popup from a hand-written
// note file beside the changelog (its first line naming the version it
// described); here the copy for 1.0.0 was reviewed with the
// implementation plan and lives next to its version constant.
import type { Lang } from "./strings";

/** The version this note belongs to - must equal tauri.conf.json. */
export const WHATSNEW_VERSION = "1.0.3";

/** localStorage key: written once the note has been dismissed for `v`. */
export const whatsnewKey = (v: string) => `opendrop-whatsnew-${v}`;

export const WHATSNEW_TITLE: Record<Lang, string> = {
  fr: "Quoi de neuf dans OpenDrop 1.0.3",
  en: "What's new in OpenDrop 1.0.3",
};

export const WHATSNEW: Record<Lang, string[]> = {
  fr: [
    "Sous le capot : les dépendances de l'application ont été actualisées, dont celles qui gèrent les mises à jour.",
    "Cette version sert aussi à tester le nouveau flux de mise à jour de bout en bout : téléchargement, « Mettre à jour » ou « Refuser », installation silencieuse et redémarrage.",
  ],
  en: [
    "Under the hood: the app's dependencies were updated, including the ones that handle updates.",
    "This release also exists to exercise the new update flow end to end: download, \"Update now\" or \"Decline\", silent install and restart.",
  ],
};

/** The single button that closes the note for good (it writes the key). */
export const WHATSNEW_ACTION: Record<Lang, string> = {
  fr: "J'ai compris",
  en: "Got it",
};
