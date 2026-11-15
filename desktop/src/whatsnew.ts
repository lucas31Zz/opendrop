// Release notes shown once per version, in the app's own language.
// The pre-1.0 desktop shipped the same popup from a hand-written
// note file beside the changelog (its first line naming the version it
// described); here the copy for 1.0.0 was reviewed with the
// implementation plan and lives next to its version constant.
import type { Lang } from "./strings";

/** The version this note belongs to - must equal tauri.conf.json. */
export const WHATSNEW_VERSION = "1.0.8";

/** localStorage key: written once the note has been dismissed for `v`. */
export const whatsnewKey = (v: string) => `opendrop-whatsnew-${v}`;

export const WHATSNEW_TITLE: Record<Lang, string> = {
  fr: "Quoi de neuf dans OpenDrop 1.0.8",
  en: "What's new in OpenDrop 1.0.8",
};

export const WHATSNEW: Record<Lang, string[]> = {
  fr: [
    "Le Service Worker ne répond plus jamais « vide » au navigateur : la page ouverte hors ligne se charge désormais correctement sur iPhone / Safari.",
    "La suite de tests utilise une autorité de certification au nom unique, pour ne plus entrer en collision avec la CA installée sur le poste.",
  ],
  en: [
    "The service worker never answers \"empty\" to the browser anymore: the offline page now loads correctly on iPhone / Safari.",
    "The test suite uses a uniquely named certificate authority, so it no longer collides with the CA installed on the machine.",
  ],
};

/** The single button that closes the note for good (it writes the key). */
export const WHATSNEW_ACTION: Record<Lang, string> = {
  fr: "J'ai compris",
  en: "Got it",
};
