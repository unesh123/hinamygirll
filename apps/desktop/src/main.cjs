/**
 * HINAA Frontier OS v2 Native Desktop Main Process.
 *
 * Implements:
 * 1. Embedded Local HTTP & Asset Server (zero file:// restrictions, full AudioWorklet & WebGL support)
 * 2. Frameless Windows Workspace with Custom Titlebar & Mode Switcher
 * 3. Floating Companion Overlay Mode (Transparent, Always-On-Top 3D Avatar Island)
 * 4. System Tray Daemon with quick summoning
 * 5. Global Hotkeys (Alt+Space / Ctrl+Shift+H)
 * 6. Native OS Hardware & Telemetry Bridge
 */

const { app, BrowserWindow, ipcMain, globalShortcut, Tray, Menu, screen, desktopCapturer } = require("electron");
const path = require("path");
const os = require("os");
const fs = require("fs");
const http = require("http");
const https = require("https");

let mainWindow = null;
let tray = null;
let currentWindowMode = "standard"; // "standard" | "floating_companion" | "compact_bar" | "full_screen"
let isAlwaysOnTop = false;
let localServerPort = 0;

const DEFAULT_WIDTH = 1280;
const DEFAULT_HEIGHT = 860;
const COMPANION_WIDTH = 380;
const COMPANION_HEIGHT = 560;
const COMPACT_WIDTH = 540;
const COMPACT_HEIGHT = 100;

const MIME_TYPES = {
  ".html": "text/html",
  ".js": "text/javascript",
  ".mjs": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
  ".vrm": "application/octet-stream",
  ".glb": "model/gltf-binary",
  ".gltf": "model/gltf+json",
  ".wasm": "application/wasm",
  ".mp3": "audio/mpeg",
  ".wav": "audio/wav",
  ".webm": "video/webm",
  ".webmanifest": "application/manifest+json",
};

/**
 * Starts an embedded local HTTP server to serve the Vite dist build cleanly.
 * This completely avoids file:// protocol restrictions on ES modules, AudioWorklets, and WebGL.
 */
function startStaticServer(distDir) {
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      try {
        const parsedUrl = new URL(req.url, "http://127.0.0.1");
        let pathname = decodeURIComponent(parsedUrl.pathname);

        // Reverse proxy /api, /v1, /health to local backend on port 8000 (with cloud failover)
        if (
          pathname.startsWith("/api/") ||
          pathname.startsWith("/v1/") ||
          pathname === "/health"
        ) {
          const bodyChunks = [];
          req.on("data", (chunk) => bodyChunks.push(chunk));
          req.on("end", () => {
            const bodyBuffer = Buffer.concat(bodyChunks);

            const forwardToCloud = () => {
              const cloudOptions = {
                hostname: "hinaa-workspace.vercel.app",
                port: 443,
                path: req.url,
                method: req.method,
                headers: {
                  ...req.headers,
                  host: "hinaa-workspace.vercel.app",
                },
              };
              const cloudReq = https.request(cloudOptions, (cloudRes) => {
                res.writeHead(cloudRes.statusCode, cloudRes.headers);
                cloudRes.pipe(res);
              });
              cloudReq.on("error", (err) => {
                res.writeHead(502, { "Content-Type": "application/json" });
                res.end(JSON.stringify({ error: "Backend unreachable (local & cloud)", detail: err.message }));
              });
              cloudReq.end(bodyBuffer);
            };

            const backendPort = 8000;
            const localOptions = {
              hostname: "127.0.0.1",
              port: backendPort,
              path: req.url,
              method: req.method,
              headers: {
                ...req.headers,
                host: `127.0.0.1:${backendPort}`,
              },
            };

            const proxyReq = http.request(localOptions, (proxyRes) => {
              res.writeHead(proxyRes.statusCode, proxyRes.headers);
              proxyRes.pipe(res);
            });

            proxyReq.on("error", () => {
              // Local backend not reachable on 8000; seamlessly fall back to cloud Vercel deployment!
              forwardToCloud();
            });

            proxyReq.end(bodyBuffer);
          });
          return;
        }

        // Static file serving from distDir
        let filePath = path.join(distDir, pathname);

        if (pathname === "/" || pathname === "") {
          filePath = path.join(distDir, "index.html");
        }

        fs.stat(filePath, (err, stats) => {
          if (!err && stats.isFile()) {
            const ext = path.extname(filePath).toLowerCase();
            const contentType = MIME_TYPES[ext] || "application/octet-stream";
            res.writeHead(200, {
              "Content-Type": contentType,
              "Access-Control-Allow-Origin": "*",
            });
            fs.createReadStream(filePath).pipe(res);
          } else {
            // SPA Fallback: serve index.html for client-side navigation
            const indexPath = path.join(distDir, "index.html");
            fs.stat(indexPath, (idxErr, idxStats) => {
              if (!idxErr && idxStats.isFile()) {
                res.writeHead(200, {
                  "Content-Type": "text/html",
                  "Access-Control-Allow-Origin": "*",
                });
                fs.createReadStream(indexPath).pipe(res);
              } else {
                res.writeHead(404, { "Content-Type": "text/plain" });
                res.end("HINAA dist not found. Please build the web frontend first.");
              }
            });
          }
        });
      } catch (e) {
        res.writeHead(500, { "Content-Type": "text/plain" });
        res.end(e.message);
      }
    });

    // Proxy WebSocket upgrades (e.g. /v1/realtime)
    server.on("upgrade", (req, socket, _head) => {
      const proxyReq = http.request({
        hostname: "127.0.0.1",
        port: 8000,
        path: req.url,
        method: req.method,
        headers: req.headers,
      });

      proxyReq.on("upgrade", (proxyRes, proxySocket, _proxyHead) => {
        socket.write(
          `HTTP/1.1 101 Switching Protocols\r\n` +
          Object.entries(proxyRes.headers)
            .map(([k, v]) => `${k}: ${v}\r\n`)
            .join("") +
          `\r\n`
        );
        proxySocket.pipe(socket);
        socket.pipe(proxySocket);
      });

      proxyReq.on("error", () => {
        socket.destroy();
      });

      proxyReq.end();
    });

    server.listen(0, "127.0.0.1", () => {
      localServerPort = server.address().port;
      console.log(`[HINAA Desktop] Embedded server listening on http://127.0.0.1:${localServerPort}`);
      resolve(localServerPort);
    });

    server.on("error", reject);
  });
}

function createWindow() {
  const primaryDisplay = screen.getPrimaryDisplay();
  const { width: screenWidth, height: screenHeight } = primaryDisplay.workAreaSize;

  mainWindow = new BrowserWindow({
    width: DEFAULT_WIDTH,
    height: DEFAULT_HEIGHT,
    x: Math.round((screenWidth - DEFAULT_WIDTH) / 2),
    y: Math.round((screenHeight - DEFAULT_HEIGHT) / 2),
    minWidth: 360,
    minHeight: 100,
    frame: false,
    transparent: false,
    backgroundColor: "#0a0a0c",
    hasShadow: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false,
      webSecurity: false,
    },
    icon: path.join(__dirname, "../../web/public/favicon.svg"),
  });

  const isDev = process.argv.includes("--dev");
  let appUrl = "";

  if (isDev) {
    appUrl = "http://localhost:5173";
  } else if (localServerPort) {
    appUrl = `http://127.0.0.1:${localServerPort}`;
  } else {
    appUrl = "https://hinaa-workspace.vercel.app";
  }

  console.log(`[HINAA Desktop] Loading interface from: ${appUrl}`);
  mainWindow.loadURL(appUrl);

  // Fallback to production cloud if local load fails
  mainWindow.webContents.on("did-fail-load", (_event, errorCode, errorDescription, validatedURL) => {
    console.error(`[HINAA Desktop] Failed to load: ${validatedURL} (${errorCode}: ${errorDescription})`);
    if (validatedURL !== "https://hinaa-workspace.vercel.app") {
      console.log("[HINAA Desktop] Falling back to production Vercel deployment...");
      mainWindow.loadURL("https://hinaa-workspace.vercel.app");
    }
  });

  // DevTools toggle with F12 or Ctrl+Shift+I
  mainWindow.webContents.on("before-input-event", (event, input) => {
    if (input.key === "F12" || (input.control && input.shift && input.key.toLowerCase() === "i")) {
      mainWindow.webContents.toggleDevTools();
      event.preventDefault();
    }
  });

  // Minimize to tray instead of quitting
  mainWindow.on("close", (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  // Setup IPC Handlers
  setupIpcHandlers();

  // Setup System Tray
  createTray();

  // Register Global Hotkeys
  registerHotkeys();
}

function setWindowMode(mode) {
  if (!mainWindow) return;
  const primaryDisplay = screen.getPrimaryDisplay();
  const { width: screenWidth, height: screenHeight } = primaryDisplay.workAreaSize;

  currentWindowMode = mode;

  if (mode === "floating_companion") {
    // Dock to bottom-right corner as a floating companion
    mainWindow.setAlwaysOnTop(true, "screen-saver");
    mainWindow.setResizable(false);
    mainWindow.setSize(COMPANION_WIDTH, COMPANION_HEIGHT, true);
    mainWindow.setPosition(screenWidth - COMPANION_WIDTH - 24, screenHeight - COMPANION_HEIGHT - 24, true);
    mainWindow.webContents.send("desktop:window-mode-changed", "floating_companion");
  } else if (mode === "compact_bar") {
    // Dock to bottom-center as a command bar
    mainWindow.setAlwaysOnTop(true, "floating");
    mainWindow.setResizable(false);
    mainWindow.setSize(COMPACT_WIDTH, COMPACT_HEIGHT, true);
    mainWindow.setPosition(Math.round((screenWidth - COMPACT_WIDTH) / 2), screenHeight - COMPACT_HEIGHT - 32, true);
    mainWindow.webContents.send("desktop:window-mode-changed", "compact_bar");
  } else if (mode === "full_screen") {
    mainWindow.setAlwaysOnTop(false);
    mainWindow.setResizable(true);
    mainWindow.maximize();
    mainWindow.webContents.send("desktop:window-mode-changed", "full_screen");
  } else {
    // Standard workspace window
    mainWindow.setAlwaysOnTop(isAlwaysOnTop);
    mainWindow.setResizable(true);
    mainWindow.setSize(DEFAULT_WIDTH, DEFAULT_HEIGHT, true);
    mainWindow.setPosition(Math.round((screenWidth - DEFAULT_WIDTH) / 2), Math.round((screenHeight - DEFAULT_HEIGHT) / 2), true);
    mainWindow.webContents.send("desktop:window-mode-changed", "standard");
  }
}

function setupIpcHandlers() {
  ipcMain.on("desktop:set-window-mode", (_event, mode) => {
    setWindowMode(mode);
  });

  ipcMain.handle("desktop:toggle-always-on-top", () => {
    if (!mainWindow) return false;
    isAlwaysOnTop = !isAlwaysOnTop;
    mainWindow.setAlwaysOnTop(isAlwaysOnTop);
    return isAlwaysOnTop;
  });

  ipcMain.on("desktop:minimize", () => {
    if (mainWindow) mainWindow.minimize();
  });

  ipcMain.on("desktop:maximize", () => {
    if (mainWindow) {
      if (mainWindow.isMaximized()) mainWindow.unmaximize();
      else mainWindow.maximize();
    }
  });

  ipcMain.on("desktop:close", () => {
    if (mainWindow) mainWindow.hide();
  });

  ipcMain.handle("desktop:get-system-metrics", () => {
    return {
      platform: os.platform(),
      release: os.release(),
      arch: os.arch(),
      totalMemMB: Math.round(os.totalmem() / (1024 * 1024)),
      freeMemMB: Math.round(os.freemem() / (1024 * 1024)),
      cpusCount: os.cpus().length,
      uptimeSec: os.uptime(),
    };
  });

  ipcMain.handle("desktop:take-screenshot", async () => {
    try {
      const sources = await desktopCapturer.getSources({
        types: ["screen"],
        thumbnailSize: { width: 1920, height: 1080 },
      });
      if (sources.length > 0) {
        return sources[0].thumbnail.toDataURL();
      }
      return null;
    } catch (err) {
      console.error("Screenshot error:", err);
      return null;
    }
  });

  ipcMain.on("desktop:ui-action", (_event, action) => {
    console.log("[HINAA Desktop IPC] Received UI Action:", action);
    if (action.action === "desktop_window_mode" && action.window_mode) {
      setWindowMode(action.window_mode);
    }
  });
}

function createTray() {
  try {
    const iconPath = path.join(__dirname, "../../web/public/favicon.svg");
    tray = new Tray(iconPath);

    const contextMenu = Menu.buildFromTemplate([
      {
        label: "🌌 Show HINAA Workspace",
        click: () => {
          if (mainWindow) {
            mainWindow.show();
            setWindowMode("standard");
          }
        },
      },
      {
        label: "✨ Floating Companion Mode",
        click: () => {
          if (mainWindow) {
            mainWindow.show();
            setWindowMode("floating_companion");
          }
        },
      },
      {
        label: "⚡ Compact Command Bar",
        click: () => {
          if (mainWindow) {
            mainWindow.show();
            setWindowMode("compact_bar");
          }
        },
      },
      { type: "separator" },
      {
        label: "📌 Pin Always On Top",
        type: "checkbox",
        checked: isAlwaysOnTop,
        click: (item) => {
          isAlwaysOnTop = item.checked;
          if (mainWindow) mainWindow.setAlwaysOnTop(isAlwaysOnTop);
        },
      },
      { type: "separator" },
      {
        label: "❌ Quit HINAA",
        click: () => {
          app.isQuitting = true;
          app.quit();
        },
      },
    ]);

    tray.setToolTip("HINAA — Intelligent Desktop OS");
    tray.setContextMenu(contextMenu);
    tray.on("double-click", () => {
      if (mainWindow) {
        if (mainWindow.isVisible()) mainWindow.hide();
        else mainWindow.show();
      }
    });
  } catch (err) {
    console.warn("Could not create system tray:", err.message);
  }
}

function registerHotkeys() {
  try {
    globalShortcut.register("Alt+Space", () => {
      if (mainWindow) {
        if (mainWindow.isVisible() && mainWindow.isFocused()) {
          mainWindow.hide();
        } else {
          mainWindow.show();
          mainWindow.focus();
        }
      }
    });

    globalShortcut.register("CommandOrControl+Shift+H", () => {
      if (mainWindow) {
        mainWindow.show();
        mainWindow.focus();
      }
    });
  } catch (err) {
    console.warn("Hotkey registration failed:", err.message);
  }
}

app.whenReady().then(async () => {
  const distDir = path.join(__dirname, "../../web/dist");
  if (fs.existsSync(distDir)) {
    try {
      await startStaticServer(distDir);
    } catch (err) {
      console.warn("[HINAA Desktop] Embedded server failed to start, falling back to cloud:", err.message);
    }
  }

  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
});
