import React, { useState, useEffect, useRef, useCallback } from "react";
import ReactDOM from "react-dom";
import { motion } from "framer-motion";
import {
  Mic,
  MicOff,
  Video,
  Zap,
  Footprints,
  Maximize2,
  X,
  Smartphone
} from "lucide-react";
import { playUiSound } from "../../lib/uiSound";

export interface HinaFloatingOverlayProps {
  isOpen: boolean;
  onClose: () => void;
  companionName?: string;
  avatarModel?: string;
  isVoiceActive?: boolean;
  onToggleVoice?: () => void;
  isWalking?: boolean;
  onToggleWalk?: () => void;
  companionState?: "idle" | "listening" | "thinking" | "working" | "speaking" | string;
  onTriggerActionBurst?: (action: string) => void;
  onCaptureScreen?: () => void;
}

export const HinaFloatingOverlay: React.FC<HinaFloatingOverlayProps> = ({
  isOpen,
  onClose,
  companionName = "Hina",
  avatarModel,
  isVoiceActive = false,
  onToggleVoice,
  isWalking = true,
  onToggleWalk,
  companionState = "speaking",
  onTriggerActionBurst,
  onCaptureScreen,
}) => {
  const [pipWindow, setPipWindow] = useState<Window | null>(null);
  const [isPipSupported, setIsPipSupported] = useState(false);
  const [walkPhase, setWalkPhase] = useState(0);
  const [speechCue, setSpeechCue] = useState<string>("I'm right here with you, babe~ 💕");

  // Check documentPictureInPicture support
  useEffect(() => {
    if (typeof window !== "undefined" && "documentPictureInPicture" in window) {
      setIsPipSupported(true);
    }
  }, []);

  // Procedural walking animation loop
  useEffect(() => {
    let animId: number;
    let lastTime = performance.now();
    const loop = (time: number) => {
      const dt = (time - lastTime) / 1000;
      lastTime = time;
      if (isWalking) {
        setWalkPhase((prev) => (prev + dt * 5.4) % (Math.PI * 2));
      }
      animId = requestAnimationFrame(loop);
    };
    animId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animId);
  }, [isWalking]);

  // Request Document PiP Window
  const handleRequestPip = useCallback(async () => {
    if (typeof window === "undefined" || !("documentPictureInPicture" in window)) return;
    try {
      playUiSound("buttonPress");
      const pip = await (window as any).documentPictureInPicture.requestWindow({
        width: 270,
        height: 380,
      });

      // Clone styles
      [...document.styleSheets].forEach((sheet) => {
        try {
          if (sheet.href) {
            const link = pip.document.createElement("link");
            link.rel = "stylesheet";
            link.href = sheet.href;
            pip.document.head.appendChild(link);
          } else if (sheet.cssRules) {
            const style = pip.document.createElement("style");
            style.textContent = [...sheet.cssRules].map((r) => r.cssText).join("\n");
            pip.document.head.appendChild(style);
          }
        } catch {
          // cross-origin stylesheets handled gracefully
        }
      });

      pip.document.body.style.margin = "0";
      pip.document.body.style.padding = "0";
      pip.document.body.style.background = "#090a0f";
      pip.document.body.style.color = "#ffffff";
      pip.document.body.style.fontFamily = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
      pip.document.body.style.overflow = "hidden";

      pip.addEventListener("pagehide", () => {
        setPipWindow(null);
      });

      setPipWindow(pip);
    } catch (err) {
      console.warn("Document PiP request failed, falling back to in-app overlay:", err);
    }
  }, []);

  // Update speech cue based on state
  useEffect(() => {
    if (companionState === "listening") {
      setSpeechCue("I'm listening closely, sweetie... ✨");
    } else if (companionState === "thinking") {
      setSpeechCue("Reasoning through this for you, babe... 💭");
    } else if (companionState === "working") {
      setSpeechCue("Executing high-speed action burst! ⚡");
    } else if (companionState === "speaking") {
      setSpeechCue("Always here by your side, darling~ 💖");
    } else {
      setSpeechCue("Ready when you are, babe~ 🌸");
    }
  }, [companionState]);

  if (!isOpen) return null;

  // Walking kinematics calculation
  const phaseSin = Math.sin(walkPhase);
  const phaseCos = Math.cos(walkPhase);
  const legLeftAngle = isWalking ? phaseSin * 25 : 0;
  const legRightAngle = isWalking ? -phaseSin * 25 : 0;
  const armLeftAngle = isWalking ? -phaseSin * 22 : 0;
  const armRightAngle = isWalking ? phaseSin * 22 : 0;
  const bodyBob = isWalking ? Math.abs(phaseCos) * 3 : 0;

  // The Companion Content (rendered either in PiP Window or Draggable In-App Overlay)
  const overlayContent = (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        background: "linear-gradient(180deg, rgba(15, 17, 26, 0.96) 0%, rgba(9, 10, 15, 0.98) 100%)",
        borderRadius: pipWindow ? 0 : 20,
        boxShadow: pipWindow ? "none" : "0 16px 48px rgba(0, 0, 0, 0.55), 0 0 0 1px rgba(255, 255, 255, 0.12)",
        backdropFilter: "blur(24px)",
        WebkitBackdropFilter: "blur(24px)",
        overflow: "hidden",
        userSelect: "none",
        position: "relative",
      }}
    >
      {/* ── Top Header ────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 14px",
          background: "rgba(255, 255, 255, 0.04)",
          borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
          zIndex: 10,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: companionState === "speaking" ? "#10b981" : "#00d4ff",
              boxShadow: `0 0 8px ${companionState === "speaking" ? "#10b981" : "#00d4ff"}`,
            }}
          />
          <span style={{ fontSize: 12, fontWeight: 800, color: "#ffffff", letterSpacing: "0.04em" }}>
            {companionName}
          </span>
          <span style={{ fontSize: 10, color: "#ec4899", fontWeight: 700 }}>
            {isWalking ? "• WALKING" : "• IDLE"}
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
          {isPipSupported && !pipWindow && (
            <button
              type="button"
              onClick={handleRequestPip}
              title="Pop out into floating desktop Picture-in-Picture"
              style={{
                background: "rgba(255, 255, 255, 0.08)",
                border: "1px solid rgba(255, 255, 255, 0.12)",
                color: "#cbd5e1",
                borderRadius: 6,
                padding: "3px 6px",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
              }}
            >
              <Maximize2 size={12} />
            </button>
          )}

          <button
            type="button"
            onClick={() => {
              playUiSound("buttonPress");
              onToggleWalk?.();
            }}
            title={isWalking ? "Pause walking" : "Start walking"}
            style={{
              background: isWalking ? "rgba(236, 72, 153, 0.2)" : "rgba(255, 255, 255, 0.08)",
              border: isWalking ? "1px solid #ec4899" : "1px solid rgba(255, 255, 255, 0.12)",
              color: isWalking ? "#ec4899" : "#cbd5e1",
              borderRadius: 6,
              padding: "3px 6px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
            }}
          >
            <Footprints size={12} />
          </button>

          <button
            type="button"
            onClick={() => {
              if (pipWindow) pipWindow.close();
              onClose();
            }}
            title="Close companion"
            style={{
              background: "rgba(255, 255, 255, 0.08)",
              border: "none",
              color: "#94a3b8",
              borderRadius: 6,
              padding: "3px 6px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
            }}
          >
            <X size={12} />
          </button>
        </div>
      </div>

      {/* ── Main Interactive 3D Avatar & Walking Canvas ────────── */}
      <div
        style={{
          flex: 1,
          position: "relative",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          overflow: "hidden",
        }}
      >
        {/* Subtle background ambient halo */}
        <div
          style={{
            position: "absolute",
            width: 170,
            height: 170,
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(236, 72, 153, 0.22) 0%, rgba(0, 212, 255, 0.08) 50%, transparent 80%)",
            filter: "blur(20px)",
            pointerEvents: "none",
          }}
        />

        {/* 2D/3D Animated Locomotion Figure */}
        <div
          style={{
            transform: `translateY(${bodyBob}px)`,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            transition: isWalking ? "none" : "transform 0.2s ease",
            cursor: "pointer",
          }}
          onClick={() => {
            playUiSound("buttonPress");
            onToggleWalk?.();
          }}
        >
          <svg width="120" height="150" viewBox="0 0 120 150" fill="none">
            {/* Shadow */}
            <ellipse
              cx="60"
              cy="142"
              rx={32 - bodyBob * 1.5}
              ry="7"
              fill="rgba(0, 0, 0, 0.35)"
            />

            {/* Left Leg */}
            <g transform={`translate(52, 92) rotate(${legLeftAngle}) translate(-52, -92)`}>
              <line x1="52" y1="92" x2="50" y2="135" stroke="#ec4899" strokeWidth="6" strokeLinecap="round" />
              <circle cx="50" cy="136" r="4" fill="#ffffff" />
            </g>

            {/* Right Leg */}
            <g transform={`translate(68, 92) rotate(${legRightAngle}) translate(-68, -92)`}>
              <line x1="68" y1="92" x2="70" y2="135" stroke="#ec4899" strokeWidth="6" strokeLinecap="round" />
              <circle cx="70" cy="136" r="4" fill="#ffffff" />
            </g>

            {/* Torso & Couture Kimono Dress */}
            <path
              d="M48 55 C48 55 42 75 40 92 C40 95 80 95 80 92 C78 75 72 55 72 55 Z"
              fill="url(#hinaGradient)"
            />

            {/* Left Arm */}
            <g transform={`translate(46, 58) rotate(${armLeftAngle}) translate(-46, -58)`}>
              <line x1="46" y1="58" x2="38" y2="85" stroke="#ffffff" strokeWidth="4" strokeLinecap="round" />
            </g>

            {/* Right Arm */}
            <g transform={`translate(74, 58) rotate(${armRightAngle}) translate(-74, -58)`}>
              <line x1="74" y1="58" x2="82" y2="85" stroke="#ffffff" strokeWidth="4" strokeLinecap="round" />
            </g>

            {/* Head & Face */}
            <circle cx="60" cy="40" r="18" fill="#ffe4e6" />

            {/* Cute Anime Eyes */}
            <ellipse cx="54" cy="38" rx="2.5" ry={companionState === "speaking" ? 1.5 : 3.5} fill="#1e1b4b" />
            <ellipse cx="66" cy="38" rx="2.5" ry={companionState === "speaking" ? 1.5 : 3.5} fill="#1e1b4b" />
            <circle cx="55" cy="37" r="1" fill="#ffffff" />
            <circle cx="67" cy="37" r="1" fill="#ffffff" />

            {/* Cheeks blush */}
            <circle cx="50" cy="43" r="2.5" fill="rgba(244, 63, 94, 0.45)" />
            <circle cx="70" cy="43" r="2.5" fill="rgba(244, 63, 94, 0.45)" />

            {/* Cute Smile / Mouth */}
            <path
              d={companionState === "speaking" ? "M56 46 Q60 51 64 46" : "M57 46 Q60 49 63 46"}
              stroke="#e11d48"
              strokeWidth="1.8"
              strokeLinecap="round"
              fill={companionState === "speaking" ? "#f43f5e" : "none"}
            />

            {/* Stylish Hair & Twin Tails */}
            <path
              d="M40 35 C40 22 50 18 60 18 C70 18 80 22 80 35 C76 31 71 31 66 31 C61 31 56 31 51 31 C46 31 42 33 40 35 Z"
              fill="#1e1b4b"
            />
            {/* Hair Ribbons */}
            <circle cx="43" cy="28" r="4" fill="#ec4899" />
            <circle cx="77" cy="28" r="4" fill="#ec4899" />

            {/* Gradients */}
            <defs>
              <linearGradient id="hinaGradient" x1="40" y1="55" x2="80" y2="95" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stopColor="#ec4899" />
                <stop offset="100%" stopColor="#8b5cf6" />
              </linearGradient>
            </defs>
          </svg>
        </div>

        {/* ── Gemini Live Style Reactive Voice Aura Ring ──────── */}
        <div
          style={{
            position: "absolute",
            bottom: 24,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 76,
            height: 76,
          }}
        >
          {/* Outer Pulsing Wave Ring */}
          <motion.div
            animate={{
              scale: isVoiceActive || companionState === "speaking" ? [1, 1.28, 1] : 1,
              opacity: isVoiceActive || companionState === "speaking" ? [0.4, 0.85, 0.4] : 0.25,
            }}
            transition={{ repeat: Infinity, duration: 1.6, ease: "easeInOut" }}
            style={{
              position: "absolute",
              width: "100%",
              height: "100%",
              borderRadius: "50%",
              border: "2px solid #00d4ff",
              boxShadow: "0 0 16px rgba(0, 212, 255, 0.45)",
            }}
          />

          {/* Middle Aura Ring */}
          <motion.div
            animate={{
              rotate: 360,
              scale: companionState === "thinking" ? [1, 1.15, 1] : 1,
            }}
            transition={{
              rotate: { repeat: Infinity, duration: 4, ease: "linear" },
              scale: { repeat: Infinity, duration: 1.2, ease: "easeInOut" },
            }}
            style={{
              position: "absolute",
              width: 58,
              height: 58,
              borderRadius: "50%",
              border: "2px dashed #ec4899",
            }}
          />

          {/* Central Live Mic Trigger Button */}
          <button
            type="button"
            onClick={() => {
              playUiSound("buttonPress");
              onToggleVoice?.();
            }}
            title={isVoiceActive ? "Mic active (Click to mute)" : "Click to activate hands-free live voice"}
            style={{
              width: 44,
              height: 44,
              borderRadius: "50%",
              background: isVoiceActive ? "linear-gradient(135deg, #ec4899 0%, #00d4ff 100%)" : "rgba(255, 255, 255, 0.12)",
              border: "1px solid rgba(255, 255, 255, 0.25)",
              color: "#ffffff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
              boxShadow: isVoiceActive ? "0 0 18px rgba(236, 72, 153, 0.6)" : "none",
              zIndex: 5,
              transition: "all 0.2s ease",
            }}
          >
            {isVoiceActive ? <Mic size={20} /> : <MicOff size={18} color="#94a3b8" />}
          </button>
        </div>

        {/* Speech / State Caption */}
        <div
          style={{
            position: "absolute",
            bottom: 4,
            fontSize: 10,
            fontWeight: 600,
            color: "#fbcfe8",
            textAlign: "center",
            padding: "0 10px",
            lineHeight: 1.2,
          }}
        >
          {speechCue}
        </div>
      </div>

      {/* ── Quick Action Burst Floating Dock ───────────────────── */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-around",
          padding: "8px 12px",
          background: "rgba(0, 0, 0, 0.45)",
          borderTop: "1px solid rgba(255, 255, 255, 0.08)",
        }}
      >
        <button
          type="button"
          onClick={() => {
            playUiSound("buttonPress");
            onCaptureScreen?.();
          }}
          title="Inspect Screen / Multimodal Vision"
          style={{
            background: "rgba(255, 255, 255, 0.06)",
            border: "1px solid rgba(255, 255, 255, 0.1)",
            color: "#00d4ff",
            borderRadius: 8,
            padding: "5px 9px",
            display: "flex",
            alignItems: "center",
            gap: 4,
            fontSize: 10,
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          <Video size={12} />
          <span>Vision</span>
        </button>

        <button
          type="button"
          onClick={() => {
            playUiSound("buttonPress");
            onTriggerActionBurst?.("playwright_burst");
          }}
          title="High-Speed Browser Action Burst"
          style={{
            background: "rgba(255, 255, 255, 0.06)",
            border: "1px solid rgba(255, 255, 255, 0.1)",
            color: "#f59e0b",
            borderRadius: 8,
            padding: "5px 9px",
            display: "flex",
            alignItems: "center",
            gap: 4,
            fontSize: 10,
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          <Zap size={12} />
          <span>Burst</span>
        </button>

        <button
          type="button"
          onClick={() => {
            playUiSound("buttonPress");
            onTriggerActionBurst?.("artemis_mobile");
          }}
          title="Google ARTEMIS Mobile Automation"
          style={{
            background: "rgba(255, 255, 255, 0.06)",
            border: "1px solid rgba(255, 255, 255, 0.1)",
            color: "#10b981",
            borderRadius: 8,
            padding: "5px 9px",
            display: "flex",
            alignItems: "center",
            gap: 4,
            fontSize: 10,
            fontWeight: 700,
            cursor: "pointer",
          }}
        >
          <Smartphone size={12} />
          <span>Mobile</span>
        </button>
      </div>
    </div>
  );

  // If PiP Window is open, render into the pop-out window body using React Portal!
  if (pipWindow) {
    return ReactDOM.createPortal(overlayContent, pipWindow.document.body);
  }

  // Otherwise, render as a sleek floating draggable desktop overlay or mobile bottom-right pill
  return (
    <motion.aside
      drag
      dragConstraints={{ left: -window.innerWidth + 280, right: 0, top: -window.innerHeight + 380, bottom: 0 }}
      initial={{ opacity: 0, scale: 0.85, y: 30 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.85, y: 30 }}
      style={{
        position: "fixed",
        bottom: 24,
        right: 24,
        width: 250,
        height: 350,
        zIndex: 99999,
        touchAction: "none",
      }}
    >
      {overlayContent}
    </motion.aside>
  );
};
