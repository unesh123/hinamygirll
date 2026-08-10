import { defineConfig } from "vitest/config";
import { readFileSync } from "node:fs";
import path from "node:path";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import tailwindcss from "@tailwindcss/vite";

// https://vite.dev/config/
const certPath = process.env.HINAA_DEV_CERT_PATH;
const keyPath = process.env.HINAA_DEV_KEY_PATH;
const https =
  certPath && keyPath
    ? { cert: readFileSync(certPath), key: readFileSync(keyPath) }
    : undefined;

export default defineConfig({
  server: {
    host: "0.0.0.0",
    https,
    // Allow reverse-proxied preview hosts (e.g. sandboxed *.e2b.app previews)
    // in addition to localhost/LAN dev access.
    allowedHosts: [".e2b.app"],
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: false,
        ws: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  preview: {
    allowedHosts: [".e2b.app"],
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: false,
        ws: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  plugins: [
    tailwindcss(),
    react(),
    {
      // Serves .vrm assets with a real MIME type (Vite has no built-in
      // mapping). Kept inline so it type-checks as a real Plugin for the
      // `tsc -b` step Playwright's webServer runs.
      name: "vrm-mime",
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          const url = req.url ?? "";
          if (url.split("?")[0].endsWith(".vrm")) {
            res.setHeader("Content-Type", "model/vrm");
          }
          next();
        });
      },
    },
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg"],
      manifest: {
        name: "HINAA Voice Companion",
        short_name: "HINAA",
        description:
          "Phase 3 realtime companion with offline mock and REST fallback",
        theme_color: "#120f1f",
        background_color: "#120f1f",
        display: "standalone",
        orientation: "any",
        start_url: "/",
        icons: [
          {
            src: "/favicon.svg",
            sizes: "any",
            type: "image/svg+xml",
            purpose: "any maskable",
          },
        ],
      },
      workbox: {
        navigateFallback: "/index.html",
        globPatterns: ["**/*.{js,css,html,svg,png}"],
      },
    }),
  ],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    exclude: ["tests/e2e/**", "node_modules/**", "dist/**"],
    restoreMocks: true,
  },
});
