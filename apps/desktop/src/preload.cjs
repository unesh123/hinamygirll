/**
 * HINAA Desktop Application Preload Script.
 * Securely bridges native Windows OS primitives and Electron window controls to the web frontend.
 */

const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("hinaaDesktop", {
  isDesktop: true,
  version: "2.0.0",
  platform: process.platform,

  // Window Controls
  setWindowMode: (mode) => ipcRenderer.send("desktop:set-window-mode", mode),
  toggleAlwaysOnTop: () => ipcRenderer.invoke("desktop:toggle-always-on-top"),
  minimizeWindow: () => ipcRenderer.send("desktop:minimize"),
  maximizeWindow: () => ipcRenderer.send("desktop:maximize"),
  closeWindow: () => ipcRenderer.send("desktop:close"),

  // System & OS Telemetry
  getSystemMetrics: () => ipcRenderer.invoke("desktop:get-system-metrics"),
  takeDesktopScreenshot: () => ipcRenderer.invoke("desktop:take-screenshot"),

  // Native App & Media Control
  launchApp: (target) => ipcRenderer.invoke("desktop:launch-app", target),
  controlMedia: (action) => ipcRenderer.invoke("desktop:media-control", action),
  openExternal: (url) => ipcRenderer.invoke("desktop:open-external", url),
  getRunningApps: () => ipcRenderer.invoke("desktop:get-running-apps"),
  executeAction: (params) => ipcRenderer.invoke("desktop:execute-action", params),

  // UI Actuation & Events
  onUIAction: (action) => ipcRenderer.send("desktop:ui-action", action),
  onGlobalHotkey: (callback) => {
    ipcRenderer.on("desktop:hotkey-triggered", (_event, hotkey) => callback(hotkey));
  },
  onWindowModeChanged: (callback) => {
    ipcRenderer.on("desktop:window-mode-changed", (_event, mode) => callback(mode));
  },
});

// Forward desktop:window-mode-changed to DOM CustomEvent on window
ipcRenderer.on("desktop:window-mode-changed", (_event, mode) => {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("desktop:window-mode-changed", { detail: mode }));
  }
});
