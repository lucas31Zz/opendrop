// Shared update-flow types: the Rust UpdatePhase mirrored by the
// `update-progress` event, and the check_updates reply. One source for
// App (toast state), Settings (tab buttons) and UpdateToast.
export type UpdatePhase = {
  phase: "idle" | "downloading" | "done" | "error";
  tag: string;
  downloaded: number;
  total: number;
  error: string;
  installer: string;
};

export type UpdateCheckR = {
  status: string; // uptodate | available | error
  version: string;
  current: string;
  asset_url: string;
  /** GitHub's `sha256:<hex>` for asset_url; Rust refuses to run the
   *  download unless it hashes to exactly this. */
  digest: string;
  installer: string; // path when the setup is already downloaded
  part_bytes: number;
};

export const IDLE_UPDATE: UpdatePhase = {
  phase: "idle",
  tag: "",
  downloaded: 0,
  total: 0,
  error: "",
  installer: "",
};

/** One refusal per version: the same tag never nags twice. */
export const dismissedKey = (version: string) =>
  `opendrop-update-dismissed-${version}`;

/** Bar fill: 0 while the total is still unknown (the label shows bytes). */
export const updatePct = (p: UpdatePhase): number =>
  p.total > 0 ? Math.min(100, Math.floor((p.downloaded / p.total) * 100)) : 0;
