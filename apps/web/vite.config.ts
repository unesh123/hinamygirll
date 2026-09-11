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
    // Allow sandboxed/tunneled preview hosts (e.g. Arena's *.e2b.app proxy)
    // to reach the dev server. Dev-only; builds are static and unaffected.
    allowedHosts: true,
    https,
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
      devOptions: {
        enabled: false,
      },
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
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          const normalized = id.replace(/\\/g, "/");
          const packagePath = normalized.split("/node_modules/").pop() ?? "";
          const parts = packagePath.split("/");
          const packageName = parts[0]?.startsWith("@")
            ? `${parts[0]}/${parts[1] ?? ""}`
            : parts[0];
          if (
            ["react", "react-dom", "react-router-dom", "react-reconciler", "scheduler", "use-sync-external-store"].includes(packageName)
          ) {
            return "vendor-react";
          }
          if (packageName === "three") return "vendor-three";
          if (packageName === "three-stdlib") return "vendor-three-stdlib";
          if (packageName.startsWith("@react-three/")) return "vendor-react-three";
          if (packageName.startsWith("@pixiv/")) return "vendor-vrm";
          if (
            ["framer-motion", "gsap", "ogl"].includes(packageName) ||
            packageName.startsWith("@react-spring/")
          ) {
            return "vendor-motion";
          }
          if (
            ["lucide-react", "zod", "clsx", "tailwind-merge", "class-variance-authority"].includes(packageName) ||
            packageName.startsWith("@radix-ui/")
          ) {
            return "vendor-ui";
          }
          if (packageName.startsWith("@clerk/")) {
            return "vendor-auth";
          }
          return `vendor-${packageName.replace("@", "").replace("/", "-").replace(/[^a-zA-Z0-9_-]/g, "") || "misc"}`;
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    exclude: ["tests/e2e/**", "node_modules/**", "dist/**"],
    restoreMocks: true,
  },
});
