/**
 * HINAA Frontier OS v2 Native Desktop Main Process.
 *
 * Implements:
 * 1. Frameless Windows Workspace with Custom Cyberpunk Titlebar
 * 2. Floating Companion Overlay Mode (Transparent, Always-On-Top 3D Avatar Island)
 * 3. System Tray Daemon with quick summoning
 * 4. Global Hotkeys (Alt+Space / Ctrl+Shift+H)
 * 5. Native OS Hardware & Telemetry Bridge
 */

const { app, BrowserWindow, ipcMain, globalShortcut, Tray, Menu, screen, desktopCapturer } = require("electron");
const path = require("path");
const os = require("os");
const fs = require("fs");

let mainWindow = null;
let tray = null;
let currentWindowMode = "standard"; // "standard" | "floating_companion" | "compact_bar" | "full_screen"
let isAlwaysOnTop = false;

const DEFAULT_WIDTH = 1280;
const DEFAULT_HEIGHT = 860;
const COMPANION_WIDTH = 380;
const COMPANION_HEIGHT = 560;
const COMPACT_WIDTH = 540;
const COMPACT_HEIGHT = 100;

function getAppUrl() {
  const isDev = process.argv.includes("--dev");
  const localDist = path.join(__dirname, "../../web/dist/index.html");

  // In production or when dist exists, load local dist or production vercel URL
  if (fs.existsSync(localDist)) {
    return `file://${localDist}`;
  }
  return "https://hinaa-workspace.vercel.app";
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
      webSecurity: true,
    },
    icon: path.join(__dirname, "../../web/public/favicon.svg"),
  });

  const appUrl = getAppUrl();
  console.log(`[HINAA Desktop] Loading interface from: ${appUrl}`);

  if (appUrl.startsWith("file://")) {
    mainWindow.loadFile(appUrl.replace("file://", ""));
  } else {
    mainWindow.loadURL(appUrl);
  }

  // Handle window close -> minimize to tray instead of quitting
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
    // Can trigger OS level actions if requested (e.g. window mode)
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
  // Global Summon Hotkey: Alt+Space or Ctrl+Shift+H
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

app.whenReady().then(() => {
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
});
