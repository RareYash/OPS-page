import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/auth": {
        target: process.env.VITE_BACKEND_URL || "http://localhost:8000",
        changeOrigin: true,
      },
      "/items": {
        target: process.env.VITE_BACKEND_URL || "http://localhost:8000",
        changeOrigin: true,
      },
      "/dashboard": {
        target: process.env.VITE_BACKEND_URL || "http://localhost:8000",
        changeOrigin: true,
      },
      "/notifications": {
        target: process.env.VITE_BACKEND_URL || "http://localhost:8000",
        changeOrigin: true,
      },
      "/teams": {
        target: process.env.VITE_BACKEND_URL || "http://localhost:8000",
        changeOrigin: true,
      },
      "/health": {
        target: process.env.VITE_BACKEND_URL || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
