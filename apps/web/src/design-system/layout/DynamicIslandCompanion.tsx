import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
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
} from "lucide-react";
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
  const [eyeOffset, setEyeOffset] = useState({ x: 0, y: 0 });
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

  // Pupil eye tracking following mouse cursor
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!mascotRef.current) return;
      const rect = mascotRef.current.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const dx = (e.clientX - cx) / 45;
      const dy = (e.clientY - cy) / 45;
      setEyeOffset({
        x: Math.max(-3.5, Math.min(3.5, dx)),
        y: Math.max(-2.8, Math.min(2.8, dy)),
      });
    };

    window.addEventListener("mousemove", handleMouseMove, { passive: true });
    return () => window.removeEventListener("mousemove", handleMouseMove);
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
  const legStride = isWalking ? Math.sin(walkPhase) * 5 : 0;
  const legLift = isWalking ? Math.abs(Math.sin(walkPhase)) * 4.5 : 0;
  const bodyBob = isWalking ? Math.abs(Math.sin(walkPhase * 2)) * 3 : 0;

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
        {/* Animated Stepping Legs & Feet (Coucou Walking Locomotion) */}
        <ellipse
          cx={36 + legStride}
          cy={82 - (legStride > 0 ? legLift : 0)}
          rx={6}
          ry={3.5}
          fill="#ffffff"
          stroke="rgba(0,0,0,0.12)"
          strokeWidth={1}
        />
        <ellipse
          cx={64 - legStride}
          cy={82 - (legStride <= 0 ? legLift : 0)}
          rx={6}
          ry={3.5}
          fill="#ffffff"
          stroke="rgba(0,0,0,0.12)"
          strokeWidth={1}
        />

        {/* Soft Mascot Squircle Body */}
        <g
          transform={`translate(0, ${-bodyBob}) ${
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
          // Normal open expressive eyes with pupil tracking
          <g transform={`translate(0, ${-bodyBob})`}>
            <ellipse cx={34 + eyeOffset.x} cy={46 + eyeOffset.y} rx="4.5" ry="6.5" fill="#121215" />
            <circle cx={32.5 + eyeOffset.x} cy={44 + eyeOffset.y} r="1.8" fill="#ffffff" />
            <ellipse cx={66 + eyeOffset.x} cy={46 + eyeOffset.y} rx="4.5" ry="6.5" fill="#121215" />
            <circle cx={64.5 + eyeOffset.x} cy={44 + eyeOffset.y} r="1.8" fill="#ffffff" />
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
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState<"agent" | "chat" | "stripe" | "upload" | "motion" | "components" | "audio">("agent");
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

  // Island Walk Locomotion state
  const [islandWalkX, setIslandWalkX] = useState(0);
  const [islandWalkDir, setIslandWalkDir] = useState<1 | -1>(1);
  const [islandWalkPhase, setIslandWalkPhase] = useState(0);
  const lastIslandStepSideRef = useRef<"left" | "right">("left");

  // Rhythmic walking loop for notch locomotion
  useEffect(() => {
    if (!isWalking) {
      setIslandWalkX(0);
      return;
    }
    let animId: number;
    let lastTime = performance.now();

    const loop = (time: number) => {
      const dt = Math.min(0.08, (time - lastTime) / 1000);
      lastTime = time;

      const cadence = walkCadence * 3.8;
      setIslandWalkPhase((p) => {
        const next = (p + dt * cadence) % (Math.PI * 2);

        // Sound trigger on step contact
        const stepSin = Math.sin(next);
        if (stepSin > 0.42 && lastIslandStepSideRef.current !== "left") {
          lastIslandStepSideRef.current = "left";
          playFootstepSound();
        } else if (stepSin < -0.42 && lastIslandStepSideRef.current !== "right") {
          lastIslandStepSideRef.current = "right";
          playFootstepSound();
        }

        return next;
      });

      setIslandWalkX((x) => {
        const maxRange = isExpanded ? 45 : 24;
        let nextX = x + islandWalkDir * dt * 24 * walkCadence;
        if (nextX > maxRange) {
          nextX = maxRange;
          setIslandWalkDir(-1);
        } else if (nextX < -maxRange) {
          nextX = -maxRange;
          setIslandWalkDir(1);
        }
        return nextX;
      });

      animId = requestAnimationFrame(loop);
    };

    animId = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(animId);
  }, [isWalking, walkCadence, isExpanded, islandWalkDir]);

  const containerRef = useRef<HTMLDivElement>(null);

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
      ref={containerRef}
      style={{
        position: inlineInTopBar ? "relative" : "fixed",
        top: inlineInTopBar ? 0 : 8,
        left: inlineInTopBar ? "auto" : "50%",
        transform: inlineInTopBar ? "none" : "translateX(-50%)",
        zIndex: 9999,
        fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, sans-serif",
      }}
    >
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
          borderRadius: isExpanded ? 24 : 32,
          padding: isExpanded ? "12px 18px" : "4px 12px",
          width: isExpanded ? 680 : isAgentActive ? 360 : 310,
          color: isDark ? "#ffffff" : "#0f172a",
          display: "flex",
          flexDirection: "column",
          gap: isExpanded ? 12 : 0,
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
              {/* Miniature Coucou Mascot in collapsed notch pill */}
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
                  background: isWalking ? "#ec4899" : isThinking ? "#00d4ff" : "#10b981",
                  boxShadow: `0 0 6px ${isWalking ? "#ec4899" : isThinking ? "#00d4ff" : "#10b981"}`,
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
                setIsExpanded((v) => !v);
              }}
              title={isExpanded ? "Collapse Island" : "Expand Island"}
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
              {isExpanded ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
            </button>
          </div>
        </div>

        {/* ── Expanded Island Command Console ───────────────────────── */}
        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.18, ease: "easeOut" }}
              style={{ display: "flex", gap: 16, paddingTop: 4 }}
            >
              {/* Left Column: Interactive Coucou Mascot */}
              <div
                onClick={() => {
                  playUiSound("pop");
                }}
                title="Hina Mascot Avatar"
              >
                <CoucouMascot
                  mood={isDraggingFile ? "eating" : pendingApproval ? "alert" : isThinking ? "thinking" : "happy"}
                  isHovered={isHovered}
                  size={64}
                />
              </div>

              {/* Center & Right Column: Interactive Deck */}
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 10, minWidth: 0 }}>
                {/* ── Console Mode Navigation Tabs ── */}
                <div style={{ display: "flex", alignItems: "center", gap: 6, borderBottom: "1px solid rgba(255,255,255,0.08)", paddingBottom: 6 }}>
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
                    }}
                  >
                    <Cpu size={12} />
                    <span>Agent & CLI</span>
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
                    }}
                  >
                    <Volume2 size={12} />
                    <span>Sound FX</span>
                  </button>

                  {/* Real Model Selector Dropdown Trigger */}
                  <div style={{ marginLeft: "auto", position: "relative" }}>
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

                {/* ── Tab Content ── */}
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
                  /* 2. Adobe 3D Motion Edit Controls */
                  <div
                    style={{
                      background: "rgba(236, 72, 153, 0.08)",
                      border: "1px solid rgba(236, 72, 153, 0.3)",
                      borderRadius: 14,
                      padding: "10px 14px",
                      display: "flex",
                      flexDirection: "column",
                      gap: 8,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <span style={{ fontSize: 12, fontWeight: 700, color: "#ec4899" }}>
                        3D Motion & Locomotion Controls
                      </span>
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
                          fontSize: 11,
                          fontWeight: 700,
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          gap: 5,
                        }}
                      >
                        <Footprints size={12} />
                        <span>{isWalking ? "Stop Walking" : "Walk / Roam Runway"}</span>
                      </button>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 11, color: isDark ? "#e2e8f0" : "#1e293b" }}>
                      <span>Gait Cadence: {walkCadence}x</span>
                      <div style={{ display: "flex", gap: 6 }}>
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
                              fontSize: 10,
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

                    <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
                      <button
                        type="button"
                        onClick={() => {
                          playUiSound("whoosh");
                          onOpenRunway?.();
                        }}
                        style={{
                          flex: 1,
                          background: "rgba(255,255,255,0.08)",
                          border: "1px solid rgba(255,255,255,0.15)",
                          color: isDark ? "#fff" : "#0f172a",
                          borderRadius: 8,
                          padding: "6px",
                          fontSize: 11,
                          fontWeight: 650,
                          cursor: "pointer",
                        }}
                      >
                        Open Runway 3D Showroom
                      </button>
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
                ) : (
                  /* 4. Real Agent CLI Step Execution Monitor */
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span style={{ fontSize: 12, fontWeight: 700, color: isDark ? "#ffffff" : "#0f172a" }}>
                          ✦ {companionName} Agent Runtime
                        </span>
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 700,
                            color: isDark ? "#94a3b8" : "#64748b",
                            background: isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.05)",
                            padding: "2px 6px",
                            borderRadius: 6,
                          }}
                        >
                          {agentSteps.length > 0 ? `${agentSteps.length} steps` : companionState}
                        </span>
                      </div>
                    </div>

                    {/* Pending Permission Approval Gate */}
                    {pendingApproval ? (
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
                    ) : agentSteps.length > 0 ? (
                      /* Live Agent Steps */
                      <div style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 110, overflowY: "auto" }}>
                        {agentSteps.map((s) => (
                          <div
                            key={s.id}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: 8,
                              fontSize: 11,
                              fontFamily: "monospace",
                              background: isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.04)",
                              padding: "4px 8px",
                              borderRadius: 6,
                              color: isDark ? "#e2e8f0" : "#1e293b",
                            }}
                          >
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
                            {s.detail && (
                              <span style={{ opacity: 0.7, fontSize: 10 }}>· {s.detail}</span>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      /* Active Idle State Monitor */
                      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                            fontSize: 11,
                            fontFamily: "monospace",
                            background: isDark ? "rgba(255,255,255,0.04)" : "rgba(0,0,0,0.03)",
                            padding: "4px 8px",
                            borderRadius: 6,
                            color: isDark ? "#e2e8f0" : "#1e293b",
                          }}
                        >
                          <span style={{ color: "#00d4ff" }}>✦</span>
                          <span>Intelligence Core: {currentDisplayModel} (Ready)</span>
                        </div>
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                            fontSize: 11,
                            fontFamily: "monospace",
                            background: isDark ? "rgba(255,255,255,0.04)" : "rgba(0,0,0,0.03)",
                            padding: "4px 8px",
                            borderRadius: 6,
                            color: isDark ? "#e2e8f0" : "#1e293b",
                          }}
                        >
                          <span style={{ color: "#10b981" }}>✓</span>
                          <span>Avatar: {isWalking ? "Procedural Walking" : "Stationary"}</span>
                        </div>
                      </div>
                    )}
                  </div>
                )}

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
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
};
