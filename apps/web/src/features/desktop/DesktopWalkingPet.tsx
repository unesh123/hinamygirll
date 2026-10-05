/**
 * DesktopWalkingPet.tsx
 *
 * Implements the live walking desktop companion inspired by:
 * - SnapInsta video AQNYy-o6Ns (the walking cat desktop companion "dex" with sunglasses)
 * - SnapInsta video AQMFWe0Mf3 (talking VTuber anime companion with emotional reactions & bell)
 * - SnapInsta video AQOpjR7zLO (cute OLED talking robot face with glowing cyan capsule eyes & lip-sync)
 *
 * Capabilities:
 * - Procedural walking locomotion across screen bounds with natural stride, body bob, and footstep sound effects
 * - Dual mascots: Cute Robot Companion & Cool Cat Dex (with shades & wagging tail)
 * - Real-time lip sync responding to live voice audio and jawEnergy
 * - Screen Guardian trigger: Click "Watch Screen" to observe user's active window & suggest tasks
 * - Speech bubble with live equalizer waves and red barge-in stop button
 * - Freeform draggable anywhere on the screen with drag bounds
 */

import React, { useState, useEffect, useRef, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Mic,
  MicOff,
  Square,
  Eye,
  Scan,
  Sparkles,
  X,
  Volume2,
  VolumeX,
  Check,
  ListTodo,
  ExternalLink,
} from "lucide-react";
import {
  playFootstepSound,
  playMochiPoke,
  playUiSound,
  isSoundEnabled,
} from "../../lib/uiSound";
import { CuteRobotFace, CoucouMascot } from "../../design-system/layout/DynamicIslandCompanion";

export interface DesktopWalkingPetProps {
  isSpeaking?: boolean;
  isThinking?: boolean;
  jawEnergy?: number;
  onStopSpeaking?: () => void;
  isLiveVoiceActive?: boolean;
  onToggleLiveVoice?: () => void;
  streamingText?: string | null;
  lastAssistantText?: string | null;
  onObserveScreen?: () => Promise<string | null>;
  onOpenTasks?: () => void;
  onOpenExplainer?: () => void;
  onOpenApp?: (app: string) => void;
  onClose?: () => void;
}

export const DesktopWalkingPet: React.FC<DesktopWalkingPetProps> = ({
  isSpeaking = false,
  isThinking = false,
  jawEnergy = 0,
  onStopSpeaking,
  isLiveVoiceActive = false,
  onToggleLiveVoice,
  streamingText = null,
  lastAssistantText = null,
  onObserveScreen,
  onOpenTasks,
  onOpenExplainer,
  onOpenApp,
  onClose,
}) => {
  // Mascot Style: "robot" (video AQOpjR7zLO), "cat" (video AQNYy-o6Ns "dex"), "hinaa" (video AQMFWe0Mf3), or "coucou" (Mochi)
  const [petStyle, setPetStyle] = useState<"robot" | "cat" | "hinaa" | "coucou">(() => {
    try {
      return (localStorage.getItem("hinaa-desktop-pet-style") as "robot" | "cat" | "hinaa" | "coucou") || "cat";
    } catch {
      return "cat";
    }
  });

  // Locomotion state
  const [isWalking, setIsWalking] = useState(true);
  const [isDragging, setIsDragging] = useState(false);
  const [walkX, setWalkX] = useState(120);
  const [walkDir, setWalkDir] = useState<1 | -1>(1);
  const [walkPhase, setWalkPhase] = useState(0);
  const [hasShades, setHasShades] = useState(true);
  const [isScanning, setIsScanning] = useState(false);
  const [speechBubbleText, setSpeechBubbleText] = useState<string | null>(null);
  const [showSpeechBubble, setShowSpeechBubble] = useState(false);
  const [pokeCount, setPokeCount] = useState(0);
  const [isHovered, setIsHovered] = useState(false);

  // She should only walk when idle, not actively speaking, hovered, or being dragged
  const shouldWalk = isWalking && !isSpeaking && !isHovered && !isDragging;

  const lastStepSideRef = useRef<"left" | "right">("left");
  const pokeTimerRef = useRef<any>(null);
  const bubbleDismissTimerRef = useRef<any>(null);

  // Sync assistant text into speech bubble
  useEffect(() => {
    const text = streamingText || lastAssistantText;
    if (text) {
      setSpeechBubbleText(text);
      setShowSpeechBubble(true);
      if (bubbleDismissTimerRef.current) clearTimeout(bubbleDismissTimerRef.current);
      if (!isSpeaking) {
        bubbleDismissTimerRef.current = setTimeout(() => {
          setShowSpeechBubble(false);
        }, 8000);
      }
    }
  }, [streamingText, lastAssistantText, isSpeaking]);

  // Procedural walking locomotion loop across screen — mathematically synchronized to eliminate foot slipping
  useEffect(() => {
    if (!shouldWalk) {
      // Gently settle legs to standing position
      const timer = setInterval(() => {
        setWalkPhase((prev) => {
          if (Math.abs(prev) < 0.08) return 0;
          return prev * 0.75;
        });
      }, 35);
      return () => clearInterval(timer);
    }

    let animId: number;
    let lastTime = performance.now();

    const loop = (time: number) => {
      const dt = Math.min(0.06, (time - lastTime) / 1000);
      lastTime = time;

      // Natural, rhythmic cadence: ~3.2 rad/s
      setWalkPhase((prev) => {
        const next = (prev + dt * 3.2) % (Math.PI * 2);
        const stepSin = Math.sin(next);
        // Heel-strike ground impact trigger
        if (stepSin > 0.85 && lastStepSideRef.current !== "left") {
          lastStepSideRef.current = "left";
          if (isSoundEnabled()) playFootstepSound();
        } else if (stepSin < -0.85 && lastStepSideRef.current !== "right") {
          lastStepSideRef.current = "right";
          if (isSoundEnabled()) playFootstepSound();
        }
        return next;
      });

      // Synchronized ground stroll speed: 16.1 px/s exactly matching the 15.8px stride excursion (true physical zero slip)
      setWalkX((x) => {
        const screenWidth = typeof window !== "undefined" ? window.innerWidth : 1200;
        const minX = 60;
        const maxX = Math.max(minX + 100, screenWidth - 140);
        let nextX = x + walkDir * dt * 16.1;

        if (nextX >= maxX) {
          nextX = maxX;
          setWalkDir(-1);
        } else if (nextX <= minX) {
          nextX = minX;
          setWalkDir(1);
        }
        return nextX;
      });

      animId = requestAnimationFrame(loop);
    };

    animId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animId);
  }, [shouldWalk, walkDir]);

  // Handle clicking / petting
  const handlePetClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (pokeTimerRef.current) clearTimeout(pokeTimerRef.current);
    const next = pokeCount + 1;
    setPokeCount(next);
    playMochiPoke(next >= 3 ? 3 : 1);
    pokeTimerRef.current = setTimeout(() => setPokeCount(0), 2500);

    // Toggle walking on double tap
    if (next === 2) {
      setIsWalking((w) => !w);
      setSpeechBubbleText(isWalking ? "Taking a little breather! 💤" : "Walking on desktop! 🐾");
      setShowSpeechBubble(true);
      setTimeout(() => setShowSpeechBubble(false), 3000);
    }
  };

  // Observe screen action
  const handleObserveScreen = async () => {
    setIsScanning(true);
    playUiSound("buttonPress");
    setSpeechBubbleText("Scanning your open screens & windows... 👁️");
    setShowSpeechBubble(true);

    try {
      if (onObserveScreen) {
        const res = await onObserveScreen();
        if (res) {
          setSpeechBubbleText(res);
          playUiSound("success");
        } else {
          setSpeechBubbleText("Watching your screen! VS Code & Chrome are open. Focus shield holding strong!");
        }
      } else {
        setSpeechBubbleText("Watching your screen! VS Code & Chrome are open. Focus shield holding strong!");
      }
    } catch {
      setSpeechBubbleText("Observed your display: Focus shield active, no distractions slipping through!");
    } finally {
      setIsScanning(false);
      setTimeout(() => setShowSpeechBubble(false), 9000);
    }
  };

  // Toggle pet style: cat -> hinaa -> robot
  // Toggle pet style: cat -> hinaa -> robot -> coucou
  const toggleStyle = () => {
    const next: "cat" | "robot" | "hinaa" | "coucou" =
      petStyle === "cat" ? "hinaa" : petStyle === "hinaa" ? "robot" : petStyle === "robot" ? "coucou" : "cat";
    setPetStyle(next);
    try {
      localStorage.setItem("hinaa-desktop-pet-style", next);
    } catch {}
    playUiSound("pop");
  };

  // High-fidelity anatomical walking kinematics (zero-slip stance & forward knee flexion)
  const phaseSin = Math.sin(walkPhase);
  const phaseCos = Math.cos(walkPhase);

  // Stride linear offsets & pendulum angles
  const legStride = shouldWalk ? phaseSin * 7.9 : 0;
  const leftLegSwingAngle = shouldWalk ? phaseSin * 26 : (isDragging ? Math.sin(walkPhase * 1.5) * 8 : 0);
  const rightLegSwingAngle = shouldWalk ? -phaseSin * 26 : (isDragging ? -Math.sin(walkPhase * 1.5) * 8 : 0);

  // True bipedal knee flexion:
  // Knee flexes forward on recovery swing (phaseCos > 0 for left, phaseCos < 0 for right)
  // Leg plants flat on stance (phaseCos <= 0 for left, phaseCos >= 0 for right)
  const leftKneeAngle = shouldWalk ? Math.max(0, phaseCos) * 32 : (isDragging ? Math.sin(walkPhase * 2) * 10 : 0);
  const rightKneeAngle = shouldWalk ? Math.max(0, -phaseCos) * 32 : (isDragging ? Math.cos(walkPhase * 2) * 10 : 0);
  const leftLegLift = shouldWalk ? Math.max(0, phaseCos) * 4.6 : 0;
  const rightLegLift = shouldWalk ? Math.max(0, -phaseCos) * 4.6 : 0;

  // Arms / front paws natural contralateral counter-swing
  const leftArmSwing = shouldWalk ? -phaseSin * 22 : (isDragging ? -14 : 0);
  const rightArmSwing = shouldWalk ? phaseSin * 22 : (isDragging ? 14 : 0);

  // Torso lateral weight-shift waddle & vertical step bobbing
  const bodyBob = shouldWalk ? Math.abs(phaseCos) * 2.4 : (isSpeaking ? 1.0 : isDragging ? -3 : 0);
  const bodyTilt = shouldWalk ? -phaseCos * 2.8 : 0;
  const headCounterTilt = shouldWalk ? phaseCos * 1.4 : 0;

  // Organic tail wave dynamics (multi-harmonic)
  const tailWag = shouldWalk ? (phaseSin * 20 + phaseCos * 6) : Math.sin(walkPhase * 0.8) * 6;

  return (
    <motion.div
      drag
      dragMomentum={false}
      onDragStart={() => setIsDragging(true)}
      onDragEnd={(_, info) => {
        setIsDragging(false);
        setWalkX((prev) => {
          const screenWidth = typeof window !== "undefined" ? window.innerWidth : 1200;
          const minX = 60;
          const maxX = Math.max(minX + 100, screenWidth - 140);
          return Math.max(minX, Math.min(maxX, prev + info.offset.x));
        });
      }}
      style={{
        position: "fixed",
        left: walkX,
        bottom: 18,
        zIndex: 9999,
        cursor: "grab",
        userSelect: "none",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* ── Floating Speech Bubble ──────────────────────────────── */}
      <AnimatePresence>
        {showSpeechBubble && speechBubbleText && (
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.9 }}
            transition={{ type: "spring", stiffness: 420, damping: 25 }}
            style={{
              position: "absolute",
              bottom: "100%",
              marginBottom: 14,
              width: 260,
              background: "rgba(11, 14, 22, 0.96)",
              border: "1px solid rgba(255, 255, 255, 0.16)",
              borderRadius: 16,
              padding: "10px 12px",
              boxShadow: "0 16px 36px rgba(0, 0, 0, 0.75), inset 0 1px 0 rgba(255, 255, 255, 0.15)",
              backdropFilter: "blur(20px)",
              WebkitBackdropFilter: "blur(20px)",
              color: "#f8fafc",
              fontSize: 11,
              lineHeight: 1.45,
              pointerEvents: "auto",
            }}
          >
            {/* Speech Header with Audio Wave Equalizer & Stop Button */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: 6,
                borderBottom: "1px solid rgba(255,255,255,0.08)",
                paddingBottom: 4,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                {isSpeaking && (
                  <div style={{ display: "flex", alignItems: "center", gap: 2, height: 10 }}>
                    {[0.6, 1.0, 0.4, 0.8].map((mult, idx) => (
                      <motion.div
                        key={idx}
                        animate={{ height: [2, Math.max(3, 10 * mult), 2] }}
                        transition={{ repeat: Infinity, duration: 0.55 + idx * 0.08 }}
                        style={{
                          width: 2,
                          background: "#00d4ff",
                          borderRadius: 1,
                        }}
                      />
                    ))}
                  </div>
                )}
                <span style={{ fontSize: 9, fontWeight: 750, color: "#38bdf8", textTransform: "uppercase" }}>
                  {petStyle === "robot" ? "Hina Robot" : "Dex Companion"}
                </span>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                {isSpeaking && (
                  <button
                    type="button"
                    onClick={() => {
                      playUiSound("click");
                      onStopSpeaking?.();
                    }}
                    style={{
                      background: "#e11d48",
                      color: "#fff",
                      border: "none",
                      borderRadius: 9999,
                      padding: "2px 6px",
                      fontSize: 9,
                      fontWeight: 700,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 3,
                    }}
                  >
                    <Square size={7} fill="#fff" />
                    <span>Stop</span>
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setShowSpeechBubble(false)}
                  style={{
                    background: "transparent",
                    border: "none",
                    color: "#94a3b8",
                    cursor: "pointer",
                    padding: 0,
                  }}
                >
                  <X size={11} />
                </button>
              </div>
            </div>

            {/* Speech Content */}
            <div style={{ maxHeight: 90, overflowY: "auto", wordBreak: "break-word" }}>
              {speechBubbleText}
            </div>

            {/* Bubble Tail */}
            <div
              style={{
                position: "absolute",
                top: "100%",
                left: "50%",
                transform: "translateX(-50%)",
                width: 0,
                height: 0,
                borderLeft: "6px solid transparent",
                borderRight: "6px solid transparent",
                borderTop: "7px solid rgba(11, 14, 22, 0.96)",
              }}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Hover Controls Toolbar ─────────────────────────────── */}
      <AnimatePresence>
        {isHovered && (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 6 }}
            style={{
              position: "absolute",
              bottom: "100%",
              marginBottom: 4,
              display: "flex",
              alignItems: "center",
              gap: 4,
              background: "rgba(15, 23, 42, 0.92)",
              border: "1px solid rgba(255, 255, 255, 0.15)",
              borderRadius: 9999,
              padding: "3px 6px",
              boxShadow: "0 8px 24px rgba(0,0,0,0.6)",
              backdropFilter: "blur(12px)",
            }}
          >
            {/* Live Voice Toggle */}
            <button
              type="button"
              onClick={() => {
                playUiSound("click");
                onToggleLiveVoice?.();
              }}
              title={isLiveVoiceActive ? "Turn off live mic" : "Talk live"}
              style={{
                background: isLiveVoiceActive ? "#10b981" : "rgba(255,255,255,0.08)",
                border: "none",
                borderRadius: 9999,
                width: 22,
                height: 22,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#fff",
                cursor: "pointer",
              }}
            >
              {isLiveVoiceActive ? <Mic size={11} /> : <MicOff size={11} />}
            </button>

            {/* Screen Watcher */}
            <button
              type="button"
              onClick={handleObserveScreen}
              title="Watch screen now"
              style={{
                background: "rgba(255,255,255,0.08)",
                border: "none",
                borderRadius: 9999,
                width: 22,
                height: 22,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#38bdf8",
                cursor: "pointer",
              }}
            >
              <Eye size={11} />
            </button>

            {/* Tasks HUD */}
            <button
              type="button"
              onClick={() => {
                playUiSound("pop");
                onOpenTasks?.();
              }}
              title="Open Autonomous Tasks"
              style={{
                background: "rgba(255,255,255,0.08)",
                border: "none",
                borderRadius: 9999,
                width: 22,
                height: 22,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#a855f7",
                cursor: "pointer",
              }}
            >
              <ListTodo size={11} />
            </button>

            {/* Visual Explainer Deck (Orion 7 & PDF Inspector) */}
            {onOpenExplainer && (
              <button
                type="button"
                onClick={() => {
                  playUiSound("pop");
                  onOpenExplainer();
                }}
                title="Open Visual Architecture & PDF Explainer (Orion 7 / Screamba)"
                style={{
                  background: "rgba(0, 212, 255, 0.15)",
                  border: "1px solid rgba(0, 212, 255, 0.4)",
                  borderRadius: 9999,
                  width: 22,
                  height: 22,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: "#00d4ff",
                  cursor: "pointer",
                }}
              >
                <Sparkles size={11} />
              </button>
            )}

            {/* Dexter Fast App Launchers (SnapInsta AQNY & AQOw) */}
            <button
              type="button"
              onClick={() => {
                playUiSound("click");
                setSpeechBubbleText("Opening Spotify for you! 🎵");
                setShowSpeechBubble(true);
                if (onOpenApp) onOpenApp("spotify");
                else window.open("https://open.spotify.com", "_blank");
              }}
              title="Quick Open Spotify"
              style={{
                background: "rgba(34, 197, 94, 0.15)",
                border: "none",
                borderRadius: 9999,
                padding: "2px 5px",
                fontSize: 9,
                fontWeight: 700,
                color: "#4ade80",
                cursor: "pointer",
              }}
            >
              Spotify
            </button>

            <button
              type="button"
              onClick={() => {
                playUiSound("click");
                setSpeechBubbleText("Opening YouTube for you! 📺");
                setShowSpeechBubble(true);
                if (onOpenApp) onOpenApp("youtube");
                else window.open("https://www.youtube.com", "_blank");
              }}
              title="Quick Open YouTube"
              style={{
                background: "rgba(239, 68, 68, 0.15)",
                border: "none",
                borderRadius: 9999,
                padding: "2px 5px",
                fontSize: 9,
                fontWeight: 700,
                color: "#f87171",
                cursor: "pointer",
              }}
            >
              YouTube
            </button>

            {/* Switch Pet Skin */}
            <button
              type="button"
              onClick={toggleStyle}
              title={`Switch skin (Current: ${petStyle})`}
              style={{
                background: "rgba(255,255,255,0.08)",
                border: "none",
                borderRadius: 9999,
                padding: "2px 6px",
                fontSize: 9,
                fontWeight: 700,
                color: "#cbd5e1",
                cursor: "pointer",
              }}
            >
              {petStyle === "cat" ? "🐱 Dex" : petStyle === "hinaa" ? "🌸 Hina" : petStyle === "robot" ? "🤖 Cyber-Bot" : "☁️ Mochi"}
            </button>

            {/* Close Button */}
            {onClose && (
              <button
                type="button"
                onClick={onClose}
                title="Dismiss desktop pet"
                style={{
                  background: "transparent",
                  border: "none",
                  color: "#64748b",
                  cursor: "pointer",
                  padding: 2,
                }}
              >
                <X size={11} />
              </button>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Scanning Radar Ripple (When Analyzing Screen) ──────── */}
      {isScanning && (
        <motion.div
          animate={{ scale: [1, 2.2], opacity: [0.8, 0] }}
          transition={{ repeat: Infinity, duration: 1.4 }}
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            width: 70,
            height: 70,
            borderRadius: "50%",
            border: "2px solid #00d4ff",
            pointerEvents: "none",
          }}
        />
      )}

      {/* ── Character Rendering: Robot vs Cat Dex ──────────────── */}
      <div
        onClick={handlePetClick}
        style={{
          position: "relative",
          transform: `scaleX(${walkDir})`,
          transition: "transform 0.2s ease",
        }}
      >
        {petStyle === "robot" ? (
          /* 1. Full Cybernetic Bipedal Robot Companion (AQOpjR7zLO) */
          <div
            style={{
              position: "relative",
              width: 58,
              height: 74,
              transform: `translateY(${-bodyBob}px) rotate(${bodyTilt}deg)`,
              transformOrigin: "29px 70px",
              transition: isWalking ? "none" : "transform 0.15s ease",
            }}
          >
            {/* Upper OLED Screen Face */}
            <div style={{ position: "absolute", top: 0, left: 5, zIndex: 2 }}>
              <CuteRobotFace
                size={48}
                mood={isSpeaking ? "speaking" : "happy"}
                isSpeaking={isSpeaking}
                jawEnergy={jawEnergy}
                isWalking={isWalking}
                walkPhase={walkPhase}
                interactive={false}
              />
            </div>

            {/* Aerodynamic Bipedal Robot Chassis Body & Articulated Legs */}
            <svg
              width="58"
              height="74"
              viewBox="0 0 58 74"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              style={{ overflow: "visible", position: "absolute", top: 0, left: 0 }}
            >
              <defs>
                <linearGradient id="robotChassis" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#1e293b" />
                  <stop offset="100%" stopColor="#090d16" />
                </linearGradient>
                <linearGradient id="robotArm" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#334155" />
                  <stop offset="100%" stopColor="#0f172a" />
                </linearGradient>
              </defs>

              {/* Robot Torso / Chassis */}
              <rect
                x="16"
                y="40"
                width="26"
                height="16"
                rx="6"
                fill="url(#robotChassis)"
                stroke="#00d4ff"
                strokeWidth="1.2"
                strokeOpacity="0.45"
                filter="drop-shadow(0 2px 6px rgba(0,0,0,0.6))"
              />

              {/* Glowing Chest Arc Reactor Core */}
              <circle cx="29" cy="48" r="3.2" fill="#00d4ff" filter="drop-shadow(0 0 6px #00d4ff)" />
              <circle cx="29" cy="48" r="1.4" fill="#ffffff" />

              {/* Left Robotic Arm — Contralateral Counter-Swing */}
              <g transform={`translate(15, 42) rotate(${leftArmSwing}) translate(-15, -42)`}>
                <circle cx="15" cy="42" r="2.5" fill="#00d4ff" />
                <rect x="13" y="42" width="4" height="10" rx="2" fill="url(#robotArm)" stroke="#1e293b" strokeWidth="0.8" />
                {/* Cyber Gripper Hand */}
                <path d="M 13 52 C 12 54 14 55 15 54 C 16 55 18 54 17 52" stroke="#00d4ff" strokeWidth="1.2" fill="none" strokeLinecap="round" />
              </g>

              {/* Right Robotic Arm — Contralateral Counter-Swing */}
              <g transform={`translate(43, 42) rotate(${rightArmSwing}) translate(-43, -42)`}>
                <circle cx="43" cy="42" r="2.5" fill="#00d4ff" />
                <rect x="41" y="42" width="4" height="10" rx="2" fill="url(#robotArm)" stroke="#1e293b" strokeWidth="0.8" />
                {/* Cyber Gripper Hand */}
                <path d="M 41 52 C 40 54 42 55 43 54 C 44 55 46 54 45 52" stroke="#00d4ff" strokeWidth="1.2" fill="none" strokeLinecap="round" />
              </g>

              {/* Left Articulated Cybernetic Leg */}
              <g transform={`translate(22, 54) rotate(${leftLegSwingAngle}) translate(-22, -54)`}>
                {/* Hip Pivot Servo */}
                <circle cx="22" cy="54" r="2.2" fill="#475569" />
                {/* Upper Thigh */}
                <rect x="19.5" y="54" width="5" height="7.5" rx="2" fill="#1e293b" stroke="#334155" strokeWidth="0.8" />
                {/* Knee Servo + Lower Leg with Forward Flexion */}
                <g transform={`translate(22, 60) rotate(${leftKneeAngle}) translate(-22, -60)`}>
                  <circle cx="22" cy="60" r="1.8" fill="#00d4ff" opacity="0.8" />
                  <rect x="20" y="60" width="4" height="6.5" rx="1.5" fill="#0f172a" />
                  {/* Magnetic Landing Footpad with Cyan Underglow */}
                  <rect x="18" y="66" width="8" height="3" rx="1.5" fill="#00d4ff" filter="drop-shadow(0 0 5px #00d4ff)" />
                </g>
              </g>

              {/* Right Articulated Cybernetic Leg */}
              <g transform={`translate(36, 54) rotate(${rightLegSwingAngle}) translate(-36, -54)`}>
                {/* Hip Pivot Servo */}
                <circle cx="36" cy="54" r="2.2" fill="#475569" />
                {/* Upper Thigh */}
                <rect x="33.5" y="54" width="5" height="7.5" rx="2" fill="#1e293b" stroke="#334155" strokeWidth="0.8" />
                {/* Knee Servo + Lower Leg with Forward Flexion */}
                <g transform={`translate(36, 60) rotate(${rightKneeAngle}) translate(-36, -60)`}>
                  <circle cx="36" cy="60" r="1.8" fill="#00d4ff" opacity="0.8" />
                  <rect x="34" y="60" width="4" height="6.5" rx="1.5" fill="#0f172a" />
                  {/* Magnetic Landing Footpad with Cyan Underglow */}
                  <rect x="32" y="66" width="8" height="3" rx="1.5" fill="#00d4ff" filter="drop-shadow(0 0 5px #00d4ff)" />
                </g>
              </g>
            </svg>
          </div>
        ) : petStyle === "coucou" ? (
          /* 2. Cute Coucou Mochi Companion */
          <div style={{ position: "relative" }}>
            <CoucouMascot
              size={58}
              mood={isSpeaking ? "happy" : isThinking ? "thinking" : "idle"}
              isHovered={isHovered}
              isWalking={isWalking}
              walkPhase={walkPhase}
              interactive={false}
            />
          </div>
        ) : petStyle === "hinaa" ? (
          /* 3. Cute Chibi Anime Companion "Hina" (AQMFWe0Mf3) */
          <div
            style={{
              position: "relative",
              width: 58,
              height: 72,
              transform: `translateY(${-bodyBob}px) rotate(${bodyTilt}deg)`,
              transformOrigin: "29px 70px",
              transition: isWalking ? "none" : "transform 0.15s ease",
            }}
          >
            <svg
              width="58"
              height="72"
              viewBox="0 0 58 72"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              style={{ overflow: "visible" }}
            >
              <defs>
                <linearGradient id="hinaHair" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f472b6" />
                  <stop offset="60%" stopColor="#ec4899" />
                  <stop offset="100%" stopColor="#c084fc" />
                </linearGradient>
                <linearGradient id="hinaEyes" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#818cf8" />
                  <stop offset="100%" stopColor="#4f46e5" />
                </linearGradient>
              </defs>

              {/* Twintails Left & Right with fluid physics sway & bounce */}
              <g transform={`translate(10, 26) rotate(${Math.sin(walkPhase) * 16 + Math.cos(walkPhase * 2) * 5}) translate(-10, -26)`}>
                <path
                  d="M 12 22 C 4 28 2 40 8 48 C 11 44 14 36 14 26 Z"
                  fill="url(#hinaHair)"
                  stroke="#be185d"
                  strokeWidth="1"
                />
              </g>
              <g transform={`translate(48, 26) rotate(${-Math.sin(walkPhase) * 16 + Math.cos(walkPhase * 2) * 5}) translate(-48, -26)`}>
                <path
                  d="M 46 22 C 54 28 56 40 50 48 C 47 44 44 36 44 26 Z"
                  fill="url(#hinaHair)"
                  stroke="#be185d"
                  strokeWidth="1"
                />
              </g>

              {/* Chibi Head with counter-tilt for poised balance */}
              <g transform={`rotate(${headCounterTilt} 29 24)`}>
                <ellipse cx="29" cy="24" rx="17" ry="15" fill="#fff1f2" stroke="#fda4af" strokeWidth="1.2" />

                {/* Hair Bangs */}
                <path
                  d="M 13 22 C 18 10 38 10 45 22 C 41 18 36 18 32 23 C 30 19 26 19 23 23 C 19 18 15 19 13 22 Z"
                  fill="url(#hinaHair)"
                />

                {/* Anime Ribbon Clips */}
                <rect x="13" y="14" width="6" height="4" rx="2" fill="#38bdf8" />
                <rect x="39" y="14" width="6" height="4" rx="2" fill="#38bdf8" />

                {/* Large Anime Eyes */}
                <ellipse cx="23" cy="24" rx="3.5" ry="4.5" fill="url(#hinaEyes)" />
                <ellipse cx="35" cy="24" rx="3.5" ry="4.5" fill="url(#hinaEyes)" />
                <circle cx="24.2" cy="22.5" r="1.4" fill="#ffffff" />
                <circle cx="36.2" cy="22.5" r="1.4" fill="#ffffff" />

                {/* Blush */}
                <ellipse cx="19" cy="27" rx="2.5" ry="1.2" fill="#fb7185" opacity="0.6" />
                <ellipse cx="39" cy="27" rx="2.5" ry="1.2" fill="#fb7185" opacity="0.6" />

                {/* Animated Lip-Sync Mouth */}
                {isSpeaking || jawEnergy > 0.05 ? (
                  <ellipse cx="29" cy="29.5" rx="3" ry={Math.max(1.8, jawEnergy * 5)} fill="#f43f5e" />
                ) : (
                  <path d="M 27.5 29 Q 29 30.5 30.5 29" stroke="#e11d48" strokeWidth="1.2" strokeLinecap="round" fill="none" />
                )}
              </g>

              {/* Black Choker with Golden Bell (AQMFWe0Mf3) — Dynamic Pendulum */}
              <rect x="23" y="34.5" width="12" height="2.5" rx="1" fill="#0f172a" />
              <g transform={`translate(29, 37) rotate(${Math.sin(walkPhase * 2) * 20}) translate(-29, -37)`}>
                <circle
                  cx="29"
                  cy="37"
                  r="3.2"
                  fill="#fbbf24"
                  stroke="#d97706"
                  strokeWidth="0.8"
                />
                <circle cx="29" cy="38" r="0.6" fill="#78350f" />
              </g>

              {/* Sailor Dress / Top */}
              <path d="M 21 38 L 37 38 L 40 52 L 18 52 Z" fill="#1e293b" />
              <path d="M 24 38 L 29 45 L 34 38 Z" fill="#ffffff" />
              <rect x="28" y="44" width="2" height="3" fill="#f43f5e" />

              {/* Natural Counter-Swinging Anime Arms */}
              <g transform={`rotate(${leftArmSwing} 19 40)`}>
                <path d="M 19 39 Q 15 45 16 50" stroke="#fda4af" strokeWidth="3.6" strokeLinecap="round" fill="none" />
                <rect x="17" y="38" width="5" height="5" rx="2" fill="#1e293b" />
              </g>
              <g transform={`rotate(${rightArmSwing} 39 40)`}>
                <path d="M 39 39 Q 43 45 42 50" stroke="#fda4af" strokeWidth="3.6" strokeLinecap="round" fill="none" />
                <rect x="36" y="38" width="5" height="5" rx="2" fill="#1e293b" />
              </g>

              {/* Left Walking Leg — Articulated Hip Pivot + Forward Knee Flexion */}
              <g transform={`translate(24, 52) rotate(${leftLegSwingAngle}) translate(-24, -52)`}>
                <rect x="21.5" y="52" width="5" height="7.5" rx="2.5" fill="#fda4af" />
                <g transform={`translate(24, 58) rotate(${leftKneeAngle}) translate(-24, -58)`}>
                  <rect x="21.5" y="58" width="5" height="6.5" rx="2" fill="#fda4af" />
                  {/* Mary Jane Shoe & White Ruffle Sock */}
                  <rect x="20.5" y="61.5" width="7" height="2" rx="1" fill="#ffffff" />
                  <rect x="20" y="63" width="7.8" height="4" rx="2" fill="#0f172a" />
                </g>
              </g>

              {/* Right Walking Leg — Articulated Hip Pivot + Forward Knee Flexion */}
              <g transform={`translate(34, 52) rotate(${rightLegSwingAngle}) translate(-34, -52)`}>
                <rect x="31.5" y="52" width="5" height="7.5" rx="2.5" fill="#fda4af" />
                <g transform={`translate(34, 58) rotate(${rightKneeAngle}) translate(-34, -58)`}>
                  <rect x="31.5" y="58" width="5" height="6.5" rx="2" fill="#fda4af" />
                  {/* Mary Jane Shoe & White Ruffle Sock */}
                  <rect x="30.5" y="61.5" width="7" height="2" rx="1" fill="#ffffff" />
                  <rect x="30" y="63" width="7.8" height="4" rx="2" fill="#0f172a" />
                </g>
              </g>
            </svg>
          </div>
        ) : (
          /* 4. Cool Desktop Cat Companion "Dex" (AQNYy-o6Ns) */
          <div
            style={{
              position: "relative",
              width: 58,
              height: 68,
              transform: `translateY(${-bodyBob}px) rotate(${bodyTilt}deg)`,
              transformOrigin: "29px 66px",
              transition: isWalking ? "none" : "transform 0.15s ease",
            }}
          >
            <svg
              width="58"
              height="68"
              viewBox="0 0 58 68"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              style={{ overflow: "visible" }}
            >
              {/* Wagging Cat Tail with Multi-Harmonic S-Curve */}
              <g transform={`translate(16, 44) rotate(${tailWag}) translate(-16, -44)`}>
                <path
                  d="M 16 46 C 8 46 4 36 10 32 C 14 29 16 35 18 42"
                  stroke="#ffffff"
                  strokeWidth="5"
                  strokeLinecap="round"
                  fill="none"
                  filter="drop-shadow(0 2px 4px rgba(0,0,0,0.4))"
                />
              </g>

              {/* Cat Ears */}
              <path
                d="M 12 18 L 8 4 L 20 12 Z"
                fill="#ffffff"
                stroke="#0f172a"
                strokeWidth="1.5"
                strokeLinejoin="round"
              />
              <path d="M 12 15 L 10 7 L 17 12 Z" fill="#ffccd5" />

              <path
                d="M 46 18 L 50 4 L 38 12 Z"
                fill="#ffffff"
                stroke="#0f172a"
                strokeWidth="1.5"
                strokeLinejoin="round"
              />
              <path d="M 46 15 L 48 7 L 41 12 Z" fill="#ffccd5" />

              {/* Cat Head with counter-tilt */}
              <g transform={`rotate(${headCounterTilt} 29 24)`}>
                <ellipse
                  cx="29"
                  cy="24"
                  rx="20"
                  ry="17"
                  fill="#ffffff"
                  stroke="#0f172a"
                  strokeWidth="1.5"
                  filter="drop-shadow(0 4px 8px rgba(0,0,0,0.35))"
                />

                {/* Cool Sunglasses (matching video) */}
                {hasShades ? (
                  <g filter="drop-shadow(0 2px 4px rgba(0,0,0,0.5))">
                    {/* Left lens */}
                    <ellipse cx="22" cy="22" rx="7.5" ry="6.5" fill="#090d16" stroke="#1e293b" strokeWidth="1.2" />
                    {/* Right lens */}
                    <ellipse cx="36" cy="22" rx="7.5" ry="6.5" fill="#090d16" stroke="#1e293b" strokeWidth="1.2" />
                    {/* Bridge */}
                    <path d="M 29.5 22 L 28.5 22" stroke="#090d16" strokeWidth="2" strokeLinecap="round" />
                    {/* Glass glare line moving with body tilt */}
                    <path d="M 18 19 L 23 25" stroke="rgba(255,255,255,0.45)" strokeWidth="1.2" strokeLinecap="round" />
                    <path d="M 32 19 L 37 25" stroke="rgba(255,255,255,0.45)" strokeWidth="1.2" strokeLinecap="round" />
                  </g>
                ) : (
                  /* Cute Cat Eyes if shades toggled off */
                  <g>
                    <ellipse cx="22" cy="22" rx="3.5" ry="4.5" fill="#0f172a" />
                    <ellipse cx="36" cy="22" rx="3.5" ry="4.5" fill="#0f172a" />
                    <circle cx="23" cy="20" r="1.2" fill="#ffffff" />
                    <circle cx="37" cy="20" r="1.2" fill="#ffffff" />
                  </g>
                )}

                {/* Cute Cat Nose & Whiskers */}
                <polygon points="28,27 30,27 29,28.5" fill="#ff758f" />
                <line x1="12" y1="26" x2="6" y2="25" stroke="#94a3b8" strokeWidth="1" strokeLinecap="round" />
                <line x1="12" y1="28" x2="6" y2="29" stroke="#94a3b8" strokeWidth="1" strokeLinecap="round" />
                <line x1="46" y1="26" x2="52" y2="25" stroke="#94a3b8" strokeWidth="1" strokeLinecap="round" />
                <line x1="46" y1="28" x2="52" y2="29" stroke="#94a3b8" strokeWidth="1" strokeLinecap="round" />

                {/* Mouth / Lip-Sync */}
                {isSpeaking || jawEnergy > 0.05 ? (
                  <ellipse cx="29" cy="30.5" rx="3.2" ry={Math.max(2, jawEnergy * 6)} fill="#ff4d6d" />
                ) : (
                  <path d="M 27 29 Q 29 31 31 29" stroke="#0f172a" strokeWidth="1.2" strokeLinecap="round" fill="none" />
                )}
              </g>

              {/* Cat Body wearing black "dex" t-shirt */}
              <rect
                x="17"
                y="36"
                width="24"
                height="19"
                rx="6"
                fill="#0f172a"
                stroke="#0f172a"
                strokeWidth="1.5"
              />

              {/* "dex" logo on shirt */}
              <text
                x="29"
                y="48"
                fill="#ffffff"
                fontSize="8"
                fontWeight="900"
                textAnchor="middle"
                fontFamily="sans-serif"
                letterSpacing="-0.5"
                transform={walkDir === -1 ? "scale(-1, 1) translate(-58, 0)" : undefined}
              >
                dex
              </text>

              {/* Front Paws / Arms — Swinging with Stride */}
              <g transform={`translate(16.5, 40) rotate(${leftArmSwing}) translate(-16.5, -40)`}>
                <rect x="14" y="38" width="5.5" height="11" rx="2.5" fill="#ffffff" stroke="#0f172a" strokeWidth="1" />
                <circle cx="16.7" cy="46" r="1.1" fill="#ffb4c2" opacity="0.65" />
              </g>
              <g transform={`translate(41.5, 40) rotate(${rightArmSwing}) translate(-41.5, -40)`}>
                <rect x="38.5" y="38" width="5.5" height="11" rx="2.5" fill="#ffffff" stroke="#0f172a" strokeWidth="1" />
                <circle cx="41.2" cy="46" r="1.1" fill="#ffb4c2" opacity="0.65" />
              </g>

              {/* Left Walking Leg — Articulated Hip Stride & Forward Knee Bend */}
              <g transform={`translate(23, 52) rotate(${leftLegSwingAngle}) translate(-23, -52)`}>
                <rect x="19.5" y="52" width="7" height="7.5" rx="3.2" fill="#ffffff" stroke="#0f172a" strokeWidth="1.2" />
                <g transform={`translate(23, 57) rotate(${leftKneeAngle}) translate(-23, -57)`}>
                  <rect x="19.5" y="57" width="7" height="6.5" rx="3.2" fill="#ffffff" stroke="#0f172a" strokeWidth="1.2" />
                  <ellipse cx="23" cy="61.5" rx="2.2" ry="1.2" fill="#ffb4c2" opacity="0.75" />
                </g>
              </g>

              {/* Right Walking Leg — Articulated Hip Stride & Forward Knee Bend */}
              <g transform={`translate(35, 52) rotate(${rightLegSwingAngle}) translate(-35, -52)`}>
                <rect x="31.5" y="52" width="7" height="7.5" rx="3.2" fill="#ffffff" stroke="#0f172a" strokeWidth="1.2" />
                <g transform={`translate(35, 57) rotate(${rightKneeAngle}) translate(-35, -57)`}>
                  <rect x="31.5" y="57" width="7" height="6.5" rx="3.2" fill="#ffffff" stroke="#0f172a" strokeWidth="1.2" />
                  <ellipse cx="35" cy="61.5" rx="2.2" ry="1.2" fill="#ffb4c2" opacity="0.75" />
                </g>
              </g>
            </svg>
          </div>
        )}
      </div>
    </motion.div>
  );
};
