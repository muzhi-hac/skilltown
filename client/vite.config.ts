import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API is same-origin in production (FastAPI serves this build); in dev the
// backend runs on :8000, so proxy instead of enabling CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
