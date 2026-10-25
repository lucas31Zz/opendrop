import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Tauri expects a fixed dev port and no auto-open.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    watch: {
      // Cargo rewrites target/debug/*.exe on every rebuild; watching a
      // file that is locked makes Vite throw EBUSY and kill the whole
      // dev server. Frontend sources only.
      ignored: ["**/src-tauri/**"],
    },
  },
});
