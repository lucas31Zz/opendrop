// Release notes shown once per version, in the app's own language.
// The pre-1.0 desktop shipped the same popup from a hand-written
// note file beside the changelog (its first line naming the version it
// described); here the copy for 1.0.0 was reviewed with the
// implementation plan and lives next to its version constant.
import type { Lang } from "./strings";

/** The version this note belongs to - must equal tauri.conf.json. */
export const WHATSNEW_VERSION = "1.0.6";

/** localStorage key: written once the note has been dismissed for `v`. */
export const whatsnewKey = (v: string) => `opendrop-whatsnew-${v}`;

export const WHATSNEW_TITLE: Record<Lang, string> = {
  fr: "Quoi de neuf dans OpenDrop 1.0.6",
  en: "What's new in OpenDrop 1.0.6",
};

export const WHATSNEW: Record<Lang, string[]> = {
  fr: [
    "Fini l'avertissement « Non sécurisé » : installez une fois le certificat local depuis Réglages > Sécurité de la page web, et le cadenas vert s'affiche sur tous vos appareils, même après les mises à jour.",
    "Nouvelle section Sécurité dans les réglages de la page web : téléchargement du certificat et guide d'installation pas à pas pour Windows, iPhone, Android, macOS et Linux.",
  ],
  en: [
    "No more \"Not secure\" warning: install the local certificate once from the web Settings > Security, and the green padlock shows on every device, updates included.",
    "New Security section in the web settings: certificate download and a step-by-step install guide for Windows, iPhone, Android, macOS and Linux.",
  ],
};

/** The single button that closes the note for good (it writes the key). */
export const WHATSNEW_ACTION: Record<Lang, string> = {
  fr: "J'ai compris",
  en: "Got it",
};
