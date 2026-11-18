// Release notes shown once per version, in the app's own language.
// The pre-1.0 desktop shipped the same popup from a hand-written
// note file beside the changelog (its first line naming the version it
// described); here the copy for 1.0.0 was reviewed with the
// implementation plan and lives next to its version constant.
import type { Lang } from "./strings";

/** The version this note belongs to - must equal tauri.conf.json. */
export const WHATSNEW_VERSION = "1.0.9";

/** localStorage key: written once the note has been dismissed for `v`. */
export const whatsnewKey = (v: string) => `opendrop-whatsnew-${v}`;

export const WHATSNEW_TITLE: Record<Lang, string> = {
  fr: "Quoi de neuf dans OpenDrop 1.0.9",
  en: "What's new in OpenDrop 1.0.9",
};

export const WHATSNEW: Record<Lang, string[]> = {
  fr: [
    "La page propose un guide de confiance adapté à votre appareil : iPhone / iPad (profil à installer, Validation des certificats) et Android (certificat d'autorité, verrou d'écran requis), avec la bannière qui l'ouvre dès la première visite.",
    "L'OS est détecté automatiquement : sa checklist est mise en avant et la liste complète des systèmes reste juste en dessous, au cas où la détection se trompe.",
  ],
  en: [
    "The page now offers a device-aware trust guide: iPhone / iPad (profile to install, Certificate Trust Settings) and Android (CA certificate, screen lock required), with a banner opening it from the very first visit.",
    "The OS is detected automatically: its checklist is brought forward and the full system list stays right below, in case the detection is wrong.",
  ],
};

/** The single button that closes the note for good (it writes the key). */
export const WHATSNEW_ACTION: Record<Lang, string> = {
  fr: "J'ai compris",
  en: "Got it",
};
