/**
 * HINAA Desktop Native Titlebar Component.
 * Automatically renders when running inside Electron frameless window mode.
 */

import React, { useState, useEffect } from "react";
import { Minus, Square, X, Pin, Sparkles, Monitor, AppWindow } from "lucide-react";

export function DesktopTitleBar() {
  const [isDesktop, setIsDesktop] = useState(false);
  const [isAlwaysOnTop, setIsAlwaysOnTop] = useState(false);
  const [windowMode, setWindowMode] = useState<"standard" | "floating_companion" | "compact_bar" | "full_screen">("standard");

  useEffect(() => {
    if (typeof window !== "undefined" && (window as any).hinaaDesktop) {
      setIsDesktop(true);

      // Listen for window mode changes from Electron
      const handler = (event: any) => {
        if (event.detail) setWindowMode(event.detail);
      };
      window.addEventListener("desktop:window-mode-changed", handler);
      return () => window.removeEventListener("desktop:window-mode-changed", handler);
    }
  }, []);

  if (!isDesktop) return null;

  const desktopApi = (window as any).hinaaDesktop;

  const handleTogglePin = async () => {
    if (desktopApi?.toggleAlwaysOnTop) {
      const state = await desktopApi.toggleAlwaysOnTop();
      setIsAlwaysOnTop(state);
    }
  };

  const handleModeChange = (mode: "standard" | "floating_companion" | "compact_bar") => {
    setWindowMode(mode);
    desktopApi?.setWindowMode(mode);
  };

  return (
    <div
      style={{
        height: "32px",
        background: "rgba(10, 10, 12, 0.95)",
        backdropFilter: "blur(12px)",
        borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 8px 0 12px",
        userSelect: "none",
        WebkitAppRegion: "drag", // Makes titlebar draggable in Electron
        zIndex: 99999,
        fontSize: "11px",
        color: "#a1a1aa",
      } as any}
    >
      {/* Left: Branding & Status */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <div style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#a855f7", boxShadow: "0 0 8px #a855f7" }} />
        <span style={{ fontWeight: 700, color: "#f4f4f5", letterSpacing: "0.5px" }}>HINAA DESKTOP OS</span>
        <span style={{ fontSize: "10px", padding: "1px 5px", borderRadius: "4px", background: "rgba(168,85,247,0.15)", color: "#c084fc", fontFamily: "monospace" }}>
          v2.0
        </span>
      </div>

      {/* Center: Desktop Mode Switcher */}
      <div style={{ display: "flex", alignItems: "center", gap: "4px", WebkitAppRegion: "no-drag" } as any}>
        <button
          onClick={() => handleModeChange("standard")}
          style={{
            padding: "2px 8px",
            borderRadius: "4px",
            border: "none",
            background: windowMode === "standard" ? "rgba(255,255,255,0.12)" : "transparent",
            color: windowMode === "standard" ? "#fff" : "#71717a",
            cursor: "pointer",
            fontSize: "10px",
            display: "flex",
            alignItems: "center",
            gap: "4px",
          }}
          title="Full Workspace Mode"
        >
          <AppWindow size={11} /> Workspace
        </button>
        <button
          onClick={() => handleModeChange("floating_companion")}
          style={{
            padding: "2px 8px",
            borderRadius: "4px",
            border: "none",
            background: windowMode === "floating_companion" ? "rgba(168,85,247,0.2)" : "transparent",
            color: windowMode === "floating_companion" ? "#c084fc" : "#71717a",
            cursor: "pointer",
            fontSize: "10px",
            display: "flex",
            alignItems: "center",
            gap: "4px",
          }}
          title="Floating 3D Companion Dock"
        >
          <Sparkles size={11} /> Floating Companion
        </button>
        <button
          onClick={() => handleModeChange("compact_bar")}
          style={{
            padding: "2px 8px",
            borderRadius: "4px",
            border: "none",
            background: windowMode === "compact_bar" ? "rgba(56,189,248,0.2)" : "transparent",
            color: windowMode === "compact_bar" ? "#38bdf8" : "#71717a",
            cursor: "pointer",
            fontSize: "10px",
            display: "flex",
            alignItems: "center",
            gap: "4px",
          }}
          title="Minimal Floating Command Bar"
        >
          <Monitor size={11} /> Command Bar
        </button>
      </div>

      {/* Right: Window Controls */}
      <div style={{ display: "flex", alignItems: "center", gap: "2px", WebkitAppRegion: "no-drag" } as any}>
        <button
          onClick={handleTogglePin}
          style={{
            width: "28px",
            height: "24px",
            border: "none",
            background: isAlwaysOnTop ? "rgba(168,85,247,0.25)" : "transparent",
            color: isAlwaysOnTop ? "#c084fc" : "#a1a1aa",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            borderRadius: "4px",
          }}
          title={isAlwaysOnTop ? "Unpin Window" : "Pin Always On Top"}
        >
          <Pin size={12} style={{ transform: isAlwaysOnTop ? "rotate(45deg)" : "none" }} />
        </button>
        <button
          onClick={() => desktopApi?.minimizeWindow()}
          style={{
            width: "28px",
            height: "24px",
            border: "none",
            background: "transparent",
            color: "#a1a1aa",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            borderRadius: "4px",
          }}
          title="Minimize"
        >
          <Minus size={12} />
        </button>
        <button
          onClick={() => desktopApi?.maximizeWindow()}
          style={{
            width: "28px",
            height: "24px",
            border: "none",
            background: "transparent",
            color: "#a1a1aa",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            borderRadius: "4px",
          }}
          title="Maximize"
        >
          <Square size={11} />
        </button>
        <button
          onClick={() => desktopApi?.closeWindow()}
          style={{
            width: "28px",
            height: "24px",
            border: "none",
            background: "transparent",
            color: "#ef4444",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            borderRadius: "4px",
          }}
          title="Close to Tray"
        >
          <X size={13} />
        </button>
      </div>
    </div>
  );
}
