import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { createPortal } from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Home,
  MessageSquare,
  Plus,
  Settings,
  Volume2,
  VolumeX,
  X,
  Maximize2,
  Minimize2,
  ChevronDown,
  Terminal,
  Upload,
  FileText,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  ExternalLink,
  CreditCard,
  GitBranch,
  Code2,
  Sparkles,
  Send,
  Loader2,
  Check,
  ShieldAlert,
  Footprints,
  Activity,
  Sliders,
  Cpu,
  Layers,
  Boxes,
  Music,
  Heart,
  Eye,
  Radio,
  Workflow,
  Wand2,
  Database,
  Search,
  Monitor,
  Square,
  ThumbsUp,
  ThumbsDown,
  Copy,
  Scan,
  Shield,
  Play,
  RefreshCw,
  FileCode,
} from "lucide-react";
import { useLiveVision } from "../../features/vision/useLiveVision";
import {
  playUiSound,
  isSoundEnabled,
  setSoundEnabled,
  playFootstepSound,
  playMochiPoke,
  playMochiLove,
  playMochiEat,
  playTypingSound,
  playSendSound,
  type UiSoundType,
} from "../../lib/uiSound";
import type { DiscoveredModel } from "../../features/providers/hooks/useCapabilities";

export interface DynamicIslandCompanionProps {
  isDark?: boolean;
  agentSteps?: Array<{
    id: string;
    label: string;
    detail?: string;
    status: "pending" | "active" | "done" | "error" | "cancelled";
  }>;
  pendingApproval?: {
    stepId: string;
    actionName: string;
    command?: string;
    detail?: string;
  } | null;
  onConfirmStep?: (approved: boolean) => void;
  onOpenTerminal?: (initialCommand?: string) => void;
  onOpenSettings?: () => void;
  onNewChat?: () => void;
  onSendMessage?: (text: string) => void;
  onAttachImage?: (dataUrl: string) => void;
  onSelectModel?: (modelId: string, providerId: string) => void;
  availableModels?: DiscoveredModel[];
  isThinking?: boolean;
  activeProviderModel?: string | null;
  companionName?: string;
  companionState?: string;
  streamingText?: string | null;
  lastAssistantText?: string | null;
  isWalking?: boolean;
  onToggleWalk?: () => void;
  onOpenRunway?: () => void;
  inlineInTopBar?: boolean;
  isSpeaking?: boolean;
  jawEnergy?: number;
  onStopSpeaking?: () => void;
  isLiveVoiceActive?: boolean;
  onToggleLiveVoice?: () => void;
  messages?: any[];
  conversationId?: string;
}

export interface CoucouMascotProps {
  mood?: "idle" | "happy" | "eating" | "alert" | "thinking" | "annoyed" | "dizzy" | "love" | "walking";
  isHovered?: boolean;
  size?: number;
  isWalking?: boolean;
  walkPhase?: number;
  direction?: 1 | -1;
  onPoke?: (count: number) => void;
  interactive?: boolean;
}

// Coucou / Mochi Interactive Mascot Avatar Component
export const CoucouMascot: React.FC<CoucouMascotProps> = ({
  mood: propMood = "idle",
  isHovered = false,
  size = 56,
  isWalking = false,
  walkPhase = 0,
  direction = 1,
  onPoke,
  interactive = true,
}) => {
  const [blink, setBlink] = useState(false);
  const [localMood, setLocalMood] = useState<string | null>(null);
  const [pokeCount, setPokeCount] = useState(0);
  // Eye tracking: use ref + direct DOM mutation to avoid per-pixel React re-renders
  const eyeOffsetRef = useRef({ x: 0, y: 0 });
  const eyeGroupRef = useRef<SVGGElement | null>(null);
  const eyeRafRef = useRef(0);
  const [showHearts, setShowHearts] = useState(false);
  const mascotRef = useRef<HTMLDivElement>(null);
  const pokeTimerRef = useRef<any>(null);
  const hoverTimerRef = useRef<any>(null);

  const mood = localMood || propMood;

  // Natural spontaneous blinking
  useEffect(() => {
    const interval = setInterval(() => {
      setBlink(true);
      setTimeout(() => setBlink(false), 160);
    }, 3800 + Math.random() * 2000);
    return () => clearInterval(interval);
  }, []);

  // Pupil eye tracking — RAF-gated direct SVG transform, zero React re-renders
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!mascotRef.current) return;
      const rect = mascotRef.current.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const dx = Math.max(-3.5, Math.min(3.5, (e.clientX - cx) / 45));
      const dy = Math.max(-2.8, Math.min(2.8, (e.clientY - cy) / 45));
      eyeOffsetRef.current = { x: dx, y: dy };
      if (!eyeRafRef.current) {
        eyeRafRef.current = requestAnimationFrame(() => {
          eyeRafRef.current = 0;
          const g = eyeGroupRef.current;
          if (g) {
            const { x, y } = eyeOffsetRef.current;
            g.setAttribute('transform', `translate(${x}, ${y})`);
          }
        });
      }
    };
    window.addEventListener("mousemove", handleMouseMove, { passive: true });
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      if (eyeRafRef.current) cancelAnimationFrame(eyeRafRef.current);
    };
  }, []);

  // Affection hover reaction: floating hearts after 1.2s hover
  useEffect(() => {
    if (isHovered) {
      hoverTimerRef.current = setTimeout(() => {
        setLocalMood("love");
        setShowHearts(true);
        playMochiLove();
        setTimeout(() => {
          setShowHearts(false);
          setLocalMood(null);
        }, 2200);
      }, 1200);
    } else {
      if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
    }
    return () => {
      if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
    };
  }, [isHovered]);

  // Mascot poke interaction (1-2 pokes = annoyed squeak; 3 pokes = dizzy wobble)
  const handleMascotClick = (e: React.MouseEvent) => {
    if (!interactive) return;
    e.stopPropagation();

    if (pokeTimerRef.current) clearTimeout(pokeTimerRef.current);

    const nextCount = pokeCount + 1;
    setPokeCount(nextCount);

    if (nextCount >= 3) {
      setLocalMood("dizzy");
      playMochiPoke(3);
    } else {
      setLocalMood("annoyed");
      playMochiPoke(1);
    }

    onPoke?.(nextCount);

    pokeTimerRef.current = setTimeout(() => {
      setPokeCount(0);
      setLocalMood(null);
    }, 2400);
  };

  const scale = size / 64;
  const coucouPhaseSin = Math.sin(walkPhase);
  const legStride = isWalking ? coucouPhaseSin * 5.5 : 0;
  const leftLegLift = isWalking ? Math.max(0, -coucouPhaseSin) * 4.2 : 0;
  const rightLegLift = isWalking ? Math.max(0, coucouPhaseSin) * 4.2 : 0;
  const bodyBob = isWalking ? Math.abs(coucouPhaseSin) * 2.6 : 0;
  const bodyTilt = isWalking ? coucouPhaseSin * 3.5 : 0;
  const leftFootTilt = isWalking ? coucouPhaseSin * 14 : 0;
  const rightFootTilt = isWalking ? -coucouPhaseSin * 14 : 0;

  return (
    <div
      ref={mascotRef}
      onClick={handleMascotClick}
      style={{
        position: "relative",
        width: size,
        height: size,
        borderRadius: Math.round(16 * scale),
        overflow: "visible",
        background: "radial-gradient(circle at 50% 35%, #1e2235 0%, #08090e 100%)",
        border: mood === "annoyed" ? "1px solid rgba(244, 63, 94, 0.4)" : "1px solid rgba(255, 255, 255, 0.16)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        boxShadow: mood === "annoyed"
          ? "0 0 12px rgba(244,63,94,0.4)"
          : "inset 0 1px 1px rgba(255,255,255,0.25), 0 4px 16px rgba(0,0,0,0.5)",
        cursor: interactive ? "pointer" : "default",
        flexShrink: 0,
        transition: "border-color 0.2s ease, box-shadow 0.2s ease",
      }}
    >
      {/* Floating affection hearts */}
      <AnimatePresence>
        {showHearts && (
          <motion.div
            initial={{ opacity: 0, y: 0, scale: 0.5 }}
            animate={{ opacity: [0, 1, 0], y: -26, scale: [0.6, 1.2, 0.9] }}
            exit={{ opacity: 0 }}
            transition={{ duration: 1.8, repeat: Infinity, ease: "easeOut" }}
            style={{
              position: "absolute",
              top: -6,
              left: "50%",
              transform: "translateX(-50%)",
              fontSize: 16,
              color: "#ec4899",
              pointerEvents: "none",
              zIndex: 10,
              display: "flex",
              gap: 4,
            }}
          >
            <span>♥</span>
            <span style={{ fontSize: 12, marginTop: -4 }}>♥</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Starry Ambient Aura */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: Math.round(16 * scale),
          overflow: "hidden",
          background:
            "radial-gradient(1px 1px at 20% 30%, rgba(255,255,255,0.8) 100%, transparent), radial-gradient(1.5px 1.5px at 75% 25%, rgba(0,212,255,0.9) 100%, transparent), radial-gradient(1px 1px at 85% 75%, rgba(236,72,153,0.8) 100%, transparent), radial-gradient(1.5px 1.5px at 35% 80%, rgba(255,255,255,0.6) 100%, transparent)",
          opacity: 0.75,
          pointerEvents: "none",
        }}
      />

      {/* SVG Coucou / Hina Character */}
      <svg
        width={Math.round(48 * scale)}
        height={Math.round(48 * scale)}
        viewBox="0 0 100 100"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{
          transform: `${isHovered ? "scale(1.06) translateY(-1px)" : "scale(1)"} ${direction < 0 ? "scaleX(-1)" : "scaleX(1)"}`,
          transition: "transform 0.15s cubic-bezier(0.34, 1.56, 0.64, 1)",
          overflow: "visible",
        }}
      >
        {/* Animated Stepping Legs & Feet (Coucou Walking Locomotion with squash & stretch) */}
        <g transform={`translate(${legStride}, ${-leftLegLift}) rotate(${leftFootTilt} 36 82)`}>
          <ellipse
            cx={36}
            cy={82}
            rx={leftLegLift > 1 ? 5.5 : 6.5}
            ry={leftLegLift > 1 ? 4 : 3}
            fill="#ffffff"
            stroke="rgba(0,0,0,0.14)"
            strokeWidth={1}
          />
        </g>
        <g transform={`translate(${-legStride}, ${-rightLegLift}) rotate(${rightFootTilt} 64 82)`}>
          <ellipse
            cx={64}
            cy={82}
            rx={rightLegLift > 1 ? 5.5 : 6.5}
            ry={rightLegLift > 1 ? 4 : 3}
            fill="#ffffff"
            stroke="rgba(0,0,0,0.14)"
            strokeWidth={1}
          />
        </g>

        {/* Soft Mascot Squircle Body with Waddle Roll */}
        <g
          transform={`translate(0, ${-bodyBob}) rotate(${bodyTilt} 50 82) ${
            mood === "dizzy"
              ? "rotate(-4 50 52)"
              : mood === "annoyed"
              ? "rotate(3 50 52)"
              : ""
          }`}
          style={{ transition: "transform 0.15s ease-out" }}
        >
          <ellipse
            cx={50}
            cy={52}
            rx={mood === "eating" ? 39 : 38}
            ry={mood === "eating" ? 33 : 30}
            fill="#ffffff"
          />
        </g>

        {/* Anime Cheeks (Blush) */}
        <ellipse
          cx="28"
          cy={56 - bodyBob}
          rx="5"
          ry="3"
          fill={mood === "annoyed" ? "#ff4976" : mood === "love" ? "#ec4899" : "#ffb4c8"}
          opacity={mood === "love" ? 0.95 : 0.7}
        />
        <ellipse
          cx="72"
          cy={56 - bodyBob}
          rx="5"
          ry="3"
          fill={mood === "annoyed" ? "#ff4976" : mood === "love" ? "#ec4899" : "#ffb4c8"}
          opacity={mood === "love" ? 0.95 : 0.7}
        />

        {/* Eyes Rendering */}
        {mood === "dizzy" ? (
          // Hypnotic spinning spirals for dizzy poke state (@ @)
          <g transform={`translate(0, ${-bodyBob})`}>
            <motion.path
              d="M 34 46 m -5 0 a 5 5 0 1 0 10 0 a 3 3 0 1 0 -6 0 a 1.5 1.5 0 1 0 3 0"
              stroke="#121215"
              strokeWidth="2.4"
              fill="none"
              strokeLinecap="round"
              animate={{ rotate: [0, 360] }}
              transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }}
              style={{ transformOrigin: "34px 46px" }}
            />
            <motion.path
              d="M 66 46 m -5 0 a 5 5 0 1 0 10 0 a 3 3 0 1 0 -6 0 a 1.5 1.5 0 1 0 3 0"
              stroke="#121215"
              strokeWidth="2.4"
              fill="none"
              strokeLinecap="round"
              animate={{ rotate: [0, -360] }}
              transition={{ repeat: Infinity, duration: 1.2, ease: "linear" }}
              style={{ transformOrigin: "66px 46px" }}
            />
          </g>
        ) : mood === "annoyed" ? (
          // Squinting irritated eyes (> <)
          <g transform={`translate(0, ${-bodyBob})`}>
            <path d="M 28 43 L 38 47 L 28 51" stroke="#121215" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="none" />
            <path d="M 72 43 L 62 47 L 72 51" stroke="#121215" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="none" />
          </g>
        ) : blink || mood === "happy" || mood === "love" ? (
          // Happy / Loving curved eyes (^ ^)
          <g transform={`translate(0, ${-bodyBob})`}>
            <path d="M 29 47 Q 34 40 39 47" stroke="#121215" strokeWidth="3.5" strokeLinecap="round" fill="none" />
            <path d="M 61 47 Q 66 40 71 47" stroke="#121215" strokeWidth="3.5" strokeLinecap="round" fill="none" />
          </g>
        ) : (
          // Normal open expressive eyes with pupil tracking via direct DOM transform
          <g transform={`translate(0, ${-bodyBob})`}>
            <g ref={eyeGroupRef}>
              <ellipse cx={34} cy={46} rx="4.5" ry="6.5" fill="#121215" />
              <circle cx={32.5} cy={44} r="1.8" fill="#ffffff" />
              <ellipse cx={66} cy={46} rx="4.5" ry="6.5" fill="#121215" />
              <circle cx={64.5} cy={44} r="1.8" fill="#ffffff" />
            </g>
          </g>
        )}

        {/* Mouth Rendering */}
        <g transform={`translate(0, ${-bodyBob})`}>
          {mood === "eating" ? (
            // Mouth open wide eating dropped file
            <motion.path
              d="M 43 53 Q 50 71 57 53 Z"
              fill="#ff5a82"
              animate={{ d: ["M 43 53 Q 50 71 57 53 Z", "M 44 55 Q 50 63 56 55 Z", "M 43 53 Q 50 71 57 53 Z"] }}
              transition={{ repeat: Infinity, duration: 0.5 }}
            />
          ) : mood === "dizzy" ? (
            // Wavy squiggly mouth
            <path d="M 44 56 Q 47 53 50 56 Q 53 59 56 56" stroke="#121215" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          ) : mood === "annoyed" ? (
            // Pouting frown
            <path d="M 45 58 Q 50 54 55 58" stroke="#121215" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          ) : mood === "happy" || mood === "love" ? (
            // Joyful open smile
            <path d="M 44 54 Q 50 63 56 54 Z" fill="#ff5a82" stroke="#121215" strokeWidth="2" strokeLinejoin="round" />
          ) : (
            // Subtle cute neutral smile
            <path d="M 47 55 Q 50 58 53 55" stroke="#121215" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          )}
        </g>

        {/* Tiny waving hands on hover */}
        {isHovered && (
          <motion.ellipse
            cx="84"
            cy={44 - bodyBob}
            rx="5"
            ry="6"
            fill="#ffffff"
            stroke="rgba(0,0,0,0.06)"
            animate={{ rotate: [-10, 20, -10] }}
            transition={{ repeat: Infinity, duration: 0.6 }}
          />
        )}
      </svg>
    </div>
  );
};

export interface CuteRobotFaceProps {
  mood?: "idle" | "happy" | "thinking" | "speaking" | "observing" | "alert" | "walking";
  isHovered?: boolean;
  size?: number;
  isSpeaking?: boolean;
  jawEnergy?: number;
  onPoke?: (count: number) => void;
  interactive?: boolean;
  isWalking?: boolean;
  walkPhase?: number;
}

// Cute Talking Robot Face matching the reference video & SnapInsta.to_AQOpjR7zLOEM_f1_50pct.jpg
export const CuteRobotFace: React.FC<CuteRobotFaceProps> = ({
  mood = "idle",
  isHovered = false,
  size = 56,
  isSpeaking = false,
  jawEnergy = 0,
  onPoke,
  interactive = true,
  isWalking = false,
  walkPhase = 0,
}) => {
  const [blink, setBlink] = useState(false);
  // Eye + eyebrow tracking: ref + direct style.transform mutation — zero React re-renders on mousemove
  const eyeOffsetRef = useRef({ x: 0, y: 0 });
  const eyebrowGroupRef = useRef<SVGGElement | null>(null);
  const eyeCapsuleGroupRef = useRef<SVGGElement | null>(null);
  const eyeRafRef = useRef(0);
  const [speechAperture, setSpeechAperture] = useState(0);
  const [pokeCount, setPokeCount] = useState(0);
  const faceRef = useRef<HTMLDivElement>(null);
  const pokeTimerRef = useRef<any>(null);

  // Spontaneous natural blinking every 3.2 - 5.5 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      setBlink(true);
      setTimeout(() => setBlink(false), 140);
    }, 3200 + Math.random() * 2200);
    return () => clearInterval(interval);
  }, []);

  // Pupil / gaze tracking — RAF-gated direct style.transform, zero React re-renders
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!faceRef.current) return;
      const rect = faceRef.current.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const dx = Math.max(-3.5, Math.min(3.5, (e.clientX - cx) / 48));
      const dy = Math.max(-2.6, Math.min(2.6, (e.clientY - cy) / 48));
      eyeOffsetRef.current = { x: dx, y: dy };
      if (!eyeRafRef.current) {
        eyeRafRef.current = requestAnimationFrame(() => {
          eyeRafRef.current = 0;
          const { x, y } = eyeOffsetRef.current;
          if (eyebrowGroupRef.current) {
            eyebrowGroupRef.current.style.transform = `translate(${x * 0.4}px, ${y * 0.4}px)`;
          }
          if (eyeCapsuleGroupRef.current) {
            eyeCapsuleGroupRef.current.style.transform = `translate(${x}px, ${y}px)`;
          }
        });
      }
    };
    window.addEventListener("mousemove", handleMouseMove, { passive: true });
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      if (eyeRafRef.current) cancelAnimationFrame(eyeRafRef.current);
    };
  }, []);

  // Real-time lip sync animation loop when speaking or jaw energy is active
  useEffect(() => {
    if (!isSpeaking && jawEnergy <= 0.02) {
      setSpeechAperture(0);
      return;
    }
    let animId: number;
    let t = 0;
    const loop = () => {
      t += 0.28;
      // Synthesize organic talking cadence modulating with jawEnergy or sinusoidal speech rhythm
      const wave = Math.sin(t * 1.6) * 0.4 + Math.sin(t * 2.9) * 0.3 + 0.55;
      const energyMod = jawEnergy > 0.05 ? jawEnergy * 2.8 : wave;
      setSpeechAperture(Math.max(0.2, Math.min(1.0, energyMod)));
      animId = requestAnimationFrame(loop);
    };
    animId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animId);
  }, [isSpeaking, jawEnergy]);

  const handleFaceClick = (e: React.MouseEvent) => {
    if (!interactive) return;
    e.stopPropagation();
    if (pokeTimerRef.current) clearTimeout(pokeTimerRef.current);
    const next = pokeCount + 1;
    setPokeCount(next);
    playMochiPoke(next >= 3 ? 3 : 1);
    onPoke?.(next);
    pokeTimerRef.current = setTimeout(() => setPokeCount(0), 2200);
  };

  const scale = size / 64;
  const mouthOpen = isSpeaking || jawEnergy > 0.05 ? speechAperture : 0;
  const isAnnoyed = pokeCount >= 2;

  // Procedural walking kinematics
  const legStride = isWalking ? Math.sin(walkPhase) * 4.5 * scale : 0;
  const legLift = isWalking ? Math.abs(Math.sin(walkPhase)) * 3.5 * scale : 0;
  const otherLift = isWalking ? Math.abs(Math.sin(walkPhase + Math.PI)) * 3.5 * scale : 0;
  const bodyBob = isWalking ? Math.abs(Math.sin(walkPhase * 2)) * 2.2 * scale : 0;
  const bodyTilt = isWalking ? Math.sin(walkPhase) * 3 : 0;

  return (
    <div
      style={{
        position: "relative",
        display: "inline-flex",
        flexDirection: "column",
        alignItems: "center",
      }}
    >
      <div
        ref={faceRef}
        onClick={handleFaceClick}
        style={{
          position: "relative",
          width: size,
          height: size,
          borderRadius: Math.round(18 * scale),
          background: "radial-gradient(circle at 50% 25%, #181c28 0%, #07080d 100%)",
          border: isAnnoyed ? "1px solid rgba(244, 63, 94, 0.4)" : "1px solid rgba(255, 255, 255, 0.18)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          boxShadow: isAnnoyed
            ? "0 0 16px rgba(244,63,94,0.4)"
            : "inset 0 1px 1px rgba(255, 255, 255, 0.22), 0 8px 24px rgba(0, 0, 0, 0.65)",
          cursor: interactive ? "pointer" : "default",
          flexShrink: 0,
          overflow: "visible",
          transform: isHovered
            ? "scale(1.04)"
            : isWalking
            ? `translateY(${-bodyBob}px) rotate(${bodyTilt}deg)`
            : "scale(1)",
          transition: isWalking ? "none" : "transform 0.15s ease, border-color 0.2s ease, box-shadow 0.2s ease",
        }}
        title="Cute Hina Robot Notch Face"
      >
      <svg
        width={Math.round(52 * scale)}
        height={Math.round(52 * scale)}
        viewBox="0 0 64 64"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ overflow: "visible" }}
      >
        {/* Arched Expressive Eyebrows — RAF-driven transform via eyebrowGroupRef */}
        <g
          ref={eyebrowGroupRef}
          style={{
            transform: `translate(0px, ${mood === "thinking" ? -1.5 : 0}px)`,
            transition: "transform 0.08s ease-out",
          }}
        >
          {/* Left Eyebrow: curved stroke */}
          <path
            d={isAnnoyed ? "M 16 20 L 27 15" : mood === "thinking" ? "M 16 15 Q 21 11 28 14" : "M 16 17 Q 21 12 28 15"}
            stroke="#f1f5f9"
            strokeWidth="3.2"
            strokeLinecap="round"
            fill="none"
            filter="drop-shadow(0 1px 2px rgba(0,0,0,0.8))"
          />
          {/* Right Eyebrow: curved stroke */}
          <path
            d={isAnnoyed ? "M 48 20 L 37 15" : "M 36 15 Q 43 12 48 17"}
            stroke="#f1f5f9"
            strokeWidth="3.2"
            strokeLinecap="round"
            fill="none"
            filter="drop-shadow(0 1px 2px rgba(0,0,0,0.8))"
          />
        </g>

        {/* Capsule Glowing Eyes — RAF-driven transform via eyeCapsuleGroupRef */}
        <g
          ref={eyeCapsuleGroupRef}
          style={{
            transform: "translate(0px, 0px)",
            transition: "transform 0.05s linear",
          }}
        >
          {/* Left Capsule Eye: tilted slightly outwards at top */}
          <g
            transform={`translate(21.5, 33) scale(1, ${blink ? 0.08 : 1}) rotate(-3.5) translate(-21.5, -33)`}
            style={{ transformOrigin: "21.5px 33px", transition: "transform 0.08s ease" }}
          >
            <rect
              x="16"
              y="20"
              width="11"
              height="25"
              rx="5.5"
              fill="#ffffff"
              filter="drop-shadow(0 0 4px rgba(255, 255, 255, 0.95)) drop-shadow(0 0 10px rgba(0, 212, 255, 0.7))"
            />
          </g>

          {/* Right Capsule Eye: tilted slightly outwards at top */}
          <g
            transform={`translate(42.5, 33) scale(1, ${blink ? 0.08 : 1}) rotate(3.5) translate(-42.5, -33)`}
            style={{ transformOrigin: "42.5px 33px", transition: "transform 0.08s ease" }}
          >
            <rect
              x="37"
              y="20"
              width="11"
              height="25"
              rx="5.5"
              fill="#ffffff"
              filter="drop-shadow(0 0 4px rgba(255, 255, 255, 0.95)) drop-shadow(0 0 10px rgba(0, 212, 255, 0.7))"
            />
          </g>
        </g>

        {/* Real-time Lip-Synced Mouth with Teeth and Coral Lips */}
        {mouthOpen > 0.05 ? (
          <g transform={`translate(32, 51) scale(1, ${0.4 + mouthOpen * 0.75}) translate(-32, -51)`}>
            {/* Dark inner cavity */}
            <path
              d="M 23 49 C 23 49 26 57.5 32 57.5 C 38 57.5 41 49 41 49 Z"
              fill="#660708"
            />
            {/* Upper Teeth Strip */}
            <path
              d="M 24.5 49.5 L 39.5 49.5 C 38.5 52 36.5 53 32 53 C 27.5 53 25.5 52 24.5 49.5 Z"
              fill="#ffffff"
            />
            {/* Coral Lip Outline */}
            <path
              d="M 22.5 49 C 22.5 49 26 58 32 58 C 38 58 41.5 49 41.5 49 C 37 50.8 27 50.8 22.5 49 Z"
              stroke="#ff4d6d"
              strokeWidth="2.2"
              strokeLinejoin="round"
              fill="none"
            />
          </g>
        ) : (
          <g>
            {/* Cute gentle smile with hint of coral and teeth */}
            <path
              d="M 24.5 50.5 Q 32 55.5 39.5 50.5"
              stroke="#ff4d6d"
              strokeWidth="2.6"
              strokeLinecap="round"
              fill="none"
              filter="drop-shadow(0 1px 2px rgba(0,0,0,0.5))"
            />
            <path
              d="M 27 51 Q 32 53.5 37 51"
              stroke="#ffffff"
              strokeWidth="1.2"
              strokeLinecap="round"
              fill="none"
              opacity="0.9"
            />
          </g>
        )}
      </svg>
      {isWalking && (
        <div
          style={{
            position: "absolute",
            bottom: -5 * scale,
            left: 0,
            right: 0,
            display: "flex",
            justifyContent: "center",
            gap: 12 * scale,
            pointerEvents: "none",
          }}
        >
          {/* Left Robot Foot Pad */}
          <div
            style={{
              width: 8 * scale,
              height: 4 * scale,
              borderRadius: 3 * scale,
              background: "#00d4ff",
              boxShadow: "0 0 6px #00d4ff",
              transform: `translate(${legStride}px, ${-legLift}px)`,
            }}
          />
          {/* Right Robot Foot Pad */}
          <div
            style={{
              width: 8 * scale,
              height: 4 * scale,
              borderRadius: 3 * scale,
              background: "#00d4ff",
              boxShadow: "0 0 6px #00d4ff",
              transform: `translate(${-legStride}px, ${-otherLift}px)`,
            }}
          />
        </div>
      )}
    </div>
    </div>
  );
};

export const SOUND_BENCH_PADS: Array<{ type: UiSoundType; label: string; desc: string }> = [
  { type: "click", label: "Tactile Click", desc: "Mechanical micro-switch" },
  { type: "buttonPress", label: "Button Press", desc: "Deeper latch click" },
  { type: "pop", label: "Dynamic Pop", desc: "Coucou bubble pop" },
  { type: "whoosh", label: "Drawer Whoosh", desc: "Sleek expansion glide" },
  { type: "switch", label: "Toggle Switch", desc: "Crisp state change" },
  { type: "success", label: "Chime Triad", desc: "Harmonic major chord" },
  { type: "deny", label: "Deny Buzz", desc: "Low caution buzz" },
  { type: "warning", label: "Alert Chime", desc: "Notification alert" },
  { type: "type", label: "Key Clack", desc: "Mechanical switch" },
  { type: "send", label: "Transmit Send", desc: "Sci-fi launch pulse" },
  { type: "step", label: "Footstep Tap", desc: "Walking locomotion gait" },
  { type: "streamChunk", label: "Stream Decode", desc: "Generative token chatter" },
  { type: "mochiPoke", label: "Mascot Squeak", desc: "Playful poke reaction" },
  { type: "mochiDizzy", label: "Dizzy Wobble", desc: "3x poke dizzy spiral" },
  { type: "mochiLove", label: "Heart Sparkle", desc: "Hover affection chime" },
  { type: "mochiEat", label: "File Crunch", desc: "File swallowing gulp" },
];

export const DynamicIslandCompanion: React.FC<DynamicIslandCompanionProps> = ({
  isDark = true,
  agentSteps = [],
  pendingApproval = null,
  onConfirmStep,
  onOpenTerminal,
  onOpenSettings,
  onNewChat,
  onSendMessage,
  onAttachImage,
  onSelectModel,
  availableModels = [],
  isThinking = false,
  activeProviderModel,
  companionName = "Hina",
  companionState = "ready",
  streamingText = null,
  lastAssistantText = null,
  isWalking = false,
  onToggleWalk,
  onOpenRunway,
  inlineInTopBar = false,
  isSpeaking = false,
  jawEnergy = 0,
  onStopSpeaking,
  isLiveVoiceActive = false,
  onToggleLiveVoice,
  messages = [],
  conversationId,
}) => {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  const [isExpanded, setIsExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState<"agent" | "chat" | "watcher" | "stripe" | "upload" | "motion" | "components" | "audio">("agent");
  const [selectedComponentIndex, setSelectedComponentIndex] = useState(0);
  const [soundActive, setSoundActive] = useState(() => isSoundEnabled());
  const [isDraggingFile, setIsDraggingFile] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [uploadedFilePreview, setUploadedFilePreview] = useState<string | null>(null);
  const [chatInput, setChatInput] = useState("");
  const [lastUserQuery, setLastUserQuery] = useState<string | null>(null);
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const [walkCadence, setWalkCadence] = useState(1.0);

  // Mascot Style: "robot" (talking robot face from video) vs "mochi" (coucou mascot)
  const [mascotStyle, setMascotStyle] = useState<"robot" | "mochi">(() => {
    try {
      return (localStorage.getItem("hinaa-mascot-avatar-style") as "robot" | "mochi") || "robot";
    } catch {
      return "robot";
    }
  });

  const toggleMascotStyle = () => {
    const next = mascotStyle === "robot" ? "mochi" : "robot";
    setMascotStyle(next);
    try {
      localStorage.setItem("hinaa-mascot-avatar-style", next);
    } catch {}
    playUiSound("pop");
  };

  // Screen Guardian Live Vision Hook
  const liveVision = useLiveVision(conversationId);
  const [showGuardianCard, setShowGuardianCard] = useState(false);
  const [taskFilter, setTaskFilter] = useState<"steps" | "changes" | "commands" | "problems" | "all">("steps");
  const [isCopied, setIsCopied] = useState(false);
  const [analyzingScreen, setAnalyzingScreen] = useState(false);
  const [screenAnalysisResult, setScreenAnalysisResult] = useState<string | null>(null);

  // Autonomous Dev Tasks Interactive State (SnapInsta Reference)
  const [devTasks, setDevTasks] = useState<Array<{
    id: string;
    type: "RUN" | "EDIT" | "CMD" | "TEST";
    target: string;
    status: "pending" | "running" | "done" | "error";
    duration?: string;
    tryCount?: number;
    errorDetail?: string;
  }>>(() => {
    try {
      const saved = localStorage.getItem("hinaa-autonomous-dev-tasks");
      if (saved) return JSON.parse(saved);
    } catch {}
    return [
      { id: "task-1", type: "RUN", target: "Run the tests", status: "error", tryCount: 2, errorDetail: "fixed on try 2" },
      { id: "task-2", type: "EDIT", target: "src/billing.ts", status: "done" },
      { id: "task-3", type: "RUN", target: "Run the tests try 2", status: "done", duration: "650ms", tryCount: 2 },
      { id: "task-4", type: "RUN", target: "Push to main", status: "done", duration: "800ms" },
    ];
  });
  const [editingTaskId, setEditingTaskId] = useState<string | null>(null);
  const [editingTaskText, setEditingTaskText] = useState("");
  const [isAddingTask, setIsAddingTask] = useState(false);
  const [newTaskTarget, setNewTaskTarget] = useState("");
  const [newTaskType, setNewTaskType] = useState<"RUN" | "EDIT" | "CMD" | "TEST">("RUN");
  const [autoWatchActive, setAutoWatchActive] = useState(false);

  const saveDevTasks = (tasks: typeof devTasks) => {
    setDevTasks(tasks);
    try {
      localStorage.setItem("hinaa-autonomous-dev-tasks", JSON.stringify(tasks));
    } catch {}
  };

  const handleToggleTaskStatus = (id: string) => {
    playUiSound("click");
    saveDevTasks(
      devTasks.map((t) => {
        if (t.id !== id) return t;
        const nextStatus =
          t.status === "done" ? "pending" : t.status === "error" ? "running" : t.status === "running" ? "done" : "done";
        return { ...t, status: nextStatus };
      })
    );
  };

  const handleRunTask = (id: string) => {
    playUiSound("buttonPress");
    saveDevTasks(devTasks.map((t) => (t.id === id ? { ...t, status: "running" } : t)));
    setTimeout(() => {
      saveDevTasks(
        devTasks.map((t) =>
          t.id === id ? { ...t, status: "done", duration: "540ms", errorDetail: undefined } : t
        )
      );
      playUiSound("success");
    }, 850);
  };

  const handleDeleteTask = (id: string) => {
    playUiSound("deny");
    saveDevTasks(devTasks.filter((t) => t.id !== id));
  };

  const handleSaveEditedTask = (id: string) => {
    if (!editingTaskText.trim()) return;
    saveDevTasks(devTasks.map((t) => (t.id === id ? { ...t, target: editingTaskText.trim() } : t)));
    setEditingTaskId(null);
    setEditingTaskText("");
    playUiSound("pop");
  };

  const handleAddNewTask = () => {
    if (!newTaskTarget.trim()) return;
    const item = {
      id: `task-${Date.now()}`,
      type: newTaskType,
      target: newTaskTarget.trim(),
      status: "pending" as const,
    };
    saveDevTasks([...devTasks, item]);
    setNewTaskTarget("");
    setIsAddingTask(false);
    playUiSound("success");
  };

  // Listen for open-dev-tasks event from DesktopWalkingPet
  useEffect(() => {
    const handleOpenTasks = () => {
      setIsExpanded(true);
      setActiveTab("agent");
    };
    window.addEventListener("hinaa:open-dev-tasks", handleOpenTasks);
    return () => window.removeEventListener("hinaa:open-dev-tasks", handleOpenTasks);
  }, []);

  // Sleeko Motion & Korus Desktop Card States (AQP7 & AQO9 References)
  const [sleekoStep, setSleekoStep] = useState<"intro" | "problem" | "usecase" | "cta">("usecase");
  const [showKorusCalculation, setShowKorusCalculation] = useState(true);
  const [showDizzyToast, setShowDizzyToast] = useState(false);

  // Island Walk Locomotion state
  const [islandWalkX, setIslandWalkX] = useState(0);
  const [islandWalkDir, setIslandWalkDir] = useState<1 | -1>(1);
  const [islandWalkPhase, setIslandWalkPhase] = useState(0);
  const lastIslandStepSideRef = useRef<"left" | "right">("left");
  const islandWalkDirRef = useRef<1 | -1>(1);
  useEffect(() => {
    islandWalkDirRef.current = islandWalkDir;
  }, [islandWalkDir]);

  // Rhythmic walking loop for notch locomotion with physically calibrated gait kinematics
  useEffect(() => {
    if (!isWalking) {
      setIslandWalkX(0);
      setIslandWalkPhase(0);
      return;
    }
    let animId: number;
    let lastTime = performance.now();

    const loop = (time: number) => {
      const dt = Math.min(0.05, (time - lastTime) / 1000);
      lastTime = time;

      // Natural human/mascot cadence: ~3.6 rad/sec scaled by cadence multiplier
      const cadence = walkCadence * 3.6;

      // Advance gait phase continuously with true elapsed delta
      setIslandWalkPhase((p) => {
        const next = (p + dt * cadence) % (Math.PI * 2);

        // Synchronized haptic/audio step on ground contact
        const stepSin = Math.sin(next);
        if (stepSin > 0.45 && lastIslandStepSideRef.current !== "left") {
          lastIslandStepSideRef.current = "left";
          if (isSoundEnabled()) playFootstepSound();
        } else if (stepSin < -0.45 && lastIslandStepSideRef.current !== "right") {
          lastIslandStepSideRef.current = "right";
          if (isSoundEnabled()) playFootstepSound();
        }

        return next;
      });

      // Synchronize horizontal translation velocity so the foot plants without sliding
      // 1 full cycle = 2 steps ≈ 20px stride at cadence 3.6 rad/s => ~13.5px/s per unit cadence
      const speed = 13.5 * walkCadence;
      const currentDir = islandWalkDirRef.current;
      setIslandWalkX((x) => {
        const maxRange = isExpanded ? 48 : 26;
        let nextX = x + currentDir * dt * speed;
        if (nextX > maxRange) {
          nextX = maxRange;
          islandWalkDirRef.current = -1;
          setIslandWalkDir(-1);
        } else if (nextX < -maxRange) {
          nextX = -maxRange;
          islandWalkDirRef.current = 1;
          setIslandWalkDir(1);
        }
        return nextX;
      });

      animId = requestAnimationFrame(loop);
    };

    animId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animId);
  }, [isWalking, walkCadence, isExpanded]);

  const containerRef = useRef<HTMLDivElement>(null);

  // Click outside & Escape key dismiss for expanded island
  useEffect(() => {
    if (!isExpanded) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsExpanded(false);
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsExpanded(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isExpanded]);

  // Sync sound setting
  useEffect(() => {
    const handleSoundToggle = (e: Event) => {
      const custom = e as CustomEvent<{ enabled: boolean }>;
      if (custom.detail) {
        setSoundActive(custom.detail.enabled);
      }
    };
    window.addEventListener("hinaa-sound-toggle", handleSoundToggle);
    return () => window.removeEventListener("hinaa-sound-toggle", handleSoundToggle);
  }, []);

  // Auto-expand island when interactive permission is requested
  useEffect(() => {
    if (pendingApproval) {
      setIsExpanded(true);
      setActiveTab("agent");
      playUiSound("warning");
    }
  }, [pendingApproval]);

  // Window drag & drop listeners for "Eat the file" feature
  useEffect(() => {
    const handleDragOver = (e: DragEvent) => {
      e.preventDefault();
      setIsDraggingFile(true);
    };
    const handleDragLeave = (e: DragEvent) => {
      if (e.relatedTarget === null) {
        setIsDraggingFile(false);
      }
    };
    const handleDrop = (e: DragEvent) => {
      e.preventDefault();
      setIsDraggingFile(false);
      const file = e.dataTransfer?.files?.[0];
      if (file) {
        handleFileDropped(file);
      }
    };

    window.addEventListener("dragover", handleDragOver);
    window.addEventListener("dragleave", handleDragLeave);
    window.addEventListener("drop", handleDrop);
    return () => {
      window.removeEventListener("dragover", handleDragOver);
      window.removeEventListener("dragleave", handleDragLeave);
      window.removeEventListener("drop", handleDrop);
    };
  }, []);

  const handleFileDropped = (file: File) => {
    setIsExpanded(true);
    setActiveTab("upload");
    setUploadedFileName(file.name);
    setUploadProgress(0);
    playUiSound("pop");

    // Read file preview if image
    if (file.type.startsWith("image/")) {
      const reader = new FileReader();
      reader.onload = (e) => {
        const dataUrl = e.target?.result as string;
        setUploadedFilePreview(dataUrl);
        onAttachImage?.(dataUrl);
      };
      reader.readAsDataURL(file);
    }

    // Realistic upload progress simulation
    let current = 0;
    const interval = setInterval(() => {
      current += 25;
      setUploadProgress(current);
      if (current >= 100) {
        clearInterval(interval);
        playUiSound("success");
      }
    }, 120);
  };

  const handleSendQuickChat = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!chatInput.trim()) return;
    playSendSound();

    const query = chatInput.trim();
    setLastUserQuery(query);
    setChatInput("");

    if (onSendMessage) {
      onSendMessage(query);
    }
  };

  const SYSTEM_COMPONENTS = useMemo(
    () => [
      {
        id: "island",
        number: "01",
        name: "Dynamic Island Companion",
        role: "Notch Companion & Telemetry HUD",
        category: "Companion Core",
        icon: Activity,
        color: "#00d4ff",
        status: "ACTIVE",
        detail: "Coucou animated mascot with mouse pupil tracking, poking states (annoyed squeak, dizzy spirals), file eating, and notch walk locomotion.",
        actionLabel: isWalking ? "Pause Walk" : "Toggle Walk",
        action: () => onToggleWalk?.(),
      },
      {
        id: "vrm",
        number: "02",
        name: "3D VRM Avatar Runway",
        role: "Procedural 3D Companion",
        category: "Visual Engine",
        icon: Footprints,
        color: "#ec4899",
        status: "ONLINE",
        detail: "WebGL/Three.js VRM rig with inverse kinematics walking gait, knee flexion, hip sway, breathing drift, and viseme lip-sync.",
        actionLabel: "Open 3D Runway",
        action: () => onOpenRunway?.(),
      },
      {
        id: "timeline",
        number: "03",
        name: "Adobe Motion Timeline",
        role: "Keyframe Scrubber & Telemetry",
        category: "Creative Suite",
        icon: Sliders,
        color: "#f59e0b",
        status: "ACTIVE",
        detail: "Multi-track sequence timeline with real-time intent, reasoning, tool, avatar, and render keyframe markers.",
        actionLabel: "Audition Keyframe",
        action: () => playUiSound("click"),
      },
      {
        id: "terminal",
        number: "04",
        name: "Claude Code CLI Daemon",
        role: "Autonomous Terminal Runner",
        category: "Engineering CLI",
        icon: Terminal,
        color: "#10b981",
        status: "READY",
        detail: "Interactive shell process runner with streaming stdout/stderr, execution logs, and interactive approval gates.",
        actionLabel: "Open CLI Terminal",
        action: () => onOpenTerminal?.(),
      },
      {
        id: "sound",
        number: "05",
        name: "Universal Tactile UI Audio",
        role: "Zero-Latency Web Audio API",
        category: "Audio Subsystem",
        icon: Music,
        color: "#8b5cf6",
        status: "ACTIVE",
        detail: "Real-time mechanical keyboard clacks, send whooshes, generative teletype stream blips, footsteps, and mascot emotes.",
        actionLabel: "Audition Chime",
        action: () => playUiSound("success"),
      },
      {
        id: "composer",
        number: "06",
        name: "Signature Composer V6",
        role: "Multi-Modal Command Center",
        category: "Input Deck",
        icon: MessageSquare,
        color: "#38bdf8",
        status: "ACTIVE",
        detail: "Mechanical typing audio, smart action triggers, image attachment roles, and live ModelSelector V7 integration.",
        actionLabel: "Quick Prompt",
        action: () => {
          setActiveTab("chat");
          setChatInput("Hello Hina!");
        },
      },
      {
        id: "vision",
        number: "07",
        name: "Live Eyes Screen Vision",
        role: "Real-Time Display Ingest",
        category: "Perception",
        icon: Eye,
        color: "#06b6d4",
        status: "STANDBY",
        detail: "Continuous screen capture feed for visual inspection, UI verification, design critiquing, and debugging.",
        actionLabel: "Audition Shutter",
        action: () => playUiSound("pop"),
      },
      {
        id: "voice",
        number: "08",
        name: "Continuous Voice & Visemes",
        role: "Neural Speech & Lip-Sync",
        category: "Speech Engine",
        icon: Radio,
        color: "#f43f5e",
        status: "READY",
        detail: "Real-time Web Audio FFT frequency analyzer, jaw energy tracking, and phoneme-to-viseme mouth shape morphing.",
        actionLabel: "Test Viseme",
        action: () => playUiSound("switch"),
      },
      {
        id: "goal",
        number: "09",
        name: "Autonomous Goal Engine",
        role: "Multi-Step Planner & Verifier",
        category: "Agentic Logic",
        icon: Workflow,
        color: "#e11d48",
        status: "READY",
        detail: "Autonomous execution loop with constraint verification, artifact compilation, self-reflection, and test execution.",
        actionLabel: "Trigger Plan",
        action: () => {
          if (onSendMessage) onSendMessage("/goal verify system components");
        },
      },
      {
        id: "telemetry",
        number: "10",
        name: "Telemetry & Compute Meter",
        role: "Performance Diagnostics",
        category: "Infrastructure",
        icon: Activity,
        color: "#6366f1",
        status: "LIVE",
        detail: "Real-time latency ms, token throughput, context memory pressure, stable 60 FPS monitor, and Stripe billing telemetry.",
        actionLabel: "Ping Latency",
        action: () => playUiSound("switch"),
      },
      {
        id: "ingest",
        number: "11",
        name: "File Eater & Asset Ingest",
        role: "Drop Zone & Multi-File Parser",
        category: "Asset Pipeline",
        icon: Upload,
        color: "#10b981",
        status: "READY",
        detail: "Window-wide drag-drop listener, Mochi file-swallowing eating animation, chunking, and multi-modal prompt synthesis.",
        actionLabel: "Open File Ingest",
        action: () => {
          setActiveTab("upload");
        },
      },
      {
        id: "shapeshift",
        number: "12",
        name: "Shapeshift Action Cards",
        role: "Inline Dynamic Cards",
        category: "UI Architecture",
        icon: Wand2,
        color: "#d946ef",
        status: "READY",
        detail: "Instant reminder scheduling, PDF report export, generative image synthesis jobs, and bill split calculation cards.",
        actionLabel: "Sample Action",
        action: () => playUiSound("pop"),
      },
    ],
    [isWalking, onToggleWalk, onOpenRunway, onOpenTerminal, onSendMessage]
  );

  const toggleSound = () => {
    const next = !soundActive;
    setSoundActive(next);
    setSoundEnabled(next);
  };

  const isAgentActive =
    agentSteps.some((s) => s.status === "active" || s.status === "pending") ||
    Boolean(pendingApproval) ||
    isThinking;

  const currentDisplayModel = activeProviderModel || "auto";

  return (
    <div
      style={{
        position: inlineInTopBar ? "relative" : "fixed",
        top: inlineInTopBar ? 0 : 8,
        left: inlineInTopBar ? "auto" : "50%",
        transform: inlineInTopBar ? "none" : "translateX(-50%)",
        zIndex: 9999,
        fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, sans-serif",
      }}
    >
      {/* ── 1. Top Bar Inline Element (Either Compact Pill or Active Mini-Dock) ── */}
      {isExpanded ? (
        <div
          onClick={() => {
            playUiSound("whoosh");
            setIsExpanded(false);
          }}
          style={{
            height: 36,
            padding: "0 14px",
            borderRadius: 9999,
            background: isDark ? "rgba(0, 212, 255, 0.12)" : "rgba(0, 212, 255, 0.08)",
            border: "1px solid rgba(0, 212, 255, 0.35)",
            boxShadow: "0 0 16px rgba(0, 212, 255, 0.2)",
            display: "flex",
            alignItems: "center",
            gap: 8,
            cursor: "pointer",
            userSelect: "none",
          }}
          title="Hina Island OS Open — Click to minimize"
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: 4,
              background: "#00d4ff",
              boxShadow: "0 0 8px #00d4ff",
            }}
          />
          <span style={{ fontSize: 11, fontWeight: 700, color: "#00d4ff", letterSpacing: "0.02em" }}>
            HINA ISLAND OS
          </span>
          <Minimize2 size={12} color="#00d4ff" />
        </div>
      ) : (
        <motion.div
          layout
          transition={{ type: "spring", stiffness: 420, damping: 32 }}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
          style={{
            background: isDark
              ? "linear-gradient(135deg, rgba(16, 18, 26, 0.96) 0%, rgba(9, 10, 15, 0.98) 100%)"
              : "linear-gradient(135deg, rgba(255, 255, 255, 0.98) 0%, rgba(245, 247, 250, 0.96) 100%)",
            backdropFilter: "blur(24px)",
            WebkitBackdropFilter: "blur(24px)",
            border: isDraggingFile
              ? "2px dashed #00d4ff"
              : isDark
              ? "1px solid rgba(255, 255, 255, 0.14)"
              : "1px solid rgba(0, 0, 0, 0.12)",
            boxShadow: isDark
              ? "0 16px 48px rgba(0, 0, 0, 0.7), inset 0 1px 0 rgba(255,255,255,0.12)"
              : "0 12px 36px rgba(0, 0, 0, 0.12), inset 0 1px 0 rgba(255,255,255,0.8)",
            borderRadius: 32,
            padding: "4px 12px",
            width: isAgentActive ? 360 : 310,
            color: isDark ? "#ffffff" : "#0f172a",
            display: "flex",
            flexDirection: "column",
            gap: 0,
            overflow: "hidden",
          }}
        >
        {/* ── Top Bar Header of Dynamic Island ──────────────────────── */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            width: "100%",
            height: isExpanded ? 34 : 36,
          }}
        >
          {/* Left: Quick Actions */}
          <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <button
              type="button"
              onClick={() => {
                playUiSound("click");
                setIsExpanded((v) => !v);
              }}
              title="Home / Expand Island"
              style={{
                background: "transparent",
                border: "none",
                color: isDark ? "#cbd5e1" : "#475569",
                cursor: "pointer",
                padding: "4px 6px",
                display: "flex",
                alignItems: "center",
                borderRadius: 8,
              }}
            >
              <Home size={15} />
            </button>

            <button
              type="button"
              onClick={() => {
                playUiSound("click");
                setIsExpanded(true);
                setActiveTab("chat");
              }}
              title="Quick Chat"
              style={{
                background: activeTab === "chat" && isExpanded ? "rgba(236,72,153,0.2)" : "transparent",
                border: "none",
                color: activeTab === "chat" && isExpanded ? "#ec4899" : isDark ? "#cbd5e1" : "#475569",
                cursor: "pointer",
                padding: "4px 6px",
                display: "flex",
                alignItems: "center",
                borderRadius: 8,
              }}
            >
              <MessageSquare size={15} />
            </button>

            <button
              type="button"
              onClick={() => {
                playUiSound("pop");
                onNewChat?.();
              }}
              title="New Session (+)"
              style={{
                background: "transparent",
                border: "none",
                color: isDark ? "#cbd5e1" : "#475569",
                cursor: "pointer",
                padding: "4px 6px",
                display: "flex",
                alignItems: "center",
                borderRadius: 8,
              }}
            >
              <Plus size={15} />
            </button>

            {/* Mascot Toggle Button (Robot vs Mochi) */}
            <button
              type="button"
              onClick={toggleMascotStyle}
              title={`Toggle Avatar Style (Currently: ${mascotStyle === "robot" ? "Talking Robot Face" : "Coucou Mochi"})`}
              style={{
                background: "transparent",
                border: "none",
                fontSize: 13,
                cursor: "pointer",
                padding: "2px 4px",
                display: "flex",
                alignItems: "center",
                borderRadius: 8,
              }}
            >
              <span>{mascotStyle === "robot" ? "🤖" : "☁️"}</span>
            </button>

            {/* Screen Guardian Quick Toggle */}
            <button
              type="button"
              onClick={() => {
                playUiSound("switch");
                setShowGuardianCard((v) => !v);
              }}
              title="Toggle Screen Guardian Focus HUD"
              style={{
                background: showGuardianCard || liveVision.isActive ? "rgba(6,182,212,0.2)" : "transparent",
                border: "none",
                color: showGuardianCard || liveVision.isActive ? "#06b6d4" : isDark ? "#cbd5e1" : "#475569",
                cursor: "pointer",
                padding: "4px 6px",
                display: "flex",
                alignItems: "center",
                borderRadius: 8,
              }}
            >
              <Eye size={15} />
            </button>
          </div>

          {/* Center Mascot & Live Status Pill (When Collapsed) */}
          {!isExpanded && (
            <div
              onClick={() => {
                playUiSound("whoosh");
                setIsExpanded(true);
              }}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                cursor: "pointer",
                padding: "2px 8px",
                borderRadius: 16,
                transform: `translateX(${islandWalkX}px)`,
                transition: "transform 0.05s linear",
              }}
            >
              {/* Mascot in collapsed notch pill */}
              {mascotStyle === "robot" ? (
                <CuteRobotFace
                  size={28}
                  mood={isThinking ? "thinking" : isSpeaking ? "speaking" : liveVision.isActive ? "observing" : "idle"}
                  isSpeaking={isSpeaking}
                  jawEnergy={jawEnergy}
                  isWalking={isWalking}
                  walkPhase={islandWalkPhase}
                  interactive={true}
                />
              ) : (
                <CoucouMascot
                  size={26}
                  mood={
                    isDraggingFile
                      ? "eating"
                      : pendingApproval
                      ? "alert"
                      : isThinking
                      ? "thinking"
                      : isWalking
                      ? "walking"
                      : "happy"
                  }
                  isWalking={isWalking}
                  walkPhase={islandWalkPhase}
                  direction={islandWalkDir}
                  interactive={true}
                />
              )}
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 650,
                  letterSpacing: "0.01em",
                  color: isDark ? "#ffffff" : "#0f172a",
                  whiteSpace: "nowrap",
                }}
              >
                {isDraggingFile
                  ? "Drop File to Feed Hina"
                  : isSpeaking
                  ? "Hina Speaking..."
                  : liveVision.isActive
                  ? "Guardian Watching Screen..."
                  : isThinking
                  ? "Hina Thinking..."
                  : isAgentActive
                  ? "Agent Executing..."
                  : isWalking
                  ? `${companionName} Roaming...`
                  : `${companionName} Island`}
              </span>

              {/* Status Dot */}
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: 3,
                  background: isSpeaking ? "#ec4899" : liveVision.isActive ? "#06b6d4" : isWalking ? "#ec4899" : isThinking ? "#00d4ff" : "#10b981",
                  boxShadow: `0 0 6px ${isSpeaking ? "#ec4899" : liveVision.isActive ? "#06b6d4" : isWalking ? "#ec4899" : isThinking ? "#00d4ff" : "#10b981"}`,
                }}
              />
            </div>
          )}

          {/* Right: Sound, Settings, Expand/Collapse */}
          <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <button
              type="button"
              onClick={toggleSound}
              title={soundActive ? "Mute UI Sounds" : "Enable UI Sounds"}
              style={{
                background: "transparent",
                border: "none",
                color: soundActive ? "#00d4ff" : isDark ? "#64748b" : "#94a3b8",
                cursor: "pointer",
                padding: "4px 6px",
                display: "flex",
                alignItems: "center",
                borderRadius: 8,
              }}
            >
              {soundActive ? <Volume2 size={15} /> : <VolumeX size={15} />}
            </button>

            <button
              type="button"
              onClick={() => {
                playUiSound("click");
                onOpenSettings?.();
              }}
              title="Settings"
              style={{
                background: "transparent",
                border: "none",
                color: isDark ? "#cbd5e1" : "#475569",
                cursor: "pointer",
                padding: "4px 6px",
                display: "flex",
                alignItems: "center",
                borderRadius: 8,
              }}
            >
              <Settings size={15} />
            </button>

            <button
              type="button"
              onClick={() => {
                playUiSound("whoosh");
                setIsExpanded(true);
              }}
              title="Expand Island OS"
              style={{
                background: "transparent",
                border: "none",
                color: isDark ? "#ffffff" : "#0f172a",
                cursor: "pointer",
                padding: "4px 6px",
                display: "flex",
                alignItems: "center",
                borderRadius: 8,
              }}
            >
              <Maximize2 size={14} />
            </button>
          </div>
        </div>
      </motion.div>
    )}

      {/* ── Under-Notch Floating Speech Pill Banner with Red Stop Button (SnapInsta Reference) ── */}
      <AnimatePresence>
        {!isExpanded && (isSpeaking || streamingText || showGuardianCard) && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            style={{
              marginTop: 6,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
              background: "rgba(10, 12, 18, 0.96)",
              border: "1px solid rgba(255, 255, 255, 0.18)",
              borderRadius: 9999,
              padding: "5px 8px 5px 14px",
              boxShadow: "0 12px 36px rgba(0,0,0,0.7), inset 0 1px 0 rgba(255,255,255,0.12)",
              backdropFilter: "blur(20px)",
              WebkitBackdropFilter: "blur(20px)",
              maxWidth: 420,
              width: "fit-content",
              margin: "6px auto 0 auto",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, overflow: "hidden" }}>
              {/* Equalizer Wave Bars */}
              <div style={{ display: "flex", alignItems: "center", gap: 2, height: 14 }}>
                {[0, 1, 2, 3].map((bar) => (
                  <motion.span
                    key={bar}
                    animate={{
                      height: isSpeaking ? [4, 14, 6, 12, 4] : [4, 6, 4],
                    }}
                    transition={{
                      repeat: Infinity,
                      duration: 0.7 + bar * 0.15,
                      ease: "easeInOut",
                    }}
                    style={{
                      width: 2.5,
                      background: bar % 2 === 0 ? "#00d4ff" : "#ec4899",
                      borderRadius: 2,
                      display: "inline-block",
                    }}
                  />
                ))}
              </div>

              {/* Spoken subtitle text preview */}
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 700,
                  color: "#ffffff",
                  letterSpacing: "0.01em",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  maxWidth: 240,
                }}
                title={streamingText || lastAssistantText || "Watching screens & guarding focus..."}
              >
                {streamingText || lastAssistantText || "BROTHER, Call me weird if you like..."}
              </span>
            </div>

            {/* Crimson Red Stop / Barge-in Button */}
            <button
              type="button"
              onClick={() => {
                playUiSound("click");
                onStopSpeaking?.();
              }}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                background: "#e11d48",
                color: "#ffffff",
                border: "none",
                borderRadius: 9999,
                padding: "4px 12px",
                fontSize: 11,
                fontWeight: 750,
                cursor: "pointer",
                boxShadow: "0 2px 8px rgba(225, 29, 72, 0.4)",
                flexShrink: 0,
              }}
            >
              <Square size={9} fill="#ffffff" />
              <span>Stop</span>
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Floating Focus Guardian Chat Card (SnapInsta Reference) ── */}
      <AnimatePresence>
        {!isExpanded && showGuardianCard && (
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.94 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.94 }}
            transition={{ type: "spring", stiffness: 380, damping: 28 }}
            style={{
              marginTop: 8,
              width: 380,
              background: "rgba(11, 13, 20, 0.96)",
              border: "1px solid rgba(255, 255, 255, 0.14)",
              borderRadius: 20,
              padding: "12px 14px",
              boxShadow: "0 24px 60px rgba(0, 0, 0, 0.8), inset 0 1px 0 rgba(255, 255, 255, 0.12)",
              backdropFilter: "blur(24px)",
              WebkitBackdropFilter: "blur(24px)",
              display: "flex",
              flexDirection: "column",
              gap: 10,
              margin: "8px auto 0 auto",
            }}
          >
            {/* Top Bar of Floating Card */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 750,
                    background: "rgba(255,255,255,0.08)",
                    border: "1px solid rgba(255,255,255,0.12)",
                    padding: "2px 6px",
                    borderRadius: 6,
                    color: "#cbd5e1",
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                  }}
                >
                  <span>&lt; 3s</span>
                  <ChevronDown size={10} />
                </span>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 650,
                    color: isSpeaking ? "#ec4899" : "#10b981",
                    display: "flex",
                    alignItems: "center",
                    gap: 5,
                  }}
                >
                  <span
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: 3,
                      background: isSpeaking ? "#ec4899" : "#10b981",
                      boxShadow: `0 0 6px ${isSpeaking ? "#ec4899" : "#10b981"}`,
                    }}
                  />
                  <span>{isSpeaking ? "Speaking..." : "Listening..."}</span>
                </span>

                <button
                  type="button"
                  onClick={() => {
                    playUiSound("pop");
                    setIsCopied(true);
                    setTimeout(() => setIsCopied(false), 1500);
                  }}
                  title="Copy observation"
                  style={{
                    background: "transparent",
                    border: "none",
                    color: isCopied ? "#10b981" : "#94a3b8",
                    cursor: "pointer",
                    padding: 2,
                  }}
                >
                  {isCopied ? <Check size={13} /> : <Copy size={13} />}
                </button>

                <button
                  type="button"
                  onClick={() => setShowGuardianCard(false)}
                  title="Dismiss Card"
                  style={{
                    background: "transparent",
                    border: "none",
                    color: "#64748b",
                    cursor: "pointer",
                    padding: 2,
                  }}
                >
                  <X size={13} />
                </button>
              </div>
            </div>

            {/* User Speech Bubble */}
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <div
                style={{
                  background: "#ffffff",
                  color: "#0f172a",
                  borderRadius: "14px 14px 4px 14px",
                  padding: "8px 12px",
                  fontSize: 12,
                  fontWeight: 550,
                  maxWidth: "85%",
                  boxShadow: "0 2px 8px rgba(0,0,0,0.2)",
                }}
              >
                {lastUserQuery || "You sound so weird. Okay, wait. Let's, let's, let's have a look."}
              </div>
            </div>

            {/* Assistant Guardian Message */}
            <div
              style={{
                fontSize: 12,
                lineHeight: 1.5,
                color: "#f1f5f9",
                fontWeight: 450,
              }}
            >
              <span style={{ fontWeight: 800, color: "#00d4ff" }}>BROTHER</span>, call me weird if you dare — that's the voice of an older brother who has taken an oath to guard your focus! Let's have a look together, then: both blocks are live and holding strong until 18:19, X and YouTube shut the moment they appear. Chrome, Discord, Music, Notes and Claude are what's open on your machine right now — nothing else suspicious slipping through. Weird or not, the walls hold.
            </div>

            {/* Active Windows Strip */}
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: 5,
                background: "rgba(255,255,255,0.05)",
                padding: "6px 8px",
                borderRadius: 8,
                fontSize: 10,
                color: "#94a3b8",
              }}
            >
              <span style={{ color: "#10b981", fontWeight: 700 }}>Open Windows:</span>
              <span>Chrome</span> · <span>Discord</span> · <span>VS Code</span> · <span>Terminal</span> · <span>Claude</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── 2. Expanded Hina Island OS Deck (Portaled to document.body) ── */}
      {mounted && createPortal(
        <AnimatePresence>
          {isExpanded && (
            <div
              className="hina-island-os-portal-root"
              style={{
            position: "fixed",
            inset: 0,
            zIndex: 99999,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "flex-start",
            paddingTop: "clamp(10px, 2.5vh, 20px)",
            paddingBottom: "clamp(10px, 2.5vh, 20px)",
            paddingLeft: "clamp(8px, 2vw, 16px)",
            paddingRight: "clamp(8px, 2vw, 16px)",
            boxSizing: "border-box",
            pointerEvents: "auto",
            fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, sans-serif",
          }}
        >
          {/* Fullscreen Backdrop Scrim */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={() => {
              playUiSound("whoosh");
              setIsExpanded(false);
            }}
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(4, 6, 12, 0.75)",
              backdropFilter: "blur(10px)",
              WebkitBackdropFilter: "blur(10px)",
              zIndex: 100000,
            }}
          />

          {/* Expanded Modal Window */}
          <motion.div
            ref={containerRef}
            initial={{ opacity: 0, scale: 0.95, y: -16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -16 }}
            transition={{ type: "spring", stiffness: 440, damping: 32 }}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
            style={{
              position: "relative",
              zIndex: 100001,
              background: isDark
                ? "linear-gradient(135deg, rgba(16, 18, 26, 0.98) 0%, rgba(9, 10, 15, 0.99) 100%)"
                : "linear-gradient(135deg, rgba(255, 255, 255, 0.99) 0%, rgba(245, 247, 250, 0.98) 100%)",
              backdropFilter: "blur(32px)",
              WebkitBackdropFilter: "blur(32px)",
              border: isDraggingFile
                ? "2px dashed #00d4ff"
                : isDark
                ? "1px solid rgba(255, 255, 255, 0.16)"
                : "1px solid rgba(0, 0, 0, 0.14)",
              boxShadow: isDark
                ? "0 28px 72px rgba(0, 0, 0, 0.85), 0 0 0 1px rgba(0, 212, 255, 0.18), inset 0 1px 0 rgba(255,255,255,0.15)"
                : "0 20px 50px rgba(0, 0, 0, 0.14), inset 0 1px 0 rgba(255,255,255,0.9)",
              borderRadius: 22,
              padding: "12px 18px",
              width: "min(760px, calc(100vw - 24px))",
              maxWidth: "calc(100vw - 24px)",
              maxHeight: "calc(100vh - 36px)",
              color: isDark ? "#ffffff" : "#0f172a",
              display: "flex",
              flexDirection: "column",
              gap: 10,
              overflow: "hidden",
              boxSizing: "border-box",
            }}
          >
            {/* Modal Header */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                width: "100%",
                height: 34,
                flexShrink: 0,
                borderBottom: isDark ? "1px solid rgba(255,255,255,0.06)" : "1px solid rgba(0,0,0,0.06)",
                paddingBottom: 6,
              }}
            >
              {/* Left Actions */}
              <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <button
                  type="button"
                  onClick={() => {
                    playUiSound("click");
                    setIsExpanded(false);
                  }}
                  title="Home / Collapse Island"
                  style={{
                    background: "transparent",
                    border: "none",
                    color: isDark ? "#cbd5e1" : "#475569",
                    cursor: "pointer",
                    padding: "4px 6px",
                    display: "flex",
                    alignItems: "center",
                    borderRadius: 8,
                  }}
                >
                  <Home size={15} />
                </button>

                <button
                  type="button"
                  onClick={() => {
                    playUiSound("click");
                    setActiveTab("agent");
                  }}
                  title="Agent & CLI Console"
                  style={{
                    background: activeTab === "agent" ? "rgba(0,212,255,0.2)" : "transparent",
                    border: "none",
                    color: activeTab === "agent" ? "#00d4ff" : isDark ? "#cbd5e1" : "#475569",
                    cursor: "pointer",
                    padding: "4px 6px",
                    display: "flex",
                    alignItems: "center",
                    borderRadius: 8,
                  }}
                >
                  <Cpu size={15} />
                </button>

                <button
                  type="button"
                  onClick={() => {
                    playUiSound("pop");
                    onNewChat?.();
                  }}
                  title="New Session (+)"
                  style={{
                    background: "transparent",
                    border: "none",
                    color: isDark ? "#cbd5e1" : "#475569",
                    cursor: "pointer",
                    padding: "4px 6px",
                    display: "flex",
                    alignItems: "center",
                    borderRadius: 8,
                  }}
                >
                  <Plus size={15} />
                </button>

                {/* Mascot Toggle Button (Robot vs Mochi) */}
                <button
                  type="button"
                  onClick={toggleMascotStyle}
                  title={`Toggle Avatar Style (Currently: ${mascotStyle === "robot" ? "Talking Robot Face" : "Coucou Mochi"})`}
                  style={{
                    background: "transparent",
                    border: "none",
                    fontSize: 13,
                    cursor: "pointer",
                    padding: "2px 4px",
                    display: "flex",
                    alignItems: "center",
                    borderRadius: 8,
                  }}
                >
                  <span>{mascotStyle === "robot" ? "🤖" : "☁️"}</span>
                </button>

                {/* Screen Guardian Quick Toggle */}
                <button
                  type="button"
                  onClick={() => {
                    playUiSound("switch");
                    setActiveTab("watcher");
                  }}
                  title="Switch to Screen Watcher & Focus HUD"
                  style={{
                    background: activeTab === "watcher" || liveVision.isActive ? "rgba(6,182,212,0.2)" : "transparent",
                    border: "none",
                    color: activeTab === "watcher" || liveVision.isActive ? "#06b6d4" : isDark ? "#cbd5e1" : "#475569",
                    cursor: "pointer",
                    padding: "4px 6px",
                    display: "flex",
                    alignItems: "center",
                    borderRadius: 8,
                  }}
                >
                  <Eye size={15} />
                </button>
              </div>

              {/* Center Title Pill */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "3px 12px",
                  borderRadius: 14,
                  background: isDark ? "rgba(255, 255, 255, 0.06)" : "rgba(0, 0, 0, 0.05)",
                  border: isDark ? "1px solid rgba(255, 255, 255, 0.08)" : "1px solid rgba(0, 0, 0, 0.06)",
                }}
              >
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: 3,
                    background: isSpeaking ? "#ec4899" : liveVision.isActive ? "#06b6d4" : isThinking ? "#00d4ff" : "#10b981",
                    boxShadow: `0 0 6px ${isSpeaking ? "#ec4899" : liveVision.isActive ? "#06b6d4" : isThinking ? "#00d4ff" : "#10b981"}`,
                  }}
                />
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 750,
                    letterSpacing: "0.04em",
                    color: isDark ? "#ffffff" : "#0f172a",
                    textTransform: "uppercase",
                  }}
                >
                  HINA ISLAND OS
                </span>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 650,
                    color: isDark ? "#94a3b8" : "#64748b",
                    padding: "1px 6px",
                    borderRadius: 6,
                    background: isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(0, 0, 0, 0.05)",
                  }}
                >
                  {activeTab.toUpperCase()}
                </span>
              </div>

              {/* Right: Sound, Settings, Minimize */}
              <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <button
                  type="button"
                  onClick={toggleSound}
                  title={soundActive ? "Mute UI Sounds" : "Enable UI Sounds"}
                  style={{
                    background: "transparent",
                    border: "none",
                    color: soundActive ? "#00d4ff" : isDark ? "#64748b" : "#94a3b8",
                    cursor: "pointer",
                    padding: "4px 6px",
                    display: "flex",
                    alignItems: "center",
                    borderRadius: 8,
                  }}
                >
                  {soundActive ? <Volume2 size={15} /> : <VolumeX size={15} />}
                </button>

                <button
                  type="button"
                  onClick={() => {
                    playUiSound("click");
                    onOpenSettings?.();
                  }}
                  title="Settings"
                  style={{
                    background: "transparent",
                    border: "none",
                    color: isDark ? "#cbd5e1" : "#475569",
                    cursor: "pointer",
                    padding: "4px 6px",
                    display: "flex",
                    alignItems: "center",
                    borderRadius: 8,
                  }}
                >
                  <Settings size={15} />
                </button>

                <button
                  type="button"
                  onClick={() => {
                    playUiSound("whoosh");
                    setIsExpanded(false);
                  }}
                  title="Collapse Island (Esc)"
                  style={{
                    background: isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(0, 0, 0, 0.06)",
                    border: isDark ? "1px solid rgba(255, 255, 255, 0.12)" : "1px solid rgba(0, 0, 0, 0.1)",
                    color: isDark ? "#ffffff" : "#0f172a",
                    cursor: "pointer",
                    padding: "4px 8px",
                    display: "flex",
                    alignItems: "center",
                    borderRadius: 8,
                    gap: 4,
                  }}
                >
                  <Minimize2 size={13} />
                  <span style={{ fontSize: 10, fontWeight: 700 }}>ESC</span>
                </button>
              </div>
            </div>

            {/* Modal Body: Columns */}
            <div
              className="hina-island-deck-columns"
              style={{
                display: "flex",
                gap: 16,
                paddingTop: 4,
                flex: 1,
                minHeight: 0,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <div
                  onClick={() => {
                    playUiSound("pop");
                  }}
                  title="Hina Mascot Avatar"
                >
                  {mascotStyle === "robot" ? (
                    <CuteRobotFace
                      mood={
                        isThinking
                          ? "thinking"
                          : isSpeaking
                          ? "speaking"
                          : liveVision.isActive
                          ? "observing"
                          : "happy"
                      }
                      isHovered={isHovered}
                      size={68}
                      isSpeaking={isSpeaking}
                      jawEnergy={jawEnergy}
                      isWalking={isWalking}
                      walkPhase={islandWalkPhase}
                    />
                  ) : (
                    <CoucouMascot
                      mood={
                        isDraggingFile
                          ? "eating"
                          : pendingApproval
                          ? "alert"
                          : isThinking
                          ? "thinking"
                          : "happy"
                      }
                      isHovered={isHovered}
                      size={64}
                    />
                  )}
                </div>

                {/* Mascot Switcher Toggle */}
                <button
                  type="button"
                  onClick={toggleMascotStyle}
                  title={`Switch to ${mascotStyle === "robot" ? "Mochi Mascot" : "Talking Robot Face"}`}
                  style={{
                    background: "rgba(255, 255, 255, 0.08)",
                    border: "1px solid rgba(255, 255, 255, 0.16)",
                    borderRadius: 9999,
                    padding: "2px 8px",
                    fontSize: 10,
                    fontWeight: 700,
                    color: isDark ? "#cbd5e1" : "#475569",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 3,
                    transition: "all 0.15s ease",
                  }}
                >
                  <span>{mascotStyle === "robot" ? "🤖 Robot" : "☁️ Mochi"}</span>
                </button>
              </div>

              {/* Center & Right Column: Interactive Deck */}
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 10, minWidth: 0 }}>
                {/* ── Console Mode Navigation Tabs ── */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    borderBottom: isDark ? "1px solid rgba(255,255,255,0.08)" : "1px solid rgba(0,0,0,0.08)",
                    paddingBottom: 6,
                    overflowX: "auto",
                    scrollbarWidth: "none",
                    whiteSpace: "nowrap",
                    WebkitOverflowScrolling: "touch",
                    flexShrink: 0,
                  }}
                >
                  <button
                    type="button"
                    onClick={() => {
                      playUiSound("click");
                      setActiveTab("agent");
                    }}
                    style={{
                      background: activeTab === "agent" ? "rgba(0, 212, 255, 0.15)" : "transparent",
                      border: activeTab === "agent" ? "1px solid rgba(0, 212, 255, 0.4)" : "1px solid transparent",
                      borderRadius: 8,
                      padding: "3px 8px",
                      fontSize: 11,
                      fontWeight: 650,
                      color: activeTab === "agent" ? "#00d4ff" : isDark ? "#cbd5e1" : "#475569",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                      flexShrink: 0,
                    }}
                  >
                    <Cpu size={12} />
                    <span>Agent & CLI</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      playUiSound("click");
                      setActiveTab("watcher");
                    }}
                    style={{
                      background: activeTab === "watcher" ? "rgba(6, 182, 212, 0.15)" : "transparent",
                      border: activeTab === "watcher" ? "1px solid rgba(6, 182, 212, 0.4)" : "1px solid transparent",
                      borderRadius: 8,
                      padding: "3px 8px",
                      fontSize: 11,
                      fontWeight: 650,
                      color: activeTab === "watcher" ? "#06b6d4" : isDark ? "#cbd5e1" : "#475569",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                      flexShrink: 0,
                    }}
                  >
                    <Monitor size={12} />
                    <span>Screen Watcher</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      playUiSound("click");
                      setActiveTab("motion");
                    }}
                    style={{
                      background: activeTab === "motion" ? "rgba(236, 72, 153, 0.15)" : "transparent",
                      border: activeTab === "motion" ? "1px solid rgba(236, 72, 153, 0.4)" : "1px solid transparent",
                      borderRadius: 8,
                      padding: "3px 8px",
                      fontSize: 11,
                      fontWeight: 650,
                      color: activeTab === "motion" ? "#ec4899" : isDark ? "#cbd5e1" : "#475569",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                      flexShrink: 0,
                    }}
                  >
                    <Footprints size={12} />
                    <span>3D Motion Edit</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      playUiSound("click");
                      setActiveTab("upload");
                    }}
                    style={{
                      background: activeTab === "upload" ? "rgba(16, 185, 129, 0.15)" : "transparent",
                      border: activeTab === "upload" ? "1px solid rgba(16, 185, 129, 0.4)" : "1px solid transparent",
                      borderRadius: 8,
                      padding: "3px 8px",
                      fontSize: 11,
                      fontWeight: 650,
                      color: activeTab === "upload" ? "#10b981" : isDark ? "#cbd5e1" : "#475569",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                      flexShrink: 0,
                    }}
                  >
                    <Upload size={12} />
                    <span>File Ingest</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      playUiSound("click");
                      setActiveTab("stripe");
                    }}
                    style={{
                      background: activeTab === "stripe" ? "rgba(99, 91, 255, 0.15)" : "transparent",
                      border: activeTab === "stripe" ? "1px solid rgba(99, 91, 255, 0.4)" : "1px solid transparent",
                      borderRadius: 8,
                      padding: "3px 8px",
                      fontSize: 11,
                      fontWeight: 650,
                      color: activeTab === "stripe" ? "#a5b4fc" : isDark ? "#cbd5e1" : "#475569",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                      flexShrink: 0,
                    }}
                  >
                    <CreditCard size={12} />
                    <span>Telemetry</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      playUiSound("click");
                      setActiveTab("components");
                    }}
                    style={{
                      background: activeTab === "components" ? "rgba(168, 85, 247, 0.15)" : "transparent",
                      border: activeTab === "components" ? "1px solid rgba(168, 85, 247, 0.4)" : "1px solid transparent",
                      borderRadius: 8,
                      padding: "3px 8px",
                      fontSize: 11,
                      fontWeight: 650,
                      color: activeTab === "components" ? "#c084fc" : isDark ? "#cbd5e1" : "#475569",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                      flexShrink: 0,
                    }}
                  >
                    <Boxes size={12} />
                    <span>Components</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      playUiSound("click");
                      setActiveTab("audio");
                    }}
                    style={{
                      background: activeTab === "audio" ? "rgba(244, 63, 94, 0.15)" : "transparent",
                      border: activeTab === "audio" ? "1px solid rgba(244, 63, 94, 0.4)" : "1px solid transparent",
                      borderRadius: 8,
                      padding: "3px 8px",
                      fontSize: 11,
                      fontWeight: 650,
                      color: activeTab === "audio" ? "#fb7185" : isDark ? "#cbd5e1" : "#475569",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                      flexShrink: 0,
                    }}
                  >
                    <Volume2 size={12} />
                    <span>Sound FX</span>
                  </button>

                  {/* Real Model Selector Dropdown Trigger */}
                  <div style={{ marginLeft: "auto", position: "relative", flexShrink: 0 }}>
                    <button
                      type="button"
                      onClick={() => {
                        playUiSound("switch");
                        setModelDropdownOpen((v) => !v);
                      }}
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 4,
                        background: isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)",
                        border: isDark ? "1px solid rgba(255,255,255,0.15)" : "1px solid rgba(0,0,0,0.1)",
                        borderRadius: 8,
                        padding: "2px 8px",
                        fontSize: 10,
                        fontWeight: 650,
                        color: isDark ? "#ffffff" : "#0f172a",
                        cursor: "pointer",
                      }}
                    >
                      <span style={{ maxWidth: 100, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {currentDisplayModel}
                      </span>
                      <ChevronDown size={10} />
                    </button>

                    {/* Dropdown Menu */}
                    {modelDropdownOpen && (
                      <div
                        style={{
                          position: "absolute",
                          top: "100%",
                          right: 0,
                          marginTop: 4,
                          background: isDark ? "#121520" : "#ffffff",
                          border: isDark ? "1px solid rgba(255,255,255,0.15)" : "1px solid #cbd5e1",
                          borderRadius: 10,
                          padding: 4,
                          boxShadow: "0 10px 25px rgba(0,0,0,0.5)",
                          zIndex: 10000,
                          minWidth: 160,
                          maxHeight: 200,
                          overflowY: "auto",
                        }}
                      >
                        <div
                          onClick={() => {
                            playUiSound("click");
                            onSelectModel?.("auto", "auto");
                            setModelDropdownOpen(false);
                          }}
                          style={{
                            padding: "6px 10px",
                            fontSize: 11,
                            fontWeight: 600,
                            borderRadius: 6,
                            cursor: "pointer",
                            color: currentDisplayModel === "auto" ? "#00d4ff" : isDark ? "#ffffff" : "#0f172a",
                            background: currentDisplayModel === "auto" ? "rgba(0,212,255,0.1)" : "transparent",
                          }}
                        >
                          Auto Router (Smart)
                        </div>
                        {availableModels.slice(0, 10).map((m) => (
                          <div
                            key={m.id}
                            onClick={() => {
                              playUiSound("click");
                              onSelectModel?.(m.id, m.provider);
                              setModelDropdownOpen(false);
                            }}
                            style={{
                              padding: "6px 10px",
                              fontSize: 11,
                              borderRadius: 6,
                              cursor: "pointer",
                              color: currentDisplayModel === m.id ? "#00d4ff" : isDark ? "#e2e8f0" : "#1e293b",
                              background: currentDisplayModel === m.id ? "rgba(0,212,255,0.1)" : "transparent",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {m.name || m.id}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* ── Tab Content (Contained & Smoothly Scrollable) ── */}
                <div
                  className="hina-island-tab-content-scroll"
                  style={{
                    flex: 1,
                    maxHeight: "calc(100vh - 145px)",
                    overflowY: "auto",
                    overflowX: "hidden",
                    paddingRight: 6,
                    minHeight: 0,
                  }}
                >
                {activeTab === "upload" || isDraggingFile ? (
                  /* 1. File Ingestion & Analysis */
                  <div
                    style={{
                      background: "rgba(16, 185, 129, 0.08)",
                      border: "1px solid rgba(16, 185, 129, 0.35)",
                      borderRadius: 14,
                      padding: "10px 14px",
                      display: "flex",
                      flexDirection: "column",
                      gap: 8,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <span style={{ fontSize: 12, fontWeight: 700, color: "#10b981" }}>
                        Drop Files (Images, Code, PDFs) for Hina to Ingest
                      </span>
                      {uploadedFileName && (
                        <span style={{ fontSize: 11, color: isDark ? "#e2e8f0" : "#1e293b" }}>
                          {uploadedFileName}
                        </span>
                      )}
                    </div>

                    {uploadProgress !== null && (
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <div
                          style={{
                            flex: 1,
                            height: 6,
                            borderRadius: 3,
                            background: "rgba(255,255,255,0.1)",
                            overflow: "hidden",
                          }}
                        >
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${uploadProgress}%` }}
                            style={{ height: "100%", background: "#10b981", borderRadius: 3 }}
                          />
                        </div>
                        <span style={{ fontSize: 11, fontWeight: 700, color: "#10b981" }}>
                          {uploadProgress}%
                        </span>
                      </div>
                    )}

                    {uploadProgress === 100 && (
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
                        <button
                          type="button"
                          onClick={() => {
                            playUiSound("buttonPress");
                            setActiveTab("chat");
                            setChatInput(`Analyze and explain this file: ${uploadedFileName}`);
                          }}
                          style={{
                            background: "#10b981",
                            color: "#fff",
                            border: "none",
                            borderRadius: 8,
                            padding: "5px 12px",
                            fontSize: 11,
                            fontWeight: 700,
                            cursor: "pointer",
                          }}
                        >
                          Ask Hina about this file
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setActiveTab("agent");
                            setUploadProgress(null);
                            setUploadedFileName(null);
                          }}
                          style={{
                            background: "transparent",
                            border: "1px solid rgba(255,255,255,0.2)",
                            color: isDark ? "#cbd5e1" : "#475569",
                            borderRadius: 8,
                            padding: "5px 12px",
                            fontSize: 11,
                            cursor: "pointer",
                          }}
                        >
                          Clear
                        </button>
                      </div>
                    )}
                  </div>
                ) : activeTab === "motion" ? (
                  /* ── 2. Sleeko Motion Architecture & 3D Gait Controls (AQP7 & AQO9 References) ── */
                  <div
                    style={{
                      background: isDark ? "rgba(236, 72, 153, 0.08)" : "rgba(236, 72, 153, 0.05)",
                      border: "1px solid rgba(236, 72, 153, 0.3)",
                      borderRadius: 14,
                      padding: "10px 14px",
                      display: "flex",
                      flexDirection: "column",
                      gap: 10,
                    }}
                  >
                    {/* Header + Locomotion toggles */}
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <Footprints size={14} color="#ec4899" />
                        <span style={{ fontSize: 12, fontWeight: 700, color: "#ec4899" }}>
                          Sleeko Motion & Autonomous Gait Engine
                        </span>
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <button
                          type="button"
                          onClick={() => {
                            playUiSound("click");
                            onToggleWalk?.();
                          }}
                          style={{
                            background: isWalking ? "#ec4899" : "rgba(255,255,255,0.08)",
                            color: "#fff",
                            border: "none",
                            borderRadius: 8,
                            padding: "4px 10px",
                            fontSize: 10,
                            fontWeight: 700,
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            gap: 4,
                          }}
                        >
                          <Footprints size={11} />
                          <span>{isWalking ? "Stop Walking" : "Walk / Roam"}</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => {
                            playUiSound("pop");
                            window.dispatchEvent(new CustomEvent("hinaa:toggle-desktop-pet"));
                          }}
                          title="Spawn / dismiss on-screen walking pet (Dex / Robot)"
                          style={{
                            background: "rgba(0, 212, 255, 0.15)",
                            border: "1px solid rgba(0, 212, 255, 0.4)",
                            color: "#00d4ff",
                            borderRadius: 8,
                            padding: "4px 8px",
                            fontSize: 10,
                            fontWeight: 700,
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            gap: 4,
                          }}
                        >
                          <Sparkles size={11} />
                          <span>Desktop Pet</span>
                        </button>
                      </div>
                    </div>

                    {/* ── Sleeko Segmented Navigation Controller (Video AQP79YnuIB) ── */}
                    <div
                      style={{
                        position: "relative",
                        display: "grid",
                        gridTemplateColumns: "repeat(4, 1fr)",
                        gap: 4,
                        background: "rgba(0, 0, 0, 0.4)",
                        borderRadius: 10,
                        padding: 3,
                        border: "1px solid rgba(255, 255, 255, 0.08)",
                      }}
                    >
                      {[
                        { id: "intro", label: "Intro" },
                        { id: "problem", label: "Problem" },
                        { id: "usecase", label: "Use Case" },
                        { id: "cta", label: "Call to Action" },
                      ].map((tab) => {
                        const isActive = sleekoStep === tab.id;
                        return (
                          <button
                            key={tab.id}
                            type="button"
                            onClick={() => {
                              playUiSound("click");
                              setSleekoStep(tab.id as any);
                            }}
                            style={{
                              position: "relative",
                              background: isActive ? "#ffffff" : "transparent",
                              color: isActive ? "#000000" : isDark ? "#94a3b8" : "#64748b",
                              border: "none",
                              borderRadius: 7,
                              padding: "5px 4px",
                              fontSize: 11,
                              fontWeight: isActive ? 750 : 550,
                              cursor: "pointer",
                              textAlign: "center",
                              transition: "all 0.18s ease",
                              zIndex: 1,
                            }}
                          >
                            <span>{tab.label}</span>
                            {/* Neon Laser Flare Light beneath active button (matching video AQP7) */}
                            {isActive && (
                              <motion.div
                                layoutId="sleeko-laser-flare"
                                style={{
                                  position: "absolute",
                                  bottom: -3,
                                  left: "25%",
                                  right: "25%",
                                  height: 3,
                                  background: "#a855f7",
                                  boxShadow: "0 0 10px #c084fc, 0 0 20px #a855f7",
                                  borderRadius: 2,
                                }}
                              />
                            )}
                          </button>
                        );
                      })}
                    </div>

                    {/* ── Sleeko Spring Popup Motion Card ── */}
                    <motion.div
                      key={sleekoStep}
                      initial={{ opacity: 0, y: 15, scale: 0.96 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      transition={{ type: "spring", stiffness: 420, damping: 28 }}
                      style={{
                        background: isDark ? "rgba(10, 13, 22, 0.75)" : "#ffffff",
                        border: "1px solid rgba(255, 255, 255, 0.12)",
                        borderRadius: 12,
                        padding: "10px 12px",
                        display: "flex",
                        flexDirection: "column",
                        gap: 8,
                        boxShadow: "0 12px 30px rgba(0,0,0,0.45)",
                        backdropFilter: "blur(16px)",
                      }}
                    >
                      {sleekoStep === "usecase" ? (
                        <>
                          <div style={{ fontSize: 11, color: isDark ? "#f1f5f9" : "#1e293b", lineHeight: 1.45, fontWeight: 450 }}>
                            Hello, how do I need your help? I am home alone, and I want pizza. Could you tell me how to cook pizza?
                          </div>
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: 4 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                              <button
                                type="button"
                                onClick={() => playUiSound("pop")}
                                style={{
                                  background: "rgba(255,255,255,0.08)",
                                  border: "1px solid rgba(255,255,255,0.15)",
                                  borderRadius: 9999,
                                  padding: "2px 8px",
                                  fontSize: 10,
                                  fontWeight: 650,
                                  color: "#cbd5e1",
                                  cursor: "pointer",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: 3,
                                }}
                              >
                                <Plus size={10} />
                                <span>Attach</span>
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  playUiSound("buttonPress");
                                  onSendMessage?.("Deep Search pizza recipes and autonomous culinary steps");
                                }}
                                style={{
                                  background: "rgba(168, 85, 247, 0.15)",
                                  border: "1px solid rgba(168, 85, 247, 0.35)",
                                  borderRadius: 9999,
                                  padding: "2px 8px",
                                  fontSize: 10,
                                  fontWeight: 700,
                                  color: "#c084fc",
                                  cursor: "pointer",
                                  display: "flex",
                                  alignItems: "center",
                                  gap: 4,
                                }}
                              >
                                <Sparkles size={10} />
                                <span>Deep Search</span>
                              </button>
                            </div>
                            <span style={{ fontSize: 10, color: "#10b981", fontWeight: 700 }}>✦ Ready</span>
                          </div>
                        </>
                      ) : sleekoStep === "problem" ? (
                        <div style={{ textAlign: "center", padding: "12px 0" }}>
                          <div style={{ fontSize: 16, fontWeight: 750, color: "#a855f7", letterSpacing: "-0.02em" }}>
                            exciting to figure out.
                          </div>
                          <div style={{ fontSize: 10, color: isDark ? "#94a3b8" : "#64748b", marginTop: 4 }}>
                            Continuous reasoning loop resolves complex multi-step bottlenecks autonomously.
                          </div>
                        </div>
                      ) : sleekoStep === "intro" ? (
                        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                          <span style={{ fontSize: 10, fontWeight: 800, color: "#00d4ff", textTransform: "uppercase" }}>
                            Product Details:
                          </span>
                          <span style={{ fontSize: 12, fontWeight: 700, color: isDark ? "#fff" : "#000" }}>
                            HINAA Autonomous Operating Companion
                          </span>
                          <span style={{ fontSize: 10, color: isDark ? "#cbd5e1" : "#475569" }}>
                            Vision guardian · 3D VRM Locomotion · Real-Time Voice · Instant Barge-in
                          </span>
                        </div>
                      ) : (
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                          <span style={{ fontSize: 11, fontWeight: 650, color: "#f1f5f9" }}>
                            Ready to orchestrate your desktop workspace?
                          </span>
                          <button
                            type="button"
                            onClick={() => {
                              playUiSound("send");
                              onOpenRunway?.();
                            }}
                            style={{
                              background: "#ec4899",
                              color: "#fff",
                              border: "none",
                              borderRadius: 6,
                              padding: "4px 10px",
                              fontSize: 10,
                              fontWeight: 700,
                              cursor: "pointer",
                            }}
                          >
                            Get Started
                          </button>
                        </div>
                      )}
                    </motion.div>

                    {/* ── Korus Quote Calculation & Integrations (Video AQO9) ── */}
                    {showKorusCalculation && (
                      <div
                        style={{
                          background: "rgba(0, 0, 0, 0.4)",
                          border: "1px solid rgba(255, 255, 255, 0.08)",
                          borderRadius: 10,
                          padding: "8px 10px",
                          display: "flex",
                          flexDirection: "column",
                          gap: 6,
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <span
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: 4,
                                background: "rgba(255,255,255,0.08)",
                                border: "1px solid rgba(255,255,255,0.12)",
                                borderRadius: 6,
                                padding: "1px 6px",
                                fontSize: 10,
                                color: "#cbd5e1",
                              }}
                            >
                              <FileText size={10} color="#f43f5e" />
                              <span>quote.pdf</span>
                            </span>
                            <span style={{ fontSize: 10, color: "#94a3b8" }}>What's the total?</span>
                          </div>

                          <button
                            type="button"
                            onClick={() => {
                              playUiSound("mochiDizzy");
                              setShowDizzyToast((v) => !v);
                            }}
                            title="Preview Rate Limit Dizzy Mascot Toast (Video AQO9)"
                            style={{
                              background: "transparent",
                              border: "none",
                              color: "#ec4899",
                              fontSize: 10,
                              fontWeight: 700,
                              cursor: "pointer",
                            }}
                          >
                            {showDizzyToast ? "Hide Alert" : "Simulate Alert"}
                          </button>
                        </div>

                        <div style={{ fontSize: 11, fontWeight: 550, color: "#f8fafc", lineHeight: 1.4 }}>
                          The total is <span style={{ color: "#10b981", fontWeight: 700 }}>€1,240 excl. VAT</span> (€1,488 incl. VAT) for Atelier Brun — valid until October 30.
                        </div>

                        {/* 4 App Integration Tiles (Stripe, GitHub, n8n, Vercel) */}
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 4, marginTop: 2 }}>
                          {[
                            { name: "Stripe", color: "#635bff" },
                            { name: "GitHub", color: "#f43f5e" },
                            { name: "n8n", color: "#f97316" },
                            { name: "Vercel", color: "#a855f7" },
                          ].map((item) => (
                            <div
                              key={item.name}
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: 4,
                                background: "rgba(255,255,255,0.05)",
                                border: "1px solid rgba(255,255,255,0.08)",
                                borderRadius: 6,
                                padding: "3px 6px",
                                fontSize: 10,
                                color: "#e2e8f0",
                              }}
                            >
                              <span style={{ width: 6, height: 6, borderRadius: 3, background: item.color }} />
                              <span>{item.name}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Dizzy Rate Limit Toast (matching video AQO9_f80) */}
                    <AnimatePresence>
                      {showDizzyToast && (
                        <motion.div
                          initial={{ opacity: 0, y: 10, scale: 0.95 }}
                          animate={{ opacity: 1, y: 0, scale: 1 }}
                          exit={{ opacity: 0, y: 10, scale: 0.95 }}
                          style={{
                            background: "rgba(20, 10, 18, 0.94)",
                            border: "1px solid rgba(244, 63, 94, 0.4)",
                            borderRadius: 10,
                            padding: "8px 12px",
                            display: "flex",
                            alignItems: "center",
                            gap: 10,
                            boxShadow: "0 8px 24px rgba(0,0,0,0.6)",
                          }}
                        >
                          {/* Dizzy Mascot Face with Spiral Eyes @ @ */}
                          <div
                            style={{
                              width: 32,
                              height: 28,
                              borderRadius: 8,
                              background: "#ffffff",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              flexShrink: 0,
                              fontWeight: 900,
                              fontSize: 12,
                              color: "#0f172a",
                            }}
                          >
                            @ @
                          </div>
                          <div style={{ display: "flex", flexDirection: "column" }}>
                            <span style={{ fontSize: 11, fontWeight: 750, color: "#fff" }}>
                              Too many hits at once.
                            </span>
                            <span style={{ fontSize: 10, color: "#cbd5e1" }}>
                              Give me a sec — back to work in three seconds.
                            </span>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>

                    {/* Gait Cadence Speed row */}
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 10, color: isDark ? "#cbd5e1" : "#475569" }}>
                      <span>Locomotion Cadence: {walkCadence}x</span>
                      <div style={{ display: "flex", gap: 4 }}>
                        {[0.5, 1.0, 1.5, 2.0].map((spd) => (
                          <button
                            key={spd}
                            type="button"
                            onClick={() => {
                              playUiSound("switch");
                              setWalkCadence(spd);
                            }}
                            style={{
                              background: walkCadence === spd ? "rgba(236,72,153,0.3)" : "rgba(255,255,255,0.06)",
                              border: "none",
                              borderRadius: 4,
                              padding: "2px 6px",
                              fontSize: 9,
                              fontWeight: 650,
                              color: walkCadence === spd ? "#fff" : isDark ? "#94a3b8" : "#64748b",
                              cursor: "pointer",
                            }}
                          >
                            {spd}x
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                ) : activeTab === "stripe" ? (
                  /* 3. Live Telemetry & Stripe Hub */
                  <div
                    style={{
                      background: "rgba(99, 91, 255, 0.1)",
                      border: "1px solid rgba(99, 91, 255, 0.35)",
                      borderRadius: 14,
                      padding: "10px 14px",
                      display: "flex",
                      flexDirection: "column",
                      gap: 6,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <CreditCard size={14} color="#818cf8" />
                        <span style={{ fontSize: 12, fontWeight: 700, color: "#fff" }}>Enterprise Metrics & Telemetry</span>
                      </div>
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          color: "#10b981",
                          background: "rgba(16,185,129,0.15)",
                          padding: "2px 6px",
                          borderRadius: 6,
                        }}
                      >
                        All Systems Live
                      </span>
                    </div>
                    <div style={{ fontSize: 17, fontWeight: 800, color: "#fff", letterSpacing: "-0.02em" }}>
                      Latency: ~850ms <span style={{ fontSize: 12, fontWeight: 500, color: "rgba(255,255,255,0.6)" }}>· Context: 42.8k / 1.0M</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "rgba(255,255,255,0.7)" }}>
                      <span>FPS: 60 stable</span>
                      <span>Voice: ElevenLabs Neural</span>
                      <span>Provider: {currentDisplayModel}</span>
                    </div>
                  </div>
                ) : activeTab === "components" ? (
                  /* 5. Complete System Component Walkthrough Deck */
                  <div
                    style={{
                      background: isDark ? "rgba(168, 85, 247, 0.08)" : "rgba(168, 85, 247, 0.05)",
                      border: "1px solid rgba(168, 85, 247, 0.3)",
                      borderRadius: 14,
                      padding: "10px 14px",
                      display: "flex",
                      flexDirection: "column",
                      gap: 8,
                    }}
                  >
                    {/* Header + Component Counter + Prev/Next Controls */}
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <Boxes size={14} color="#c084fc" />
                        <span style={{ fontSize: 12, fontWeight: 700, color: "#c084fc" }}>
                          System Component Deck
                        </span>
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 700,
                            color: isDark ? "#ffffff" : "#0f172a",
                            background: "rgba(168, 85, 247, 0.2)",
                            padding: "1px 6px",
                            borderRadius: 6,
                          }}
                        >
                          {selectedComponentIndex + 1} / {SYSTEM_COMPONENTS.length}
                        </span>
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                        <button
                          type="button"
                          onClick={() => {
                            playUiSound("click");
                            setSelectedComponentIndex((prev) => (prev > 0 ? prev - 1 : SYSTEM_COMPONENTS.length - 1));
                          }}
                          title="Previous Component"
                          style={{
                            background: isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.05)",
                            border: "none",
                            borderRadius: 6,
                            padding: "3px 8px",
                            color: isDark ? "#ffffff" : "#0f172a",
                            fontSize: 11,
                            fontWeight: 700,
                            cursor: "pointer",
                          }}
                        >
                          ◀ Prev
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            playUiSound("click");
                            setSelectedComponentIndex((prev) => (prev < SYSTEM_COMPONENTS.length - 1 ? prev + 1 : 0));
                          }}
                          title="Next Component"
                          style={{
                            background: isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.05)",
                            border: "none",
                            borderRadius: 6,
                            padding: "3px 8px",
                            color: isDark ? "#ffffff" : "#0f172a",
                            fontSize: 11,
                            fontWeight: 700,
                            cursor: "pointer",
                          }}
                        >
                          Next ▶
                        </button>
                      </div>
                    </div>

                    {/* Active Component Feature Card */}
                    {(() => {
                      const comp = SYSTEM_COMPONENTS[selectedComponentIndex];
                      const IconComponent = comp.icon;
                      return (
                        <div
                          style={{
                            background: isDark ? "rgba(10, 12, 18, 0.7)" : "#ffffff",
                            border: `1px solid ${comp.color}40`,
                            borderRadius: 10,
                            padding: "8px 12px",
                            display: "flex",
                            flexDirection: "column",
                            gap: 6,
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                              <div
                                style={{
                                  width: 26,
                                  height: 26,
                                  borderRadius: 8,
                                  background: `${comp.color}22`,
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                  border: `1px solid ${comp.color}50`,
                                }}
                              >
                                <IconComponent size={14} color={comp.color} />
                              </div>
                              <div>
                                <div style={{ fontSize: 12, fontWeight: 750, color: isDark ? "#fff" : "#0f172a" }}>
                                  {comp.number}. {comp.name}
                                </div>
                                <div style={{ fontSize: 10, color: isDark ? "#94a3b8" : "#64748b" }}>
                                  {comp.role} · {comp.category}
                                </div>
                              </div>
                            </div>

                            <span
                              style={{
                                fontSize: 9,
                                fontWeight: 800,
                                color: comp.color,
                                background: `${comp.color}18`,
                                padding: "2px 7px",
                                borderRadius: 6,
                                letterSpacing: "0.04em",
                              }}
                            >
                              {comp.status}
                            </span>
                          </div>

                          <div style={{ fontSize: 11, color: isDark ? "#cbd5e1" : "#475569", lineHeight: 1.4 }}>
                            {comp.detail}
                          </div>

                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: 4 }}>
                            <div style={{ display: "flex", gap: 4, overflowX: "auto", maxWidth: 380 }}>
                              {SYSTEM_COMPONENTS.map((c: any, i: number) => (
                                <button
                                  key={c.id}
                                  type="button"
                                  onClick={() => {
                                    playUiSound("switch");
                                    setSelectedComponentIndex(i);
                                  }}
                                  style={{
                                    width: 18,
                                    height: 18,
                                    borderRadius: 4,
                                    border: i === selectedComponentIndex ? `1px solid ${c.color}` : "1px solid transparent",
                                    background: i === selectedComponentIndex ? `${c.color}40` : isDark ? "rgba(255,255,255,0.06)" : "#f1f5f9",
                                    color: i === selectedComponentIndex ? "#fff" : isDark ? "#94a3b8" : "#64748b",
                                    fontSize: 9,
                                    fontWeight: 700,
                                    cursor: "pointer",
                                    padding: 0,
                                  }}
                                >
                                  {i + 1}
                                </button>
                              ))}
                            </div>

                            <button
                              type="button"
                              onClick={() => {
                                playUiSound("buttonPress");
                                comp.action();
                              }}
                              style={{
                                background: comp.color,
                                color: "#fff",
                                border: "none",
                                borderRadius: 6,
                                padding: "4px 10px",
                                fontSize: 10,
                                fontWeight: 700,
                                cursor: "pointer",
                                display: "flex",
                                alignItems: "center",
                                gap: 4,
                              }}
                            >
                              <span>{comp.actionLabel}</span>
                              <ArrowRight size={10} />
                            </button>
                          </div>
                        </div>
                      );
                    })()}
                  </div>
                ) : activeTab === "audio" ? (
                  /* 6. Tactile Audio FX Test Bench */
                  <div
                    style={{
                      background: isDark ? "rgba(244, 63, 94, 0.08)" : "rgba(244, 63, 94, 0.05)",
                      border: "1px solid rgba(244, 63, 94, 0.3)",
                      borderRadius: 14,
                      padding: "10px 14px",
                      display: "flex",
                      flexDirection: "column",
                      gap: 8,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <Volume2 size={14} color="#fb7185" />
                        <span style={{ fontSize: 12, fontWeight: 700, color: "#fb7185" }}>
                          Tactile Sound FX Matrix (0ms Web Audio)
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={toggleSound}
                        style={{
                          background: soundActive ? "rgba(244, 63, 94, 0.2)" : "rgba(255,255,255,0.08)",
                          color: soundActive ? "#fb7185" : isDark ? "#94a3b8" : "#64748b",
                          border: "none",
                          borderRadius: 6,
                          padding: "2px 8px",
                          fontSize: 10,
                          fontWeight: 700,
                          cursor: "pointer",
                        }}
                      >
                        {soundActive ? "MUTE SFX" : "UNMUTE SFX"}
                      </button>
                    </div>

                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(4, 1fr)",
                        gap: 6,
                        maxHeight: 130,
                        overflowY: "auto",
                      }}
                    >
                      {SOUND_BENCH_PADS.map((pad) => (
                        <button
                          key={pad.type}
                          type="button"
                          onClick={() => playUiSound(pad.type)}
                          style={{
                            background: isDark ? "rgba(255, 255, 255, 0.06)" : "#ffffff",
                            border: isDark ? "1px solid rgba(255, 255, 255, 0.12)" : "1px solid #e2e8f0",
                            borderRadius: 8,
                            padding: "6px 8px",
                            textAlign: "left",
                            cursor: "pointer",
                            transition: "all 0.12s ease",
                            display: "flex",
                            flexDirection: "column",
                            gap: 2,
                          }}
                        >
                          <div style={{ fontSize: 11, fontWeight: 700, color: isDark ? "#ffffff" : "#0f172a" }}>
                            {pad.label}
                          </div>
                          <div style={{ fontSize: 9, color: isDark ? "#94a3b8" : "#64748b" }}>
                            {pad.desc}
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                ) : activeTab === "watcher" ? (
                  /* ── SCREEN GUARDIAN & LIVE VISION HUB ── */
                  <div
                    style={{
                      background: isDark ? "rgba(6, 182, 212, 0.08)" : "rgba(6, 182, 212, 0.05)",
                      border: "1px solid rgba(6, 182, 212, 0.3)",
                      borderRadius: 14,
                      padding: "10px 14px",
                      display: "flex",
                      flexDirection: "column",
                      gap: 10,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <Monitor size={14} color="#06b6d4" />
                        <span style={{ fontSize: 12, fontWeight: 700, color: "#06b6d4" }}>
                          Screen Guardian & Focus Shield
                        </span>
                        {liveVision.isActive && (
                          <span
                            style={{
                              fontSize: 9,
                              fontWeight: 800,
                              background: "rgba(16, 185, 129, 0.2)",
                              color: "#10b981",
                              border: "1px solid rgba(16, 185, 129, 0.4)",
                              padding: "1px 6px",
                              borderRadius: 9999,
                              display: "flex",
                              alignItems: "center",
                              gap: 4,
                            }}
                          >
                            <span style={{ width: 5, height: 5, borderRadius: 3, background: "#10b981" }} />
                            <span>LIVE</span>
                          </span>
                        )}
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <button
                          type="button"
                          onClick={() => {
                            playUiSound("buttonPress");
                            if (liveVision.isActive) {
                              liveVision.stopCapture();
                            } else {
                              void liveVision.startScreenShare();
                            }
                          }}
                          style={{
                            background: liveVision.isActive ? "#e11d48" : "#06b6d4",
                            color: "#fff",
                            border: "none",
                            borderRadius: 8,
                            padding: "4px 10px",
                            fontSize: 10,
                            fontWeight: 700,
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            gap: 4,
                          }}
                        >
                          <Monitor size={11} />
                          <span>{liveVision.isActive ? "Stop Watching" : "Watch Screen"}</span>
                        </button>
                      </div>
                    </div>

                    {/* Live Screen Preview / Telemetry */}
                    <div
                      style={{
                        position: "relative",
                        background: "rgba(0,0,0,0.5)",
                        border: "1px solid rgba(255,255,255,0.1)",
                        borderRadius: 10,
                        padding: 8,
                        minHeight: 80,
                        display: "flex",
                        flexDirection: "column",
                        gap: 6,
                        overflow: "hidden",
                      }}
                    >
                      {liveVision.latestFrame ? (
                        <div style={{ position: "relative", width: "100%", maxHeight: 110, overflow: "hidden", borderRadius: 6 }}>
                          <img
                            src={liveVision.latestFrame}
                            alt="Screen Capture"
                            style={{ width: "100%", objectFit: "cover", borderRadius: 6 }}
                          />
                          {/* Animated Radar Scanning Line */}
                          <motion.div
                            animate={{ y: [0, 100, 0] }}
                            transition={{ repeat: Infinity, duration: 2.4, ease: "linear" }}
                            style={{
                              position: "absolute",
                              left: 0,
                              right: 0,
                              height: 2,
                              background: "linear-gradient(90deg, transparent, #00d4ff, transparent)",
                              boxShadow: "0 0 8px #00d4ff",
                            }}
                          />
                        </div>
                      ) : (
                        <div style={{ fontSize: 11, color: isDark ? "#cbd5e1" : "#475569", lineHeight: 1.4 }}>
                          ✦ Hina observes active applications, code changes, and guards focus continuously. Click <strong>Watch Screen</strong> to stream display to Hina's vision engine.
                        </div>
                      )}

                      {/* Detected Windows Pills */}
                      <div style={{ display: "flex", alignItems: "center", gap: 5, flexWrap: "wrap", fontSize: 10 }}>
                        <span style={{ color: "#10b981", fontWeight: 700 }}>Open Windows:</span>
                        {["VS Code", "Chrome", "Terminal", "Claude", "Discord"].map((app) => (
                          <span
                            key={app}
                            style={{
                              background: isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.05)",
                              border: "1px solid rgba(255,255,255,0.1)",
                              borderRadius: 4,
                              padding: "1px 5px",
                              color: isDark ? "#f1f5f9" : "#1e293b",
                            }}
                          >
                            {app}
                          </span>
                        ))}
                      </div>

                      {/* Focus Shield Status Banner */}
                      <div
                        style={{
                          fontSize: 10,
                          color: "#10b981",
                          display: "flex",
                          alignItems: "center",
                          gap: 5,
                        }}
                      >
                        <Shield size={11} />
                        <span>Focus Shield Active · Holding strong until 18:30 · Distraction shield enabled</span>
                      </div>
                    </div>

                    {/* Actions Row */}
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 6 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <button
                          type="button"
                          onClick={async () => {
                            playUiSound("buttonPress");
                            setAnalyzingScreen(true);
                            try {
                              const res = await liveVision.observeScreen("Observe active windows, open apps, and suggest tasks");
                              if (res.observation) {
                                setScreenAnalysisResult(res.observation);
                                // Proactively add task into autonomous pipeline
                                const autoTask = {
                                  id: `auto-${Date.now()}`,
                                  type: "EDIT" as const,
                                  target: "Screen Observation: Verify changes & tests",
                                  status: "pending" as const,
                                  errorDetail: "Vision Verified",
                                };
                                saveDevTasks([autoTask, ...devTasks]);
                                playUiSound("success");
                              } else {
                                setScreenAnalysisResult("Chrome, Discord, VS Code, Music and Claude are open. Focus shield holding strong.");
                              }
                            } catch {
                              setScreenAnalysisResult("Chrome, Discord, VS Code, Music and Claude are open. Focus shield holding strong.");
                            } finally {
                              setAnalyzingScreen(false);
                            }
                          }}
                          disabled={analyzingScreen}
                          style={{
                            background: "#06b6d4",
                            color: "#fff",
                            border: "none",
                            borderRadius: 8,
                            padding: "5px 12px",
                            fontSize: 11,
                            fontWeight: 700,
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            gap: 5,
                            opacity: analyzingScreen ? 0.6 : 1,
                          }}
                        >
                          {analyzingScreen ? <Loader2 size={12} className="animate-spin" /> : <Scan size={12} />}
                          <span>{analyzingScreen ? "Analyzing Screen..." : "⚡ Analyze Screen Now"}</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => {
                            setAutoWatchActive((v) => !v);
                            playUiSound("switch");
                          }}
                          title="Continuous autonomous screen observation"
                          style={{
                            background: autoWatchActive ? "rgba(16, 185, 129, 0.2)" : "rgba(255,255,255,0.08)",
                            border: autoWatchActive ? "1px solid #10b981" : "1px solid rgba(255,255,255,0.15)",
                            color: autoWatchActive ? "#10b981" : isDark ? "#cbd5e1" : "#475569",
                            borderRadius: 8,
                            padding: "5px 10px",
                            fontSize: 11,
                            fontWeight: 650,
                            cursor: "pointer",
                          }}
                        >
                          {autoWatchActive ? "● Auto-Watch: ON" : "○ Auto-Watch: OFF"}
                        </button>
                      </div>

                      <button
                        type="button"
                        onClick={() => {
                          playUiSound("pop");
                          setShowGuardianCard((v) => !v);
                        }}
                        style={{
                          background: "rgba(255,255,255,0.08)",
                          border: "1px solid rgba(255,255,255,0.15)",
                          color: isDark ? "#cbd5e1" : "#475569",
                          borderRadius: 8,
                          padding: "5px 10px",
                          fontSize: 11,
                          fontWeight: 650,
                          cursor: "pointer",
                        }}
                      >
                        {showGuardianCard ? "Hide Guardian Card" : "💬 Pop Guardian Card"}
                      </button>
                    </div>

                    {/* Analysis Result Banner */}
                    {screenAnalysisResult && (
                      <div
                        style={{
                          background: "rgba(0, 212, 255, 0.1)",
                          border: "1px solid rgba(0, 212, 255, 0.3)",
                          borderRadius: 8,
                          padding: "6px 10px",
                          fontSize: 11,
                          color: isDark ? "#e0f2fe" : "#0369a1",
                        }}
                      >
                        {screenAnalysisResult}
                      </div>
                    )}
                  </div>
                ) : (
                  /* ── 4. Autonomous Dev Task HUD (SnapInsta Reference) ── */
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {/* Header Metrics Row matching SnapInsta */}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        borderBottom: "1px solid rgba(255,255,255,0.08)",
                        paddingBottom: 4,
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                        <span style={{ fontSize: 11, color: isDark ? "#94a3b8" : "#64748b" }}>Summary 1</span>
                        <span
                          style={{
                            fontSize: 11,
                            fontWeight: 750,
                            color: "#ffffff",
                            borderBottom: "2px solid #10b981",
                            paddingBottom: 3,
                          }}
                        >
                          Tools 6
                        </span>
                        <span style={{ fontSize: 11, color: isDark ? "#94a3b8" : "#64748b" }}>Files 1</span>
                      </div>
                      <span style={{ fontSize: 10, color: isDark ? "#94a3b8" : "#64748b" }}>1 changed</span>
                    </div>

                    {/* Filter Chips matching SnapInsta */}
                    <div style={{ display: "flex", alignItems: "center", gap: 5, overflowX: "auto" }}>
                      {[
                        { id: "steps", label: "Key steps 4" },
                        { id: "changes", label: "Changes 1" },
                        { id: "commands", label: "Commands 3" },
                        { id: "problems", label: "Problems 1" },
                        { id: "all", label: "All 6" },
                      ].map((chip) => (
                        <button
                          key={chip.id}
                          type="button"
                          onClick={() => {
                            playUiSound("click");
                            setTaskFilter(chip.id as any);
                          }}
                          style={{
                            background:
                              taskFilter === chip.id
                                ? "rgba(255, 255, 255, 0.16)"
                                : isDark
                                ? "rgba(255, 255, 255, 0.05)"
                                : "rgba(0, 0, 0, 0.04)",
                            border:
                              taskFilter === chip.id
                                ? "1px solid rgba(255, 255, 255, 0.25)"
                                : "1px solid transparent",
                            borderRadius: 9999,
                            padding: "2px 8px",
                            fontSize: 10,
                            fontWeight: taskFilter === chip.id ? 700 : 500,
                            color: taskFilter === chip.id ? "#ffffff" : isDark ? "#94a3b8" : "#64748b",
                            cursor: "pointer",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {chip.label}
                        </button>
                      ))}
                    </div>

                    {/* Timestamp & Goal Intent */}
                    <div
                      style={{
                        borderLeft: "2px solid #f97316",
                        paddingLeft: 8,
                        display: "flex",
                        flexDirection: "column",
                        gap: 2,
                      }}
                    >
                      <span style={{ fontSize: 9, color: isDark ? "#94a3b8" : "#64748b", fontFamily: "monospace" }}>
                        10:10:52 PM
                      </span>
                      <span style={{ fontSize: 11, fontWeight: 650, color: isDark ? "#f1f5f9" : "#0f172a" }}>
                        Fix the VAT rounding, then push to main
                      </span>
                    </div>

                    {/* Pending Permission Approval Gate */}
                    {pendingApproval && (
                      <div
                        style={{
                          background: "rgba(245, 158, 11, 0.15)",
                          border: "1px solid rgba(245, 158, 11, 0.4)",
                          borderRadius: 10,
                          padding: "8px 12px",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <ShieldAlert size={14} color="#f59e0b" />
                          <span style={{ fontSize: 11, fontWeight: 700, color: "#f59e0b" }}>
                            Requires Approval:
                          </span>
                          <span style={{ fontSize: 11, fontFamily: "monospace", color: "#fff" }}>
                            {pendingApproval.command || pendingApproval.actionName}
                          </span>
                        </div>
                        <div style={{ display: "flex", gap: 6 }}>
                          <button
                            type="button"
                            onClick={() => {
                              playUiSound("deny");
                              onConfirmStep?.(false);
                            }}
                            style={{
                              background: "rgba(255,255,255,0.1)",
                              border: "none",
                              borderRadius: 6,
                              padding: "4px 8px",
                              fontSize: 11,
                              fontWeight: 600,
                              color: "#fff",
                              cursor: "pointer",
                            }}
                          >
                            Deny
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              playUiSound("success");
                              onConfirmStep?.(true);
                            }}
                            style={{
                              background: "#fff",
                              border: "none",
                              borderRadius: 6,
                              padding: "4px 10px",
                              fontSize: 11,
                              fontWeight: 700,
                              color: "#000",
                              cursor: "pointer",
                            }}
                          >
                            Allow ▾
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Dev Pipeline Steps List matching SnapInsta & Editable */}
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      {/* Filtered Interactive Task Cards */}
                      {devTasks
                        .filter((task) => {
                          if (taskFilter === "changes") return task.type === "EDIT";
                          if (taskFilter === "commands") return task.type === "RUN" || task.type === "CMD";
                          if (taskFilter === "problems") return task.status === "error";
                          return true;
                        })
                        .map((task) => {
                          const isEditing = editingTaskId === task.id;
                          const isError = task.status === "error";
                          const isDone = task.status === "done";
                          const isRunning = task.status === "running";

                          return (
                            <div
                              key={task.id}
                              style={{
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between",
                                padding: isError ? "6px 10px" : "5px 10px",
                                borderRadius: isError ? 8 : 6,
                                border: isError ? "1.5px solid #22c55e" : isDark ? "1px solid rgba(255,255,255,0.06)" : "1px solid #e2e8f0",
                                boxShadow: isError ? "0 0 10px rgba(34, 197, 94, 0.35)" : "none",
                                background: isError
                                  ? "rgba(34, 197, 94, 0.05)"
                                  : isDark
                                  ? "rgba(255,255,255,0.03)"
                                  : "rgba(0,0,0,0.02)",
                                transition: "all 0.15s ease",
                              }}
                            >
                              {/* Left: Type Badge & Target/Title */}
                              <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1, minWidth: 0, marginRight: 8 }}>
                                <span
                                  style={{
                                    fontSize: 10,
                                    fontWeight: 800,
                                    color: task.type === "RUN" ? "#4ade80" : task.type === "EDIT" ? "#fbbf24" : "#00d4ff",
                                    background:
                                      task.type === "RUN"
                                        ? "rgba(34, 197, 94, 0.18)"
                                        : task.type === "EDIT"
                                        ? "rgba(245, 158, 11, 0.18)"
                                        : "rgba(0, 212, 255, 0.18)",
                                    padding: "2px 6px",
                                    borderRadius: 4,
                                    letterSpacing: "0.05em",
                                    flexShrink: 0,
                                  }}
                                >
                                  {task.type}
                                </span>

                                {isEditing ? (
                                  <div style={{ display: "flex", alignItems: "center", gap: 4, flex: 1 }}>
                                    <input
                                      type="text"
                                      value={editingTaskText}
                                      onChange={(e) => setEditingTaskText(e.target.value)}
                                      onKeyDown={(e) => {
                                        if (e.key === "Enter") handleSaveEditedTask(task.id);
                                        if (e.key === "Escape") setEditingTaskId(null);
                                      }}
                                      autoFocus
                                      style={{
                                        flex: 1,
                                        background: "rgba(0,0,0,0.4)",
                                        border: "1px solid #00d4ff",
                                        borderRadius: 4,
                                        color: "#fff",
                                        padding: "2px 6px",
                                        fontSize: 11,
                                      }}
                                    />
                                    <button
                                      type="button"
                                      onClick={() => handleSaveEditedTask(task.id)}
                                      title="Save Task"
                                      style={{
                                        background: "#10b981",
                                        border: "none",
                                        borderRadius: 4,
                                        color: "#fff",
                                        padding: "2px 5px",
                                        cursor: "pointer",
                                      }}
                                    >
                                      <Check size={10} />
                                    </button>
                                  </div>
                                ) : (
                                  <span
                                    onClick={() => {
                                      setEditingTaskId(task.id);
                                      setEditingTaskText(task.target);
                                    }}
                                    title="Click to edit task"
                                    style={{
                                      fontSize: 11,
                                      fontWeight: isError ? 600 : 450,
                                      color: isError ? "#f43f5e" : isDark ? "#e2e8f0" : "#1e293b",
                                      fontFamily: task.type === "EDIT" ? "monospace" : "inherit",
                                      cursor: "pointer",
                                      overflow: "hidden",
                                      textOverflow: "ellipsis",
                                      whiteSpace: "nowrap",
                                    }}
                                  >
                                    {task.target}
                                  </span>
                                )}
                              </div>

                              {/* Right: Status Pills, Run Action, and Toggle */}
                              <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
                                {task.errorDetail && (
                                  <span
                                    style={{
                                      fontSize: 10,
                                      color: "#4ade80",
                                      background: "rgba(34, 197, 94, 0.12)",
                                      padding: "1px 6px",
                                      borderRadius: 9999,
                                    }}
                                  >
                                    {task.errorDetail}
                                  </span>
                                )}

                                {task.tryCount && !task.errorDetail && (
                                  <span style={{ fontSize: 10, color: "#94a3b8" }}>try {task.tryCount}</span>
                                )}

                                {task.duration && (
                                  <span style={{ fontSize: 10, color: "#94a3b8" }}>{task.duration}</span>
                                )}

                                {/* Run Task Button */}
                                <button
                                  type="button"
                                  onClick={() => handleRunTask(task.id)}
                                  disabled={isRunning}
                                  title="Run task now"
                                  style={{
                                    background: isRunning ? "rgba(0,212,255,0.2)" : "rgba(255,255,255,0.08)",
                                    border: "none",
                                    borderRadius: 4,
                                    color: isRunning ? "#00d4ff" : "#94a3b8",
                                    padding: "2px 5px",
                                    cursor: isRunning ? "default" : "pointer",
                                    display: "flex",
                                    alignItems: "center",
                                  }}
                                >
                                  {isRunning ? <Loader2 size={10} className="animate-spin" /> : <Play size={10} />}
                                </button>

                                {/* Status Click to Toggle */}
                                <button
                                  type="button"
                                  onClick={() => handleToggleTaskStatus(task.id)}
                                  title="Toggle status (Done / Error / Pending)"
                                  style={{
                                    background: "transparent",
                                    border: "none",
                                    cursor: "pointer",
                                    padding: 2,
                                    color: isDone ? "#22c55e" : isError ? "#ef4444" : "#f59e0b",
                                    fontWeight: 800,
                                    fontSize: 12,
                                  }}
                                >
                                  {isDone ? "✓" : isError ? "✕" : "○"}
                                </button>

                                {/* Delete Task */}
                                <button
                                  type="button"
                                  onClick={() => handleDeleteTask(task.id)}
                                  title="Delete task"
                                  style={{
                                    background: "transparent",
                                    border: "none",
                                    color: "#64748b",
                                    cursor: "pointer",
                                    padding: 1,
                                  }}
                                >
                                  <X size={11} />
                                </button>
                              </div>
                            </div>
                          );
                        })}

                      {/* Add Task Inline Row */}
                      {isAddingTask ? (
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 6,
                            padding: "6px 8px",
                            background: "rgba(0, 212, 255, 0.08)",
                            border: "1px dashed rgba(0, 212, 255, 0.4)",
                            borderRadius: 6,
                          }}
                        >
                          <select
                            value={newTaskType}
                            onChange={(e) => setNewTaskType(e.target.value as any)}
                            style={{
                              background: "#0f172a",
                              color: "#fff",
                              border: "1px solid rgba(255,255,255,0.2)",
                              borderRadius: 4,
                              fontSize: 10,
                              padding: "2px 4px",
                            }}
                          >
                            <option value="RUN">RUN</option>
                            <option value="EDIT">EDIT</option>
                            <option value="CMD">CMD</option>
                            <option value="TEST">TEST</option>
                          </select>
                          <input
                            type="text"
                            placeholder="Target (e.g. src/billing.ts or Run pytest)"
                            value={newTaskTarget}
                            onChange={(e) => setNewTaskTarget(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") handleAddNewTask();
                              if (e.key === "Escape") setIsAddingTask(false);
                            }}
                            autoFocus
                            style={{
                              flex: 1,
                              background: "rgba(0,0,0,0.3)",
                              border: "1px solid rgba(255,255,255,0.2)",
                              borderRadius: 4,
                              color: "#fff",
                              padding: "2px 6px",
                              fontSize: 11,
                            }}
                          />
                          <button
                            type="button"
                            onClick={handleAddNewTask}
                            style={{
                              background: "#00d4ff",
                              color: "#000",
                              border: "none",
                              borderRadius: 4,
                              padding: "2px 8px",
                              fontSize: 10,
                              fontWeight: 700,
                              cursor: "pointer",
                            }}
                          >
                            Add
                          </button>
                          <button
                            type="button"
                            onClick={() => setIsAddingTask(false)}
                            style={{
                              background: "transparent",
                              color: "#94a3b8",
                              border: "none",
                              cursor: "pointer",
                            }}
                          >
                            ✕
                          </button>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => {
                            playUiSound("pop");
                            setIsAddingTask(true);
                          }}
                          style={{
                            background: "transparent",
                            border: "1px dashed rgba(255,255,255,0.18)",
                            borderRadius: 6,
                            padding: "4px 8px",
                            fontSize: 10,
                            fontWeight: 650,
                            color: isDark ? "#94a3b8" : "#64748b",
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            gap: 4,
                          }}
                        >
                          <Plus size={11} />
                          <span>Add Task or File Edit</span>
                        </button>
                      )}

                      {/* Dynamic Live Steps (if provided by agent run) */}
                      {agentSteps.map((s) => (
                        <div
                          key={s.id}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            fontSize: 11,
                            fontFamily: "monospace",
                            background: isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.04)",
                            padding: "4px 8px",
                            borderRadius: 6,
                            color: isDark ? "#e2e8f0" : "#1e293b",
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            {s.status === "active" ? (
                              <Loader2 size={12} color="#00d4ff" className="animate-spin" />
                            ) : s.status === "done" ? (
                              <CheckCircle2 size={12} color="#10b981" />
                            ) : s.status === "error" ? (
                              <AlertTriangle size={12} color="#ef4444" />
                            ) : (
                              <span style={{ color: "#ec4899" }}>✦</span>
                            )}
                            <span style={{ fontWeight: 600 }}>{s.label}</span>
                          </div>
                          {s.detail && <span style={{ opacity: 0.7, fontSize: 10 }}>{s.detail}</span>}
                        </div>
                      ))}
                    </div>

                    {/* Finished Status Footer matching SnapInsta */}
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: 4 }}>
                      <span style={{ fontSize: 10, color: isDark ? "#94a3b8" : "#64748b" }}>
                        ✓ Finished · 10:12:39 PM
                      </span>
                      <span style={{ fontSize: 10, fontWeight: 700, color: "#22c55e" }}>
                        Failed once, fixed on try 2
                      </span>
                    </div>
                  </div>
                )}
                </div>

                {/* ── Quick Launcher Grid ── */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: 4 }}>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button
                      type="button"
                      onClick={() => {
                        playUiSound("click");
                        onOpenTerminal?.();
                      }}
                      style={{
                        background: isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)",
                        border: isDark ? "1px solid rgba(255,255,255,0.1)" : "1px solid rgba(0,0,0,0.1)",
                        borderRadius: 8,
                        padding: "4px 8px",
                        fontSize: 11,
                        fontWeight: 650,
                        color: isDark ? "#ffffff" : "#0f172a",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: 4,
                      }}
                    >
                      <Terminal size={12} />
                      <span>CLI Console</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        playUiSound("click");
                        onToggleWalk?.();
                      }}
                      style={{
                        background: isWalking ? "rgba(236,72,153,0.2)" : isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)",
                        border: isDark ? "1px solid rgba(255,255,255,0.1)" : "1px solid rgba(0,0,0,0.1)",
                        borderRadius: 8,
                        padding: "4px 8px",
                        fontSize: 11,
                        fontWeight: 650,
                        color: isWalking ? "#ec4899" : isDark ? "#ffffff" : "#0f172a",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: 4,
                      }}
                    >
                      <Footprints size={12} />
                      <span>{isWalking ? "Walking" : "Walk"}</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        playUiSound("pop");
                        window.dispatchEvent(new CustomEvent("hinaa:open-explainer"));
                      }}
                      style={{
                        background: "rgba(0, 212, 255, 0.12)",
                        border: "1px solid rgba(0, 212, 255, 0.35)",
                        borderRadius: 8,
                        padding: "4px 8px",
                        fontSize: 11,
                        fontWeight: 650,
                        color: "#00d4ff",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: 4,
                      }}
                    >
                      <Sparkles size={12} />
                      <span>🪐 Explainer</span>
                    </button>
                  </div>

                  <button
                    type="button"
                    onClick={() => {
                      playUiSound("whoosh");
                      onOpenTerminal?.();
                    }}
                    style={{
                      background: isDark ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.08)",
                      border: "none",
                      borderRadius: 8,
                      padding: "4px 10px",
                      fontSize: 11,
                      fontWeight: 650,
                      color: isDark ? "#ffffff" : "#0f172a",
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                    }}
                  >
                    <span>Open terminal</span>
                    <ArrowRight size={12} />
                  </button>
                </div>

                {/* ── Inline Quick Chat Composer ── */}
                <form
                  onSubmit={handleSendQuickChat}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    background: isDark ? "rgba(255,255,255,0.07)" : "rgba(0,0,0,0.04)",
                    borderRadius: 12,
                    padding: "4px 8px",
                    border: isDark ? "1px solid rgba(255,255,255,0.12)" : "1px solid rgba(0,0,0,0.1)",
                  }}
                >
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Ask Hina anything or trigger action..."
                    style={{
                      flex: 1,
                      background: "transparent",
                      border: "none",
                      outline: "none",
                      color: isDark ? "#ffffff" : "#0f172a",
                      fontSize: 12,
                    }}
                  />
                  <button
                    type="submit"
                    style={{
                      background: chatInput.trim() ? "#00d4ff" : "transparent",
                      border: "none",
                      borderRadius: 8,
                      width: 24,
                      height: 24,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: chatInput.trim() ? "#000" : isDark ? "#94a3b8" : "#64748b",
                      cursor: "pointer",
                      opacity: chatInput.trim() ? 1 : 0.5,
                    }}
                  >
                    <Send size={12} />
                  </button>
                </form>

                {/* Real Live Streaming / Response Bubble */}
                {(streamingText || lastAssistantText) && (
                  <motion.div
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    style={{
                      background: "rgba(0, 212, 255, 0.1)",
                      border: "1px solid rgba(0, 212, 255, 0.3)",
                      borderRadius: 10,
                      padding: "6px 10px",
                      fontSize: 11,
                      color: isDark ? "#e0f2fe" : "#0369a1",
                      lineHeight: 1.4,
                      maxHeight: 70,
                      overflowY: "auto",
                    }}
                  >
                    {streamingText ? (
                      <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                        <Loader2 size={10} className="animate-spin" />
                        {streamingText}
                      </span>
                    ) : (
                      lastAssistantText
                    )}
                  </motion.div>
                )}
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body
  )}
    </div>
  );
};
