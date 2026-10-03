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

const { app, BrowserWindow, ipcMain, globalShortcut, Tray, Menu, screen, desktopCapturer, shell } = require("electron");
const { exec } = require("child_process");
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

  if (mode === "dynamic_island") {
    // Dock to top-center as a sleek Dynamic Island Companion Bar
    const ISLAND_WIDTH = 680;
    const ISLAND_HEIGHT = 220;
    mainWindow.setAlwaysOnTop(true, "screen-saver");
    mainWindow.setResizable(false);
    mainWindow.setSize(ISLAND_WIDTH, ISLAND_HEIGHT, true);
    mainWindow.setPosition(Math.round((screenWidth - ISLAND_WIDTH) / 2), 12, true);
    mainWindow.webContents.send("desktop:window-mode-changed", "dynamic_island");
  } else if (mode === "floating_companion") {
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

  // Native Application & External URL Launcher
  ipcMain.handle("desktop:launch-app", async (_event, target) => {
    try {
      if (!target) return { success: false, error: "No target specified" };
      const trimmed = target.trim();
      if (trimmed.startsWith("http://") || trimmed.startsWith("https://") || trimmed.startsWith("spotify:")) {
        await shell.openExternal(trimmed);
        return { success: true, target: trimmed, action: "opened_external_url" };
      }

      const appMap = {
        spotify: "spotify",
        whatsapp: "whatsapp",
        chrome: "chrome",
        edge: "msedge",
        discord: "discord",
        notepad: "notepad",
        calc: "calc",
        calculator: "calc",
        code: "code",
        vscode: "code",
        terminal: "wt",
        cmd: "cmd",
        explorer: "explorer",
        files: "explorer",
        youtube: "https://www.youtube.com",
      };
      const resolved = appMap[trimmed.toLowerCase()] || trimmed;

      if (resolved.startsWith("http://") || resolved.startsWith("https://")) {
        await shell.openExternal(resolved);
        return { success: true, target: resolved, action: "opened_external_url" };
      }

      return new Promise((resolve) => {
        const safeTarget = resolved.replace(/'/g, "''").replace(/"/g, '');
        const psScript = `
          $target = '${safeTarget}'
          $ws = New-Object -ComObject WScript.Shell
          $activated = $ws.AppActivate($target)
          if (-not $activated) {
            $found = Get-StartApps | Where-Object { $_.Name -match $target -or $_.AppID -match $target } | Select-Object -First 1
            if ($found) {
              Start-Process "shell:AppsFolder\\$($found.AppID)" -ErrorAction SilentlyContinue
            } else {
              Start-Process $target -ErrorAction SilentlyContinue
            }
          }
        `;
        exec(`powershell -NoProfile -Command "${psScript.replace(/"/g, '\\"')}"`, (err) => {
          if (err) {
            exec(`start "" "${resolved}"`, (startErr) => {
              if (startErr) resolve({ success: false, error: startErr.message });
              else resolve({ success: true, target: resolved, action: "started_process" });
            });
          } else {
            resolve({ success: true, target: resolved, action: "activated_or_started" });
          }
        });
      });
    } catch (e) {
      return { success: false, error: e.message };
    }
  });

  // Native Windows Media Keys Bridge
  ipcMain.handle("desktop:media-control", async (_event, action) => {
    try {
      const keyCodes = {
        play: 179,
        pause: 179,
        toggle: 179,
        next: 176,
        prev: 177,
        previous: 177,
        mute: 173,
        voldown: 174,
        volup: 175,
      };
      const code = keyCodes[String(action).toLowerCase()] || 179;
      const ps = `
        $sig = '[DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, int dwExtraInfo);'
        $type = Add-Type -MemberDefinition $sig -Name "Win32KeybdMedia_${Date.now()}" -Namespace "Win32" -PassThru
        $type::keybd_event(${code}, 0, 0, 0)
        $type::keybd_event(${code}, 0, 2, 0)
      `;
      return new Promise((resolve) => {
        exec(`powershell -NoProfile -Command "${ps.replace(/"/g, '\\"')}"`, (err) => {
          if (err) resolve({ success: false, error: err.message });
          else resolve({ success: true, action });
        });
      });
    } catch (e) {
      return { success: false, error: e.message };
    }
  });

  // External URL Navigation
  ipcMain.handle("desktop:open-external", async (_event, url) => {
    try {
      await shell.openExternal(url);
      return { success: true, url };
    } catch (e) {
      return { success: false, error: e.message };
    }
  });

  // Enumerate Running Windows Applications
  ipcMain.handle("desktop:get-running-apps", async () => {
    return new Promise((resolve) => {
      exec('powershell -NoProfile -Command "Get-Process | Where-Object { $_.MainWindowTitle } | Select-Object -Property Id, ProcessName, MainWindowTitle | ConvertTo-Json"', (err, stdout) => {
        if (err) return resolve([]);
        try {
          const apps = JSON.parse(stdout);
          resolve(Array.isArray(apps) ? apps : [apps]);
        } catch {
          resolve([]);
        }
      });
    });
  });

  // General OS & Native Desktop Action Execution Bridge
  ipcMain.handle("desktop:execute-action", async (_event, params) => {
    try {
      const { action, target, content, keys, direction, amount } = params || {};
      const act = String(action || "").toLowerCase().trim();

      if (act === "scroll") {
        const dir = direction === "up" ? "up" : "down";
        const delta = (amount || 3) * (dir === "down" ? -120 : 120);
        const ps = `
          $sig = '[DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, int dx, int dy, int dwData, int dwExtraInfo);'
          $type = Add-Type -MemberDefinition $sig -Name "Win32Scroll_${Date.now()}" -Namespace "Win32" -PassThru
          $type::mouse_event(0x0800, 0, 0, ${delta}, 0)
        `;
        return new Promise((resolve) => {
          exec(`powershell -NoProfile -Command "${ps.replace(/"/g, '\\"')}"`, (err) => {
            resolve({ success: !err, action: "scroll", direction: dir });
          });
        });
      } else if (act === "click") {
        const ps = `
          $sig = '[DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, int dx, int dy, int dwData, int dwExtraInfo);'
          $type = Add-Type -MemberDefinition $sig -Name "Win32Click_${Date.now()}" -Namespace "Win32" -PassThru
          $type::mouse_event(0x02, 0, 0, 0, 0)
          $type::mouse_event(0x04, 0, 0, 0, 0)
        `;
        return new Promise((resolve) => {
          exec(`powershell -NoProfile -Command "${ps.replace(/"/g, '\\"')}"`, (err) => {
            resolve({ success: !err, action: "click" });
          });
        });
      } else if (act === "type_text" || act === "type") {
        const textToType = (content || target || "").replace(/'/g, "''");
        const ps = `
          $ws = New-Object -ComObject WScript.Shell
          $ws.SendKeys('${textToType}')
        `;
        return new Promise((resolve) => {
          exec(`powershell -NoProfile -Command "${ps.replace(/"/g, '\\"')}"`, (err) => {
            resolve({ success: !err, action: "type_text" });
          });
        });
      } else if (act === "press_hotkey" || act === "hotkey") {
        const hotkey = (keys || target || "enter").toLowerCase();
        const map = { enter: "{ENTER}", escape: "{ESC}", tab: "{TAB}", "ctrl+f": "^f", "ctrl+a": "^a", space: " " };
        const mapped = map[hotkey] || hotkey;
        const ps = `
          $ws = New-Object -ComObject WScript.Shell
          $ws.SendKeys('${mapped}')
        `;
        return new Promise((resolve) => {
          exec(`powershell -NoProfile -Command "${ps.replace(/"/g, '\\"')}"`, (err) => {
            resolve({ success: !err, action: "press_hotkey", key: hotkey });
          });
        });
      }
      return { success: false, error: `Unhandled action: ${action}` };
    } catch (e) {
      return { success: false, error: e.message };
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
        label: "🏝 Dynamic Island (Coucou Mode)",
        click: () => {
          if (mainWindow) {
            mainWindow.show();
            setWindowMode("dynamic_island");
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

    globalShortcut.register("CommandOrControl+Shift+I", () => {
      if (mainWindow) {
        mainWindow.show();
        mainWindow.focus();
        setWindowMode(currentWindowMode === "dynamic_island" ? "standard" : "dynamic_island");
      }
    });
  } catch (err) {
    console.warn("Hotkey registration failed:", err.message);
  }
}

let backendProcess = null;

function checkBackendHealth(timeoutMs = 800) {
  return new Promise((resolve) => {
    const req = http.get("http://127.0.0.1:8000/health", (res) => {
      resolve(res.statusCode === 200);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(timeoutMs, () => {
      req.destroy();
      resolve(false);
    });
  });
}

async function ensureBackendRunning() {
  const isHealthy = await checkBackendHealth(800);
  if (isHealthy) {
    console.log("[HINAA Desktop] Local Python backend already running on http://127.0.0.1:8000");
    return;
  }

  console.log("[HINAA Desktop] Backend not detected on port 8000. Auto-spawning local Python backend...");
  const workspaceRoot = path.resolve(__dirname, "../../..");
  const apiDir = path.join(workspaceRoot, "apps", "api");
  const winPython = path.join(apiDir, ".venv", "Scripts", "python.exe");
  const unixPython = path.join(apiDir, ".venv", "bin", "python");

  let pythonPath = "python";
  if (fs.existsSync(winPython)) {
    pythonPath = winPython;
  } else if (fs.existsSync(unixPython)) {
    pythonPath = unixPython;
  }

  try {
    const { spawn } = require("child_process");
    backendProcess = spawn(
      pythonPath,
      ["-m", "uvicorn", "hinaa_api.main:app", "--host", "127.0.0.1", "--port", "8000"],
      {
        cwd: apiDir,
        env: {
          ...process.env,
          PYTHONPATH: apiDir,
        },
        stdio: ["ignore", "pipe", "pipe"],
      }
    );

    backendProcess.stdout.on("data", (data) => {
      const line = data.toString().trim();
      if (line) console.log(`[HINAA Backend] ${line}`);
    });

    backendProcess.stderr.on("data", (data) => {
      const line = data.toString().trim();
      if (line) console.warn(`[HINAA Backend ERR] ${line}`);
    });

    backendProcess.on("exit", (code, signal) => {
      console.log(`[HINAA Desktop] Backend process exited (code=${code}, signal=${signal})`);
      backendProcess = null;
    });

    // Wait up to 8 seconds for backend to become healthy
    for (let i = 0; i < 16; i++) {
      await new Promise((r) => setTimeout(r, 500));
      if (await checkBackendHealth(400)) {
        console.log("[HINAA Desktop] Local Python backend is ready on port 8000!");
        break;
      }
    }
  } catch (err) {
    console.error("[HINAA Desktop] Failed to auto-spawn backend process:", err.message);
  }
}

function cleanupBackend() {
  if (backendProcess && !backendProcess.killed) {
    console.log("[HINAA Desktop] Terminating spawned backend process...");
    try {
      if (process.platform === "win32") {
        exec(`taskkill /pid ${backendProcess.pid} /T /F`);
      } else {
        backendProcess.kill("SIGTERM");
      }
    } catch {
      // ignore
    }
    backendProcess = null;
  }
}

app.whenReady().then(async () => {
  // Ensure local python backend is operational before opening workspace
  await ensureBackendRunning();

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
  cleanupBackend();
});

