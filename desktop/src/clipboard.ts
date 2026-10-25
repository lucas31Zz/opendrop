// Clipboard helper shared by the main window and the settings window.
// Lives in its own module: mixing a component export with a plain
// function export in Settings.tsx defeats Vite's Fast Refresh.
import { invoke } from "@tauri-apps/api/core";

/** Copy to the clipboard: the webview API first, the Rust fallback after. */
export async function copyToClipboard(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    await invoke("copy_text", { text });
  }
}
