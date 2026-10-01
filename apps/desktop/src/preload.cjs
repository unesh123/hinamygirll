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

  // UI Actuation & Events
  onUIAction: (action) => ipcRenderer.send("desktop:ui-action", action),
  onGlobalHotkey: (callback) => {
    ipcRenderer.on("desktop:hotkey-triggered", (_event, hotkey) => callback(hotkey));
  },
});
