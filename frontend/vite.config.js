import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// W trybie deweloperskim REST, WebSocket i zrzuty ekranu idą przez ten sam origin (proxy do API).
const API = process.env.IW_API_PROXY || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": API,
      "/socket.io": { target: API, ws: true },
    },
  },
  build: { chunkSizeWarningLimit: 900 },
});
