import React, { useState, useEffect, useRef, memo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles,
  ArrowRight,
  Shield,
  Zap,
  Terminal,
  Cpu,
  Layers,
  ChevronRight,
  Eye,
  Radio,
  ExternalLink,
  Code,
  Compass,
  Check,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Send,
  MessageSquare,
  Play,
  RotateCcw,
  X,
  Bot,
  User,
  Copy,
  CheckCircle2,
  Brain,
} from "lucide-react";
import { VRMAvatar } from "../../features/avatar/VRMAvatar";
import { CipherDecoderText, GyroOrbLoader } from "../../components/ui/HinaCyberLoaders";
import type { VisemeEvent } from "../../features/audio/textToViseme";
import type { CompanionState, TranscriptMessage } from "../../features/companion/types";
import { WorkMessage } from "./WorkMode";

export interface ShowroomModeProps {
  onEnterWorkspace?: () => void;
  onEnterTalk?: () => void;
  selectedAvatarModel?: string;
  onSelectAvatarModel?: (modelUrl: string) => void;
  isVoiceActive?: boolean;
  isPaused?: boolean;
  voiceDetail?: string;
  microphoneLevel?: number;
  onStartVoice?: () => void;
  onStopVoice?: () => void;
  partialTranscript?: string;
  streamingText?: string;
  companionState?: CompanionState;
  companionName?: string;
  jawEnergy?: React.MutableRefObject<number>;
  speakingRef?: React.MutableRefObject<boolean>;
  visemeEvents?: React.MutableRefObject<VisemeEvent[]>;
  audioStartTimeRef?: React.MutableRefObject<number>;
  onSendText?: (text: string) => void;
  onOpenTerminal?: (cmd?: string) => void;
  onOpenVault?: () => void;
  messages?: TranscriptMessage[];
  isMuted?: boolean;
  onToggleMute?: () => void;
  isDark?: boolean;
}

interface FashionCollectionItem {
  id: string;
  index: string;
  name: string;
  modelUrl: string;
  subtitle: string;
  tagline: string;
  energyPulse: string;
  styleDna: string;
  codeEssence: string;
  accentColor: string;
  bgGradient: string;
  description: string;
  badge: string;
}

const COLLECTIONS: FashionCollectionItem[] = [
  {
    id: "oraniths",
    index: ".01",
    name: "ORANITHS",
    modelUrl: "/models/hinaa-original.vrm",
    subtitle: "Future-Playful Cyber Floral",
    tagline: "Radiant rebels of light, dancing fearlessly at creation's edge.",
    energyPulse: "VIBRANT ORANGE",
    styleDna: "FUTURE-PLAYFUL",
    codeEssence: "CREATIVE CHAOS",
    accentColor: "#ff7a00",
    bgGradient: "radial-gradient(circle at center, rgba(255, 122, 0, 0.15), transparent 70%)",
    description: "Their electric essence shapes the future through bold neural innovation and generative vision.",
    badge: "COLLECTION 01",
  },
  {
    id: "anturax",
    index: ".02",
    name: "ANTURAX",
    modelUrl: "/models/model_6164.vrm",
    subtitle: "Haute-Couture Kimono Neon",
    tagline: "Fiber-optic silk woven with ancient Japanese elegance.",
    energyPulse: "CRIMSON LASER",
    styleDna: "AVANT-GARDE TRADITION",
    codeEssence: "NEURO-HARMONY",
    accentColor: "#ff2a5f",
    bgGradient: "radial-gradient(circle at center, rgba(255, 42, 95, 0.16), transparent 70%)",
    description: "Traditional silhouettes reconstructed through laser-cut organza and bio-luminescent thread.",
    badge: "COLLECTION 02",
  },
  {
    id: "cybersphere",
    index: ".03",
    name: "CYBERSPHERE",
    modelUrl: "/models/model_5447.vrm",
    subtitle: "Streetwear Cyberpunk Casual",
    tagline: "High-frequency urban mobility engineered for augmented reality.",
    energyPulse: "ULTRA VIOLET",
    styleDna: "TACTICAL CASUAL",
    codeEssence: "QUANTUM EFFICIENCY",
    accentColor: "#8b5cf6",
    bgGradient: "radial-gradient(circle at center, rgba(139, 92, 246, 0.16), transparent 70%)",
    description: "Modular techwear tailored for hackers, terminal operators, and deep-space researchers.",
    badge: "COLLECTION 03",
  },
  {
    id: "scholastic",
    index: ".04",
    name: "AKADEMIA",
    modelUrl: "/models/AvatarSample_E.vrm",
    subtitle: "Collegiate VIP Deep Vault",
    tagline: "Institutional academic precision paired with elite cognitive models.",
    energyPulse: "EMERALD SYNAPSE",
    styleDna: "OXFORD RESEARCH",
    codeEssence: "PROVABLE REASONING",
    accentColor: "#10b981",
    bgGradient: "radial-gradient(circle at center, rgba(16, 185, 129, 0.16), transparent 70%)",
    description: "Designed for university faculty, campus researchers, and students mastering defensive cybersecurity.",
    badge: "VIP VAULT",
  },
];

export const ShowroomMode: React.FC<ShowroomModeProps> = memo(({
  onEnterWorkspace,
  onEnterTalk,
  selectedAvatarModel = "/models/hinaa-original.vrm",
  onSelectAvatarModel,
  isVoiceActive = false,
  isPaused = false,
  voiceDetail,
  microphoneLevel = 0,
  onStartVoice,
  onStopVoice,
  partialTranscript = "",
  streamingText = "",
  companionState = "idle",
  companionName = "Hinaa",
  jawEnergy,
  speakingRef,
  visemeEvents,
  audioStartTimeRef,
  onSendText,
  onOpenTerminal,
  onOpenVault,
  messages = [],
  isMuted = false,
  onToggleMute,
  isDark = false,
}) => {
  const [activeItem, setActiveItem] = useState<FashionCollectionItem>(() => {
    if (selectedAvatarModel) {
      const match = COLLECTIONS.find((c) => c.modelUrl === selectedAvatarModel);
      if (match) return match;
    }
    return COLLECTIONS[0];
  });
  const [mouseCoords, setMouseCoords] = useState({ x: 0.0412, y: 0.0306 });
  const [viewMode, setViewMode] = useState<"lookbook" | "runway" | "steep_analytics">("lookbook");
  const [promptInput, setPromptInput] = useState("");
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [drawerInput, setDrawerInput] = useState("");
  const chatScrollRef = useRef<HTMLDivElement>(null);

  const [isMobile, setIsMobile] = useState<boolean>(() => {
    if (typeof window !== "undefined") {
      return window.innerWidth <= 768;
    }
    return false;
  });

  useEffect(() => {
    const handleResize = () => {
      setIsMobile(window.innerWidth <= 768);
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Auto-scroll chat thread to bottom when new message or stream chunk arrives
  useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [messages, streamingText, isChatOpen]);

  // Sync selectedAvatarModel prop with active collection item
  useEffect(() => {
    if (selectedAvatarModel) {
      const match = COLLECTIONS.find((c) => c.modelUrl === selectedAvatarModel);
      if (match && match.id !== activeItem.id) {
        setActiveItem(match);
      }
    }
  }, [selectedAvatarModel, activeItem.id]);

  // Track mouse coordinates for the cyber HUD telemetry
  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width).toFixed(4);
    const y = ((e.clientY - rect.top) / rect.height).toFixed(4);
    setMouseCoords({ x: parseFloat(x), y: parseFloat(y) });
  };

  const handleSelectItem = (item: FashionCollectionItem) => {
    setActiveItem(item);
    if (onSelectAvatarModel) {
      onSelectAvatarModel(item.modelUrl);
    }
  };

  return (
    <div
      className="dich-showroom-root"
      onMouseMove={handleMouseMove}
      style={{
        position: "relative",
        width: "100%",
        minHeight: "calc(100vh - 56px)",
        background: isDark ? "transparent" : "#fbf6f0",
        color: isDark ? "#ffffff" : "#17191c",
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
        overflowY: "auto",
        overflowX: "hidden",
        boxSizing: "border-box",
        padding: isMobile
          ? "8px 8px calc(76px + env(safe-area-inset-bottom, 0px)) 8px"
          : "16px 24px 60px 24px",
      }}
    >
      {/* ── Outer HUD Framing ──────────────────────────────── */}
      <div
        className="dich-outer-frame"
        style={{
          position: "relative",
          maxWidth: 1360,
          margin: "0 auto",
          border: isDark ? "1.5px solid rgba(255, 255, 255, 0.12)" : "1.5px solid rgba(23, 25, 28, 0.12)",
          borderRadius: isMobile ? 18 : 24,
          background: isDark ? "rgba(0, 0, 0, 0.76)" : "#f7efe4",
          backdropFilter: isDark ? "blur(24px)" : "none",
          WebkitBackdropFilter: isDark ? "blur(24px)" : "none",
          boxShadow: isDark ? "0 25px 60px -12px rgba(0, 0, 0, 0.7)" : "0 20px 48px -8px rgba(0, 0, 0, 0.08)",
          overflow: "hidden",
        }}
      >
        {/* Corner HUD Brackets */}
        <div className="dich-corner-bracket dich-corner-tl" />
        <div className="dich-corner-bracket dich-corner-tr" />
        <div className="dich-corner-bracket dich-corner-bl" />
        <div className="dich-corner-bracket dich-corner-br" />

        {/* ── Top Cyber HUD Bar ────────────────────────────── */}
        <header
          style={{
            display: "flex",
            flexDirection: isMobile ? "column" : "row",
            alignItems: "center",
            justifyContent: "space-between",
            padding: isMobile ? "10px 12px" : "12px 24px",
            gap: isMobile ? 8 : 12,
            borderBottom: isDark ? "1px solid rgba(255, 255, 255, 0.08)" : "1px solid rgba(23, 25, 28, 0.08)",
            background: isDark ? "rgba(255, 255, 255, 0.03)" : "rgba(255, 255, 255, 0.65)",
            backdropFilter: "blur(12px)",
          }}
        >
          {/* Left Brand */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
            <div className="dich-pulse-wave">
              <span>/\/\/\-</span>
              <span>LIVE</span>
            </div>
            <span
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 11,
                letterSpacing: "0.08em",
                color: isDark ? "#2b7fff" : "#5d2a1a",
                fontWeight: 700,
                whiteSpace: "nowrap",
              }}
            >
              {isMobile ? "HINAA // 3D RUNWAY" : "HINAA // OMEGA HAUTE-COUTURE"}
            </span>
          </div>

          {/* Center Navigation Pill Switcher */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 4,
              background: isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(23, 25, 28, 0.06)",
              padding: "3px 4px",
              borderRadius: 9999,
              overflowX: "auto",
              flexShrink: 0,
            }}
          >
            <button
              type="button"
              onClick={() => setViewMode("lookbook")}
              style={{
                border: "none",
                background: viewMode === "lookbook" ? (isDark ? "#f5f5f5" : "#17191c") : "transparent",
                color: viewMode === "lookbook" ? (isDark ? "#1b1b1b" : "#ffffff") : (isDark ? "#94a3b8" : "#5d2a1a"),
                fontSize: 11,
                fontWeight: 600,
                padding: "4px 12px",
                borderRadius: 9999,
                cursor: "pointer",
                whiteSpace: "nowrap",
                transition: "all 0.15s ease",
              }}
            >
              LOOKBOOK .01
            </button>
            <button
              type="button"
              onClick={() => setViewMode("runway")}
              style={{
                border: "none",
                background: viewMode === "runway" ? (isDark ? "#f5f5f5" : "#17191c") : "transparent",
                color: viewMode === "runway" ? (isDark ? "#1b1b1b" : "#ffffff") : (isDark ? "#94a3b8" : "#5d2a1a"),
                fontSize: 11,
                fontWeight: 600,
                padding: "4px 12px",
                borderRadius: 9999,
                cursor: "pointer",
                whiteSpace: "nowrap",
                transition: "all 0.15s ease",
              }}
            >
              RUNWAY GALLERY
            </button>
            <button
              type="button"
              onClick={() => setViewMode("steep_analytics")}
              style={{
                border: "none",
                background: viewMode === "steep_analytics" ? (isDark ? "#f5f5f5" : "#17191c") : "transparent",
                color: viewMode === "steep_analytics" ? (isDark ? "#1b1b1b" : "#ffffff") : (isDark ? "#94a3b8" : "#5d2a1a"),
                fontSize: 11,
                fontWeight: 600,
                padding: "4px 12px",
                borderRadius: 9999,
                cursor: "pointer",
                whiteSpace: "nowrap",
                transition: "all 0.15s ease",
              }}
            >
              EDITORIAL ANALYTICS
            </button>
          </div>

          {/* Right Telemetry & Actions */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 11,
              color: isDark ? "#426188" : "#787574",
              flexShrink: 0,
            }}
          >
            {!isMobile && (
              <span>X .0{Math.floor(mouseCoords.x * 1000)} // Y .0{Math.floor(mouseCoords.y * 1000)}</span>
            )}
            <button
              type="button"
              data-testid="showroom-toggle-chat-btn"
              onClick={() => setIsChatOpen(!isChatOpen)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                background: isChatOpen ? activeItem.accentColor : (isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(23, 25, 28, 0.08)"),
                color: isChatOpen ? "#ffffff" : (isDark ? "#ffffff" : "#17191c"),
                border: "none",
                padding: isMobile ? "5px 10px" : "5px 13px",
                borderRadius: 9999,
                fontSize: 11,
                fontWeight: 650,
                cursor: "pointer",
                transition: "all 0.15s ease",
                boxShadow: isChatOpen ? `0 2px 10px ${activeItem.accentColor}55` : "none",
                whiteSpace: "nowrap",
              }}
            >
              <MessageSquare size={12} />
              <span>LIVE CHAT {messages.length > 0 ? `(${messages.length})` : ""}</span>
            </button>
            <button
              type="button"
              onClick={onEnterWorkspace}
              style={{
                background: isDark ? "#f5f5f5" : "#17191c",
                color: isDark ? "#1b1b1b" : "#ffffff",
                border: "none",
                padding: isMobile ? "5px 10px" : "5px 14px",
                borderRadius: 9999,
                fontSize: 11,
                fontWeight: 600,
                cursor: "pointer",
                whiteSpace: "nowrap",
              }}
            >
              {isMobile ? "CANVAS →" : "WORKSPACE →"}
            </button>
          </div>
        </header>

        {/* ── VIEW 1: DICH FASHION LOOKBOOK HERO (Screenshot 1) ── */}
        {viewMode === "lookbook" && (
          isMobile ? (
            <div
              style={{
                padding: "16px 12px 28px 12px",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 18,
                minHeight: 480,
              }}
            >
              {/* 1. Iconic Circular Cyber-Fashion Viewport (Centered) */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  position: "relative",
                  width: "100%",
                }}
              >
                <div
                  className="dich-circular-lens"
                  style={{
                    position: "relative",
                    width: "min(300px, 82vw)",
                    height: "min(300px, 82vw)",
                    borderRadius: "50%",
                    border: isVoiceActive
                      ? `2.5px solid ${activeItem.accentColor}`
                      : "2px solid #17191c",
                    boxShadow: isVoiceActive
                      ? `0 0 0 ${8 + Math.round((microphoneLevel || 0) * 16)}px ${activeItem.accentColor}33, 0 0 40px ${activeItem.accentColor}88, 0 16px 36px -8px ${activeItem.accentColor}44`
                      : companionState === "speaking" || (speakingRef?.current ?? false)
                      ? `0 0 0 10px ${activeItem.accentColor}44, 0 0 32px ${activeItem.accentColor}88, 0 16px 36px -8px ${activeItem.accentColor}33`
                      : `0 0 0 8px rgba(255,255,255,0.7), 0 16px 36px -8px ${activeItem.accentColor}33`,
                    background: activeItem.bgGradient,
                    overflow: "hidden",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    transition: "box-shadow 0.15s ease, border-color 0.2s ease",
                  }}
                >
                  {/* Real 3D VRM Model */}
                  <div style={{ width: "100%", height: "100%", transform: "scale(1.15)" }}>
                    <VRMAvatar
                      companionId="hinaa"
                      state={companionState}
                      modelUrl={activeItem.modelUrl}
                      reducedMotion={false}
                      textOnly={false}
                      closeUp={true}
                      jawEnergy={jawEnergy}
                      speakingRef={speakingRef}
                      visemeEvents={visemeEvents}
                      audioStartTimeRef={audioStartTimeRef}
                    />
                  </div>

                  {/* Top Status Pill on the Lens */}
                  <div
                    style={{
                      position: "absolute",
                      top: 14,
                      background: isVoiceActive
                        ? "rgba(16, 185, 129, 0.95)"
                        : companionState === "speaking" || (speakingRef?.current ?? false)
                        ? "rgba(255, 122, 0, 0.95)"
                        : "rgba(23, 25, 28, 0.85)",
                      color: "#ffffff",
                      backdropFilter: "blur(8px)",
                      fontSize: 10,
                      fontWeight: 700,
                      letterSpacing: "0.08em",
                      padding: "4px 12px",
                      borderRadius: 9999,
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      boxShadow: "0 4px 12px rgba(0,0,0,0.2)",
                      zIndex: 10,
                    }}
                  >
                    {isVoiceActive ? (
                      <>
                        <Mic size={11} />
                        <span>LISTENING...</span>
                      </>
                    ) : companionState === "speaking" || (speakingRef?.current ?? false) ? (
                      <>
                        <Volume2 size={11} />
                        <span>SPEAKING...</span>
                      </>
                    ) : (
                      <>
                        <span style={{ width: 6, height: 6, borderRadius: "50%", background: activeItem.accentColor }} />
                        <span>{activeItem.badge} // 3D VRM</span>
                      </>
                    )}
                  </div>

                  {/* Floating Dialogue HUD inside the Lens */}
                  <AnimatePresence>
                    {(partialTranscript || streamingText) && (
                      <motion.div
                        initial={{ opacity: 0, y: 8, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 8, scale: 0.95 }}
                        style={{
                          position: "absolute",
                          bottom: 50,
                          maxWidth: "90%",
                          background: "rgba(23, 25, 28, 0.92)",
                          color: "#ffffff",
                          backdropFilter: "blur(12px)",
                          padding: "8px 12px",
                          borderRadius: 12,
                          boxShadow: "0 8px 24px rgba(0,0,0,0.3)",
                          border: `1px solid ${activeItem.accentColor}88`,
                          zIndex: 15,
                          textAlign: "center",
                          fontSize: 11,
                          lineHeight: 1.4,
                          pointerEvents: "none",
                        }}
                      >
                        {partialTranscript ? (
                          <div style={{ color: "#fbe1d1" }}>
                            <span style={{ fontWeight: 700, color: activeItem.accentColor }}>You: </span>
                            {partialTranscript}
                          </div>
                        ) : (
                          <div>
                            <span style={{ fontWeight: 700, color: activeItem.accentColor }}>Hinaa: </span>
                            {streamingText.slice(-160)}
                          </div>
                        )}
                      </motion.div>
                    )}
                  </AnimatePresence>

                  {/* Subtitle Badge */}
                  <div
                    style={{
                      position: "absolute",
                      bottom: 16,
                      background: "rgba(23, 25, 28, 0.85)",
                      color: "#ffffff",
                      backdropFilter: "blur(8px)",
                      fontSize: 10,
                      fontWeight: 600,
                      letterSpacing: "0.08em",
                      padding: "3px 10px",
                      borderRadius: 9999,
                      zIndex: 5,
                    }}
                  >
                    {activeItem.badge}
                  </div>
                </div>

                {/* Title below lens */}
                <div
                  style={{
                    marginTop: 14,
                    fontFamily: "'Signifier', Georgia, ui-serif, serif",
                    fontSize: 34,
                    fontWeight: 400,
                    letterSpacing: "-0.02em",
                    color: "#17191c",
                    textAlign: "center",
                    lineHeight: 1.1,
                  }}
                >
                  {activeItem.name}
                </div>
                <div
                  style={{
                    fontSize: 12,
                    color: "#5d2a1a",
                    textAlign: "center",
                    maxWidth: 320,
                    marginTop: 4,
                    lineHeight: 1.45,
                  }}
                >
                  {activeItem.tagline}
                </div>
              </div>

              {/* 2. Haute-Couture Switcher (All 6 Models) */}
              <div style={{ width: "100%", textAlign: "center" }}>
                <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", color: "#787574", marginBottom: 8 }}>
                  HAUTE-COUTURE SELECTION ({COLLECTIONS.length} AVATARS)
                </div>
                <div style={{ display: "flex", gap: 8, justifyContent: "center", flexWrap: "wrap" }}>
                  {COLLECTIONS.map((c) => {
                    const isSelected = c.id === activeItem.id;
                    return (
                      <button
                        key={c.id}
                        type="button"
                        onClick={() => handleSelectItem(c)}
                        style={{
                          padding: "6px 12px",
                          borderRadius: 8,
                          border: isSelected ? `2px solid ${c.accentColor}` : "1px solid rgba(23, 25, 28, 0.15)",
                          background: isSelected ? "#ffffff" : "rgba(255,255,255,0.5)",
                          display: "flex",
                          alignItems: "center",
                          gap: 6,
                          cursor: "pointer",
                          transition: "all 0.15s ease",
                          boxShadow: isSelected ? `0 4px 12px ${c.accentColor}44` : "none",
                        }}
                      >
                        <div
                          style={{
                            width: 8,
                            height: 8,
                            borderRadius: "50%",
                            background: c.accentColor,
                          }}
                        />
                        <span style={{ fontSize: 11, fontWeight: 700, color: "#17191c" }}>{c.index}</span>
                        <span style={{ fontSize: 10, color: "#5d2a1a" }}>{c.name}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* 3. Cyber Metadata Badge */}
              <div
                style={{
                  background: "rgba(255, 255, 255, 0.7)",
                  padding: "12px 16px",
                  borderRadius: 14,
                  border: "1px solid rgba(23, 25, 28, 0.08)",
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 10.5,
                  lineHeight: 1.5,
                  color: "#332f2d",
                  width: "100%",
                  maxWidth: 380,
                  boxSizing: "border-box",
                }}
              >
                <div style={{ color: activeItem.accentColor, fontWeight: 700, marginBottom: 4 }}>
                  &lt;BODY ( SERIE#OMEGA_V2 )
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span>PULSE: {activeItem.energyPulse}</span>
                  <span>DNA: {activeItem.styleDna}</span>
                </div>
                <div style={{ marginTop: 4, fontWeight: 600, color: "#17191c" }}>
                  {activeItem.codeEssence}
                </div>
              </div>
            </div>
          ) : (
            <div
              style={{
                padding: "36px 32px 48px 32px",
                display: "grid",
                gridTemplateColumns: "1.1fr 1.6fr 1.1fr",
                gap: 24,
                alignItems: "center",
                minHeight: 580,
              }}
            >
              {/* Left Column: Cyber Code Metadata & Micro Ticks */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 20,
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 11,
                  lineHeight: 1.65,
                  color: "#332f2d",
                }}
              >
                <div style={{ color: "#787574", letterSpacing: "0.08em" }}>
                  +++ <br />
                  DARE_TO_DISRUPT <br />
                  &lt;META CHARSET=UTF-8&gt;
                </div>

                <div
                  style={{
                    background: "rgba(255, 255, 255, 0.6)",
                    padding: "16px 18px",
                    borderRadius: 16,
                    border: "1px solid rgba(23, 25, 28, 0.08)",
                    boxShadow: "0 4px 12px rgba(0,0,0,0.03)",
                  }}
                >
                  <div style={{ color: activeItem.accentColor, fontWeight: 700, marginBottom: 4 }}>
                    &lt;BODY (
                  </div>
                  <div>SERIE#OMEGA_V2</div>
                  <div>ENERGY-PULSE: {activeItem.energyPulse}</div>
                  <div style={{ margin: "6px 0", opacity: 0.4 }}>+++</div>
                  <div>STYLE-DNA: {activeItem.styleDna}</div>
                  <div>CODE-ESSENCE: {activeItem.codeEssence}</div>
                  <div style={{ marginTop: 8, fontWeight: 700, color: "#17191c" }}>
                    DISRUPT. CREATE. DOMINATE )
                  </div>
                </div>

                {/* Reticle Crosshair */}
                <div style={{ display: "flex", alignItems: "center", gap: 10, opacity: 0.6 }}>
                  <div
                    style={{
                      width: 28,
                      height: 28,
                      border: "1px dashed #17191c",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <div style={{ width: 6, height: 6, background: activeItem.accentColor }} />
                  </div>
                  <span>STYLE=UTF-1 // LIVE</span>
                </div>
              </div>

              {/* Center Column: Iconic Circular Cyber-Fashion Viewport */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  position: "relative",
                }}
              >
                <div
                  className="dich-circular-lens"
                  style={{
                    position: "relative",
                    width: 380,
                    height: 380,
                    borderRadius: "50%",
                    border: isVoiceActive
                      ? `2.5px solid ${activeItem.accentColor}`
                      : "2px solid #17191c",
                    boxShadow: isVoiceActive
                      ? `0 0 0 ${10 + Math.round((microphoneLevel || 0) * 20)}px ${activeItem.accentColor}33, 0 0 50px ${activeItem.accentColor}88, 0 20px 48px -10px ${activeItem.accentColor}44`
                      : companionState === "speaking" || (speakingRef?.current ?? false)
                      ? `0 0 0 12px ${activeItem.accentColor}44, 0 0 40px ${activeItem.accentColor}88, 0 20px 48px -10px ${activeItem.accentColor}33`
                      : `0 0 0 10px rgba(255,255,255,0.7), 0 20px 48px -10px ${activeItem.accentColor}33`,
                    background: activeItem.bgGradient,
                    overflow: "hidden",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    transition: "box-shadow 0.15s ease, border-color 0.2s ease",
                  }}
                >
                  {/* Real 3D VRM Model Loaded in the circular lens */}
                  <div style={{ width: "100%", height: "100%", transform: "scale(1.15)" }}>
                    <VRMAvatar
                      companionId="hinaa"
                      state={companionState}
                      modelUrl={activeItem.modelUrl}
                      reducedMotion={false}
                      textOnly={false}
                      closeUp={true}
                      jawEnergy={jawEnergy}
                      speakingRef={speakingRef}
                      visemeEvents={visemeEvents}
                      audioStartTimeRef={audioStartTimeRef}
                    />
                  </div>

                  {/* Top Status Pill on the Lens */}
                  <div
                    style={{
                      position: "absolute",
                      top: 18,
                      background: isVoiceActive
                        ? "rgba(16, 185, 129, 0.95)"
                        : companionState === "thinking"
                        ? "linear-gradient(135deg, rgba(168, 85, 247, 0.95), rgba(236, 72, 153, 0.95))"
                        : companionState === "speaking" || (speakingRef?.current ?? false)
                        ? "rgba(255, 122, 0, 0.95)"
                        : "rgba(23, 25, 28, 0.85)",
                      color: "#ffffff",
                      backdropFilter: "blur(8px)",
                      fontSize: 10,
                      fontWeight: 700,
                      letterSpacing: "0.08em",
                      padding: "4px 12px",
                      borderRadius: 9999,
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                      boxShadow: companionState === "thinking" ? "0 4px 18px rgba(168, 85, 247, 0.45)" : "0 4px 12px rgba(0,0,0,0.2)",
                      zIndex: 10,
                    }}
                  >
                    {isVoiceActive ? (
                      <>
                        <Mic size={11} />
                        <span>LISTENING...</span>
                      </>
                    ) : companionState === "thinking" ? (
                      <>
                        <Brain size={11} className="animate-pulse" style={{ color: "#ffffff" }} />
                        <span>DEEP REASONING...</span>
                      </>
                    ) : companionState === "speaking" || (speakingRef?.current ?? false) ? (
                      <>
                        <Volume2 size={11} />
                        <span>SPEAKING...</span>
                      </>
                    ) : (
                      <>
                        <span style={{ width: 6, height: 6, borderRadius: "50%", background: activeItem.accentColor }} />
                        <span>{activeItem.badge} // 3D VRM</span>
                      </>
                    )}
                  </div>

                  {/* Floating Dialogue HUD inside the Lens */}
                  <AnimatePresence>
                    {(partialTranscript || streamingText || companionState === "thinking") && (
                      <motion.div
                        initial={{ opacity: 0, y: 10, scale: 0.95 }}
                        animate={{ opacity: 1, y: 0, scale: 1 }}
                        exit={{ opacity: 0, y: 10, scale: 0.95 }}
                        style={{
                          position: "absolute",
                          bottom: 60,
                          maxWidth: "85%",
                          background: isDark ? "rgba(18, 22, 31, 0.92)" : "rgba(255, 255, 255, 0.94)",
                          color: isDark ? "#ffffff" : "#17191c",
                          backdropFilter: "blur(14px)",
                          padding: "8px 14px",
                          borderRadius: 14,
                          boxShadow: "0 8px 24px rgba(0,0,0,0.2)",
                          border: isDark ? "1px solid rgba(255, 255, 255, 0.12)" : "1px solid rgba(23, 25, 28, 0.12)",
                          zIndex: 15,
                          textAlign: "center",
                          fontSize: 11,
                          lineHeight: 1.45,
                          pointerEvents: "none",
                        }}
                      >
                        {partialTranscript ? (
                          <div style={{ color: isDark ? "#fbe1d1" : "#854d0e" }}>
                            <span style={{ fontWeight: 700, color: activeItem.accentColor }}>You: </span>
                            {partialTranscript}
                          </div>
                        ) : streamingText ? (
                          <div>
                            <span style={{ fontWeight: 700, color: activeItem.accentColor }}>Hinaa: </span>
                            {streamingText.length > 180
                              ? "…" + streamingText.slice(Math.max(0, streamingText.lastIndexOf(" ", streamingText.length - 140)))
                              : streamingText}
                          </div>
                        ) : companionState === "thinking" ? (
                          <div style={{ display: "inline-flex", alignItems: "center", gap: 6, color: isDark ? "#ffffff" : "#17191c" }}>
                            <Brain size={12} className="animate-pulse" style={{ color: activeItem.accentColor }} />
                            <span style={{ fontWeight: 700, color: activeItem.accentColor }}>Hinaa: </span>
                            <span style={{ fontStyle: "italic", opacity: 0.85 }}>Synthesizing deep reasoning...</span>
                          </div>
                        ) : null}
                      </motion.div>
                    )}
                  </AnimatePresence>

                  {/* Subtitle Badge */}
                  <div
                    style={{
                      position: "absolute",
                      bottom: 24,
                      background: "rgba(23, 25, 28, 0.85)",
                      color: "#ffffff",
                      backdropFilter: "blur(8px)",
                      fontSize: 10,
                      fontWeight: 600,
                      letterSpacing: "0.08em",
                      padding: "4px 12px",
                      borderRadius: 9999,
                      zIndex: 5,
                    }}
                  >
                    {activeItem.badge}
                  </div>
                </div>

                {/* Massive Geometric Title below the Lens */}
                <div
                  style={{
                    marginTop: 20,
                    fontFamily: "'Signifier', Georgia, ui-serif, serif",
                    fontSize: 52,
                    fontWeight: 400,
                    letterSpacing: "-0.03em",
                    color: "#17191c",
                    textAlign: "center",
                    lineHeight: 1,
                  }}
                >
                  {activeItem.name}
                </div>
                <div
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 11,
                    color: "#787574",
                    marginTop: 4,
                    letterSpacing: "0.1em",
                  }}
                >
                  X .0412 // Y .0306 // 3D_VRM_LIVE
                </div>
              </div>

              {/* Right Column: Collection Metric, Discover CTA, and Carousel Thumbnails */}
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 20,
                }}
              >
                {/* Giant Index Number */}
                <div
                  style={{
                    fontSize: 76,
                    fontFamily: "'Signifier', Georgia, serif",
                    lineHeight: 0.9,
                    fontWeight: 400,
                    color: "#17191c",
                  }}
                >
                  {activeItem.index}
                </div>

                {/* Discover Pill Button */}
                <div>
                  <button
                    type="button"
                    onClick={() => {
                      if (isVoiceActive) onStopVoice?.();
                      else onStartVoice?.();
                    }}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 12,
                      background: isVoiceActive ? "#059669" : "#17191c",
                      color: "#ffffff",
                      border: isVoiceActive ? "2px solid #34d399" : "none",
                      borderRadius: 9999,
                      padding: "10px 22px",
                      fontSize: 13,
                      fontWeight: 600,
                      letterSpacing: "0.04em",
                      cursor: "pointer",
                      boxShadow: isVoiceActive
                        ? "0 0 20px rgba(16, 185, 129, 0.5)"
                        : "0 6px 16px rgba(0,0,0,0.15)",
                      transition: "all 0.15s ease",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.transform = "translateY(-1px)")}
                    onMouseLeave={(e) => (e.currentTarget.style.transform = "translateY(0)")}
                  >
                    <span>{isVoiceActive ? "STOP VOICE" : "COMMUNICATE"}</span>
                    <span
                      style={{
                        background: isVoiceActive ? "#ffffff" : activeItem.accentColor,
                        color: "#17191c",
                        width: 22,
                        height: 22,
                        borderRadius: 9999,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontWeight: 800,
                        fontSize: 11,
                      }}
                    >
                      {isVoiceActive ? "■" : ">>"}
                    </span>
                  </button>
                </div>

                {/* Editorial Description */}
                <div
                  style={{
                    fontSize: 13,
                    lineHeight: 1.6,
                    color: "#5d2a1a",
                    maxWidth: 280,
                  }}
                >
                  {activeItem.tagline} {activeItem.description}
                </div>

                {/* Collection Carousel Thumbnails */}
                <div style={{ marginTop: 8 }}>
                  <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", color: "#787574", marginBottom: 8 }}>
                    HAUTE-COUTURE SELECTION
                  </div>
                  <div style={{ display: "flex", gap: 8 }}>
                    {COLLECTIONS.map((c) => {
                      const isSelected = c.id === activeItem.id;
                      return (
                        <button
                          key={c.id}
                          type="button"
                          onClick={() => handleSelectItem(c)}
                          style={{
                            width: 48,
                            height: 56,
                            borderRadius: 8,
                            border: isSelected ? `2px solid ${c.accentColor}` : "1px solid rgba(23, 25, 28, 0.15)",
                            background: isSelected ? "#ffffff" : "rgba(255,255,255,0.5)",
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "center",
                            justifyContent: "center",
                            gap: 2,
                            cursor: "pointer",
                            transition: "all 0.15s ease",
                            boxShadow: isSelected ? `0 4px 12px ${c.accentColor}44` : "none",
                          }}
                        >
                          <span style={{ fontSize: 10, fontWeight: 700, color: "#17191c" }}>{c.index}</span>
                          <div
                            style={{
                              width: 6,
                              height: 6,
                              borderRadius: "50%",
                              background: c.accentColor,
                            }}
                          />
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          )
        )}

        {/* ── VIEW 2: DICH RUNWAY GALLERY (Screenshot 2 ANTURAX) ── */}
        {viewMode === "runway" && (
          <div
            className="dich-hud-dark-matrix"
            style={{
              padding: "48px 32px 64px 32px",
              background: "#0e100f",
              color: "#fffce1",
              minHeight: 580,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <div
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 11,
                letterSpacing: "0.15em",
                color: "#ff8709",
                marginBottom: 16,
              }}
            >
              &#123; DICH // RUNWAY GALLERY &#125;
            </div>

            {/* Horizontal Runway Cards */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 24,
                width: "100%",
                overflowX: "auto",
                padding: "20px 0",
              }}
            >
              {COLLECTIONS.map((c, i) => {
                const isSelected = c.id === activeItem.id;
                return (
                  <motion.div
                    key={c.id}
                    whileHover={{ scale: 1.03 }}
                    onClick={() => handleSelectItem(c)}
                    style={{
                      width: 220,
                      minHeight: 340,
                      borderRadius: 24,
                      background: isSelected ? "rgba(255, 252, 225, 0.08)" : "rgba(255, 252, 225, 0.03)",
                      border: isSelected ? `2px solid ${c.accentColor}` : "1px solid #42433d",
                      boxShadow: isSelected ? `0 0 24px ${c.accentColor}66` : "none",
                      padding: 16,
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "space-between",
                      cursor: "pointer",
                      position: "relative",
                      backdropFilter: "blur(8px)",
                    }}
                  >
                    <div>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <span style={{ fontSize: 12, fontFamily: "'JetBrains Mono', monospace", color: c.accentColor }}>
                          {c.index}
                        </span>
                        {isSelected && (
                          <span
                            style={{
                              fontSize: 9,
                              background: c.accentColor,
                              color: "#0e100f",
                              fontWeight: 700,
                              padding: "2px 6px",
                              borderRadius: 9999,
                            }}
                          >
                            SELECTED
                          </span>
                        )}
                      </div>

                      {/* Small avatar circular preview */}
                      <div
                        style={{
                          width: 140,
                          height: 140,
                          borderRadius: "50%",
                          margin: "16px auto",
                          border: `1.5px solid ${c.accentColor}`,
                          background: c.bgGradient,
                          overflow: "hidden",
                        }}
                      >
                        <VRMAvatar
                          companionId="hinaa"
                          state={isSelected ? companionState : "idle"}
                          modelUrl={c.modelUrl}
                          reducedMotion={!isSelected}
                          textOnly={false}
                          closeUp={true}
                          jawEnergy={isSelected ? jawEnergy : undefined}
                          speakingRef={isSelected ? speakingRef : undefined}
                          visemeEvents={isSelected ? visemeEvents : undefined}
                          audioStartTimeRef={isSelected ? audioStartTimeRef : undefined}
                        />
                      </div>

                      <div style={{ fontSize: 18, fontWeight: 600, color: "#fffce1", textAlign: "center" }}>
                        {c.name}
                      </div>
                      <div style={{ fontSize: 11, color: "#7c7c6f", textAlign: "center", marginTop: 4 }}>
                        {c.subtitle}
                      </div>
                    </div>

                    <button
                      type="button"
                      style={{
                        width: "100%",
                        padding: "8px 0",
                        borderRadius: 100,
                        background: isSelected ? c.accentColor : "transparent",
                        color: isSelected ? "#0e100f" : "#fffce1",
                        border: `1px solid ${c.accentColor}`,
                        fontSize: 11,
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      {isSelected ? "ACTIVE VRM MODEL" : "SELECT MODEL"}
                    </button>
                  </motion.div>
                );
              })}
            </div>

            {/* Bottom Title Bar */}
            <div
              style={{
                marginTop: 24,
                fontFamily: "'Signifier', Georgia, serif",
                fontSize: 38,
                letterSpacing: "0.1em",
                color: "#fffce1",
              }}
            >
              A N T U R A X
            </div>
            <div
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 10,
                color: "#7c7c6f",
                marginTop: 4,
              }}
            >
              X .0852 // Y .0370 // FIBER_OPTIC_HAUTE_COUTURE
            </div>
          </div>
        )}

        {/* ── VIEW 3: STEEP & SHOP STYLE EDITORIAL ARTIFACTS ── */}
        {viewMode === "steep_analytics" && (
          <div
            style={{
              padding: "40px 32px 56px 32px",
              background: "#ffffff",
              minHeight: 580,
            }}
          >
            {/* Steep Serif Headline on White Canvas */}
            <div style={{ maxWidth: 880, margin: "0 auto 40px auto", textAlign: "center" }}>
              <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.08em", color: "#777b86", textTransform: "uppercase" }}>
                EDITORIAL ARTIFACTS & TELEMETRY
              </div>
              <h1
                style={{
                  fontFamily: "'Signifier', Georgia, ui-serif, serif",
                  fontSize: 48,
                  fontWeight: 400,
                  lineHeight: 1.25,
                  letterSpacing: "-0.96px",
                  color: "#17191c",
                  marginTop: 12,
                }}
              >
                Serif analytics floating on <em>warm editorial paper</em>.
              </h1>
              <p
                style={{
                  fontSize: 17,
                  lineHeight: 1.5,
                  color: "#777b86",
                  marginTop: 12,
                  maxWidth: 640,
                  margin: "12px auto 0 auto",
                }}
              >
                HINAA unifies university infrastructure, deep dual-path cognitive routing, and private college knowledge bases into one seamless executive canvas.
              </p>
            </div>

            {/* Grid of Steep & Shop Floating Artifact Cards */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
                gap: 24,
                maxWidth: 1180,
                margin: "0 auto",
              }}
            >
              {/* Card 1: Steep Signature Blush Peach Card */}
              <div
                style={{
                  background: "#fbe1d1",
                  color: "#5d2a1a",
                  borderRadius: 24,
                  padding: "32px 24px",
                  border: "none",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                }}
              >
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.05em", opacity: 0.8 }}>
                    COLLEGE VIP DEEP VAULT
                  </div>
                  <div style={{ fontSize: 24, fontWeight: 500, marginTop: 8, letterSpacing: "-0.01em" }}>
                    Verified Student ID Portal
                  </div>
                  <p style={{ fontSize: 15, lineHeight: 1.5, marginTop: 12, opacity: 0.9 }}>
                    Curated playbooks on Ethical Hacking, production AI agent scripts, and 4-hour systems architecture lectures locked under campus credentials.
                  </p>
                </div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    marginTop: 20,
                    fontWeight: 600,
                    fontSize: 14,
                  }}
                >
                  <Shield size={16} />
                  <span>100% On-Premise Data Sovereignty</span>
                </div>
              </div>

              {/* Card 2: Neutral Metric Artifact Card */}
              <div
                style={{
                  background: isDark ? "rgba(255, 255, 255, 0.05)" : "#ffffff",
                  borderRadius: 20,
                  padding: 24,
                  border: isDark ? "1px solid rgba(255, 255, 255, 0.08)" : "1px solid rgba(4, 23, 43, 0.05)",
                  boxShadow: isDark ? "0 20px 25px -5px rgba(0,0,0,0.3)" : "0 20px 25px -5px rgba(0,0,0,0.06), 0 8px 10px -6px rgba(0,0,0,0.04)",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                }}
              >
                <div>
                  <div style={{ fontSize: 13, color: isDark ? "#426188" : "#777b86", fontWeight: 500 }}>
                    Cognitive Response Latency
                  </div>
                  <div style={{ fontSize: 36, fontWeight: 600, color: isDark ? "#ffffff" : "#17191c", marginTop: 4 }}>
                    142ms
                  </div>
                  <div style={{ fontSize: 13, color: "#10b981", fontWeight: 600, marginTop: 2 }}>
                    ↑ 5.5x faster with Casual Fast-Path
                  </div>

                  {/* Gestural line simulation */}
                  <div
                    style={{
                      height: 48,
                      width: "100%",
                      marginTop: 20,
                      background: isDark
                        ? "linear-gradient(90deg, rgba(255,255,255,0.04) 0%, rgba(43, 127, 255, 0.2) 100%)"
                        : "linear-gradient(90deg, #f2f2f3 0%, rgba(220, 95, 139, 0.2) 100%)",
                      borderRadius: 8,
                      position: "relative",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        position: "absolute",
                        bottom: 0,
                        left: 0,
                        right: 0,
                        height: 2,
                        background: isDark ? "#2b7fff" : "#5d2a1a",
                      }}
                    />
                  </div>
                </div>

                <div style={{ fontSize: 12, color: isDark ? "#426188" : "#979799", marginTop: 16 }}>
                  Active Engine: OmniRoute (Claude 3.5 Sonnet + Gemini 2.5 Flash)
                </div>
              </div>

              {/* Card 3: Shop Style Discovery Pill Card */}
              <div
                style={{
                  background: isDark ? "rgba(255, 255, 255, 0.04)" : "#f2f4f5",
                  borderRadius: 28,
                  padding: 24,
                  border: isDark ? "1px solid rgba(255, 255, 255, 0.08)" : "none",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                }}
              >
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: isDark ? "#2b7fff" : "#5433eb" }}>
                    SHOP CONSTELLATION
                  </div>
                  <div style={{ fontSize: 22, fontWeight: 600, color: isDark ? "#ffffff" : "#000000", marginTop: 6 }}>
                    Hands & Automation
                  </div>
                  <p style={{ fontSize: 14, color: isDark ? "rgba(255, 255, 255, 0.65)" : "#787574", marginTop: 8, lineHeight: 1.45 }}>
                    Execute terminal shell commands, manage git branches, and send Office 365 Outlook emails directly.
                  </p>
                </div>

                {/* Shop Violet Action Pill */}
                <div style={{ marginTop: 24 }}>
                  <button
                    type="button"
                    onClick={onEnterWorkspace}
                    style={{
                      width: "100%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "8px 16px",
                      borderRadius: 9999,
                      background: "#ffffff",
                      border: "1px solid rgba(5,41,77,0.1)",
                      cursor: "pointer",
                      boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
                    }}
                  >
                    <span style={{ fontSize: 13, fontWeight: 500, color: "#000000" }}>
                      Launch Terminal Hands
                    </span>
                    <span
                      style={{
                        width: 32,
                        height: 32,
                        borderRadius: "50%",
                        background: "#5433eb",
                        color: "#ffffff",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        boxShadow: "0 4px 16px rgba(69,36,219,0.34)",
                      }}
                    >
                      <ArrowRight size={14} />
                    </span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── Interactive Runway Voice & Prompt Dock ────────── */}
        <div
          style={{
            borderTop: isDark ? "1px solid rgba(255, 255, 255, 0.08)" : "1px solid rgba(23, 25, 28, 0.08)",
            background: isDark ? "rgba(11, 14, 20, 0.9)" : "rgba(255, 255, 255, 0.85)",
            backdropFilter: "blur(16px)",
            padding: isMobile ? "10px 12px 14px" : "14px 28px",
            display: "flex",
            flexDirection: "column",
            gap: isMobile ? 8 : 10,
          }}
        >
          {/* Quick Action Chips */}
          <div style={{ display: "flex", alignItems: "center", gap: 6, overflowX: "auto", paddingBottom: 2 }}>
            <span
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 10,
                color: isDark ? "#426188" : "#787574",
                fontWeight: 600,
                letterSpacing: "0.06em",
                marginRight: 4,
                flexShrink: 0,
              }}
            >
              ACTIONS:
            </span>
            <button
              type="button"
              onClick={() => onSendText?.("Tell me about your current outfit, cyber aesthetic, and style DNA!")}
              style={{
                background: isDark ? "rgba(255, 255, 255, 0.06)" : "rgba(23, 25, 28, 0.05)",
                border: isDark ? "1px solid rgba(255, 255, 255, 0.1)" : "1px solid rgba(23, 25, 28, 0.1)",
                borderRadius: 9999,
                padding: "4px 10px",
                fontSize: isMobile ? 10.5 : 11,
                fontWeight: 600,
                color: isDark ? "#f5f5f5" : "#17191c",
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                whiteSpace: "nowrap",
                transition: "all 0.15s ease",
              }}
            >
              <Sparkles size={11} color={activeItem.accentColor} />
              <span>Explain Outfit</span>
            </button>
            <button
              type="button"
              onClick={() => onSendText?.("Let's review our code architecture and check our recent test runs.")}
              style={{
                background: isDark ? "rgba(255, 255, 255, 0.06)" : "rgba(23, 25, 28, 0.05)",
                border: isDark ? "1px solid rgba(255, 255, 255, 0.1)" : "1px solid rgba(23, 25, 28, 0.1)",
                borderRadius: 9999,
                padding: "4px 10px",
                fontSize: isMobile ? 10.5 : 11,
                fontWeight: 600,
                color: isDark ? "#f5f5f5" : "#17191c",
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                whiteSpace: "nowrap",
              }}
            >
              <Code size={11} />
              <span>Code Craft</span>
            </button>
            <button
              type="button"
              onClick={() => onSendText?.("Give me a fast update on the 2026 global crisis and technology trends.")}
              style={{
                background: isDark ? "rgba(255, 255, 255, 0.06)" : "rgba(23, 25, 28, 0.05)",
                border: isDark ? "1px solid rgba(255, 255, 255, 0.1)" : "1px solid rgba(23, 25, 28, 0.1)",
                borderRadius: 9999,
                padding: "4px 10px",
                fontSize: isMobile ? 10.5 : 11,
                fontWeight: 600,
                color: isDark ? "#f5f5f5" : "#17191c",
                cursor: "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                whiteSpace: "nowrap",
              }}
            >
              <Compass size={11} />
              <span>2026 World Pulse</span>
            </button>
            {onOpenTerminal && (
              <button
                type="button"
                onClick={() => onOpenTerminal("git status")}
                style={{
                  background: isDark ? "rgba(255, 255, 255, 0.06)" : "rgba(23, 25, 28, 0.05)",
                  border: isDark ? "1px solid rgba(255, 255, 255, 0.1)" : "1px solid rgba(23, 25, 28, 0.1)",
                  borderRadius: 9999,
                  padding: "4px 10px",
                  fontSize: isMobile ? 10.5 : 11,
                  fontWeight: 600,
                  color: isDark ? "#f5f5f5" : "#17191c",
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                  whiteSpace: "nowrap",
                }}
              >
                <Terminal size={11} />
                <span>Terminal Hands</span>
              </button>
            )}
            {onOpenVault && (
              <button
                type="button"
                onClick={onOpenVault}
                style={{
                  background: isDark ? "rgba(255, 255, 255, 0.06)" : "rgba(23, 25, 28, 0.05)",
                  border: isDark ? "1px solid rgba(255, 255, 255, 0.1)" : "1px solid rgba(23, 25, 28, 0.1)",
                  borderRadius: 9999,
                  padding: "4px 10px",
                  fontSize: isMobile ? 10.5 : 11,
                  fontWeight: 600,
                  color: isDark ? "#f5f5f5" : "#17191c",
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                  whiteSpace: "nowrap",
                }}
              >
                <Shield size={11} />
                <span>VIP Vault</span>
              </button>
            )}
          </div>

          {/* Quick Voice / Text Input Row */}
          <div style={{ display: "flex", alignItems: "center", gap: isMobile ? 8 : 12, width: "100%" }}>
            {/* Live Mic Button */}
            <button
              type="button"
              onClick={() => {
                if (isVoiceActive) onStopVoice?.();
                else onStartVoice?.();
              }}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: isMobile ? 5 : 8,
                background: isVoiceActive ? "#059669" : (isDark ? "#f5f5f5" : "#17191c"),
                color: isVoiceActive ? "#ffffff" : (isDark ? "#1b1b1b" : "#ffffff"),
                border: isVoiceActive ? "2px solid #34d399" : "none",
                borderRadius: 9999,
                padding: isMobile ? "8px 12px" : "8px 18px",
                fontSize: isMobile ? 11 : 12,
                fontWeight: 700,
                cursor: "pointer",
                boxShadow: isVoiceActive
                  ? "0 0 16px rgba(16, 185, 129, 0.4)"
                  : "0 2px 8px rgba(0,0,0,0.1)",
                transition: "all 0.15s ease",
                flexShrink: 0,
                whiteSpace: "nowrap",
              }}
            >
              {isVoiceActive ? <MicOff size={13} /> : <Mic size={13} />}
              <span>{isVoiceActive ? (isMobile ? "END" : "END VOICE") : (isMobile ? "VOICE" : "LIVE VOICE")}</span>
            </button>

            {/* Quick Text Input */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (promptInput.trim()) {
                  onSendText?.(promptInput.trim());
                  setPromptInput("");
                  setIsChatOpen(true);
                }
              }}
              style={{ flex: 1, display: "flex", alignItems: "center", gap: 6, minWidth: 0 }}
            >
              <div
                style={{
                  flex: 1,
                  position: "relative",
                  display: "flex",
                  alignItems: "center",
                  minWidth: 0,
                }}
              >
                <input
                  type="text"
                  value={promptInput}
                  onChange={(e) => setPromptInput(e.target.value)}
                  placeholder={isMobile ? "Talk or type..." : "Talk or type to Hina in 3D Runway..."}
                  style={{
                    width: "100%",
                    background: isDark ? "rgba(20, 24, 33, 0.9)" : "rgba(255, 255, 255, 0.9)",
                    border: isDark ? "1px solid rgba(255, 255, 255, 0.12)" : "1px solid rgba(23, 25, 28, 0.15)",
                    borderRadius: 9999,
                    padding: isMobile ? "8px 34px 8px 12px" : "9px 40px 9px 18px",
                    fontSize: isMobile ? 12 : 13,
                    color: isDark ? "#ffffff" : "#17191c",
                    outline: "none",
                    fontFamily: "inherit",
                    boxShadow: "inset 0 1px 3px rgba(0,0,0,0.03)",
                    minWidth: 0,
                  }}
                />
                <button
                  type="submit"
                  disabled={!promptInput.trim()}
                  style={{
                    position: "absolute",
                    right: 4,
                    width: 26,
                    height: 26,
                    borderRadius: "50%",
                    background: promptInput.trim() ? "#17191c" : "transparent",
                    color: promptInput.trim() ? "#ffffff" : "#9ca3af",
                    border: "none",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    cursor: promptInput.trim() ? "pointer" : "default",
                  }}
                >
                  <Send size={12} />
                </button>
              </div>
            </form>

            {/* Live Chat Toggle Button */}
            <button
              type="button"
              data-testid="showroom-footer-chat-btn"
              onClick={() => setIsChatOpen(!isChatOpen)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                background: isChatOpen ? activeItem.accentColor : "#17191c",
                color: "#ffffff",
                border: "none",
                borderRadius: 9999,
                padding: isMobile ? "8px 10px" : "8px 16px",
                fontSize: isMobile ? 11 : 12,
                fontWeight: 650,
                cursor: "pointer",
                flexShrink: 0,
                boxShadow: isChatOpen ? `0 2px 12px ${activeItem.accentColor}66` : "0 2px 8px rgba(0,0,0,0.15)",
                transition: "all 0.15s ease",
                whiteSpace: "nowrap",
              }}
            >
              <MessageSquare size={12} />
              <span>{isChatOpen ? "HIDE" : `CHAT (${messages.length})`}</span>
            </button>

            {!isMobile && (
              <button
                type="button"
                onClick={onEnterWorkspace}
                style={{
                  background: "transparent",
                  border: isDark ? "1px solid rgba(255, 255, 255, 0.12)" : "1px solid rgba(23, 25, 28, 0.12)",
                  borderRadius: 9999,
                  padding: "8px 14px",
                  fontSize: 12,
                  fontWeight: 600,
                  color: isDark ? "#f5f5f5" : "#17191c",
                  cursor: "pointer",
                  flexShrink: 0,
                }}
              >
                Canvas →
              </button>
            )}
          </div>
        </div>

        {/* ── Cyber-Runway Live Chat Drawer (Full Interactive Dialogue Experience) ── */}
        <AnimatePresence>
          {isChatOpen && (
            <motion.div
              initial={isMobile ? { y: "100%", opacity: 0 } : { x: "100%", opacity: 0 }}
              animate={isMobile ? { y: 0, opacity: 1 } : { x: 0, opacity: 1 }}
              exit={isMobile ? { y: "100%", opacity: 0 } : { x: "100%", opacity: 0 }}
              transition={{ type: "spring", damping: 28, stiffness: 240 }}
              style={{
                position: "fixed",
                bottom: 0,
                right: 0,
                left: isMobile ? 0 : "auto",
                top: isMobile ? "auto" : 0,
                height: isMobile ? "82vh" : "100%",
                width: isMobile ? "100%" : "min(460px, 94vw)",
                background: isDark ? "rgba(11, 14, 20, 0.98)" : "rgba(255, 255, 255, 0.98)",
                backdropFilter: "blur(28px) saturate(1.2)",
                WebkitBackdropFilter: "blur(28px) saturate(1.2)",
                borderLeft: isMobile ? "none" : (isDark ? "1.5px solid rgba(255, 255, 255, 0.1)" : "1.5px solid rgba(23, 25, 28, 0.12)"),
                borderTop: isMobile ? (isDark ? "1.5px solid rgba(255, 255, 255, 0.1)" : "1.5px solid rgba(23, 25, 28, 0.15)") : "none",
                borderRadius: isMobile ? "22px 22px 0 0" : 0,
                boxShadow: isMobile ? "0 -16px 48px rgba(0, 0, 0, 0.35)" : "-12px 0 40px rgba(0, 0, 0, 0.25)",
                zIndex: 99999,
                display: "flex",
                flexDirection: "column",
                overflow: "hidden",
                fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
              }}
            >
              {/* Mobile Drag Indicator */}
              {isMobile && (
                <div style={{ width: 36, height: 4, borderRadius: 2, background: isDark ? "rgba(255, 255, 255, 0.2)" : "rgba(23, 25, 28, 0.2)", margin: "8px auto 0 auto" }} />
              )}
              {/* Drawer Header */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "14px 18px",
                  borderBottom: isDark ? "1px solid rgba(255, 255, 255, 0.08)" : "1px solid rgba(23, 25, 28, 0.08)",
                  background: isDark ? "rgba(18, 22, 31, 0.9)" : "rgba(247, 239, 228, 0.7)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: "50%",
                      background: activeItem.accentColor,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "#ffffff",
                    }}
                  >
                    <Sparkles size={14} />
                  </div>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: isDark ? "#ffffff" : "#17191c", display: "flex", alignItems: "center", gap: 6 }}>
                      <span>Runway Dialogue</span>
                      <span
                        style={{
                          fontSize: 9,
                          fontWeight: 700,
                          letterSpacing: "0.06em",
                          background: isVoiceActive ? "#10b981" : (isDark ? "#2b7fff" : "#17191c"),
                          color: "#ffffff",
                          padding: "1px 6px",
                          borderRadius: 4,
                        }}
                      >
                        {isVoiceActive ? "VOICE ACTIVE" : "3D STREAM"}
                      </span>
                    </div>
                    <div style={{ fontSize: 10, color: isDark ? "#426188" : "#787574", fontFamily: "'JetBrains Mono', monospace" }}>
                      COLLECTION // {activeItem.name} ({activeItem.styleDna})
                    </div>
                  </div>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <button
                    type="button"
                    onClick={() => {
                      if (isVoiceActive) onStopVoice?.();
                      else onStartVoice?.();
                    }}
                    title={isVoiceActive ? "Stop Voice" : "Start Live Voice"}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: 30,
                      height: 30,
                      borderRadius: "50%",
                      border: "none",
                      background: isVoiceActive ? "#ef4444" : (isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(23, 25, 28, 0.08)"),
                      color: isVoiceActive ? "#ffffff" : (isDark ? "#ffffff" : "#17191c"),
                      cursor: "pointer",
                    }}
                  >
                    {isVoiceActive ? <MicOff size={14} /> : <Mic size={14} />}
                  </button>
                  <button
                    type="button"
                    onClick={() => setIsChatOpen(false)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: 30,
                      height: 30,
                      borderRadius: "50%",
                      border: "none",
                      background: isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(23, 25, 28, 0.08)",
                      color: isDark ? "#ffffff" : "#17191c",
                      cursor: "pointer",
                      fontSize: 16,
                      fontWeight: 700,
                    }}
                  >
                    <X size={15} />
                  </button>
                </div>
              </div>

              {/* Message History Thread */}
              <div
                ref={chatScrollRef}
                style={{
                  flex: 1,
                  overflowY: "auto",
                  padding: "16px 16px",
                  display: "flex",
                  flexDirection: "column",
                  gap: 12,
                  WebkitOverflowScrolling: "touch",
                }}
              >
                {messages.length === 0 && !streamingText && !partialTranscript && (
                  <div
                    style={{
                      margin: "auto 0",
                      textAlign: "center",
                      padding: "24px 16px",
                      borderRadius: 16,
                      background: isDark ? "rgba(18, 22, 31, 0.6)" : "rgba(247, 239, 228, 0.6)",
                      border: isDark ? "1px dashed rgba(255, 255, 255, 0.15)" : "1px dashed rgba(23, 25, 28, 0.15)",
                    }}
                  >
                    <div
                      style={{
                        width: 48,
                        height: 48,
                        borderRadius: "50%",
                        background: activeItem.accentColor,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        margin: "0 auto 12px auto",
                        color: "#ffffff",
                        boxShadow: `0 8px 24px ${activeItem.accentColor}55`,
                      }}
                    >
                      <Bot size={24} />
                    </div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: isDark ? "#ffffff" : "#17191c", marginBottom: 4 }}>
                      Hina Live 3D Runway
                    </div>
                    <div style={{ fontSize: 12, color: isDark ? "#94a3b8" : "#5d2a1a", lineHeight: 1.5, maxWidth: 280, margin: "0 auto 14px auto" }}>
                      I am standing in the 3D Runway with full lip-sync visemes and voice recognition. Ask me anything or click below to talk!
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, justifyContent: "center" }}>
                      {[
                        "Tell me about this 3D model",
                        "नमस्ते हिना! कैसी हो?",
                        "What is your energy pulse?",
                        "Help me write an essay",
                      ].map((prompt) => (
                        <button
                          key={prompt}
                          type="button"
                          onClick={() => {
                            onSendText?.(prompt);
                          }}
                          style={{
                            fontSize: 11,
                            padding: "5px 10px",
                            borderRadius: 9999,
                            border: isDark ? "1px solid rgba(255, 255, 255, 0.12)" : "1px solid rgba(23, 25, 28, 0.12)",
                            background: isDark ? "rgba(255, 255, 255, 0.06)" : "#ffffff",
                            color: isDark ? "#ffffff" : "#17191c",
                            cursor: "pointer",
                            transition: "all 0.12s ease",
                          }}
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Render Past Messages with full Markdown, Code, Sources, and Artifacts */}
                {messages.map((msg, idx) => {
                  const text = msg.text || (msg as any).content || "";
                  if (!text.trim() && !msg.imageUrl) return null;
                  return <WorkMessage key={msg.id || idx} message={msg} isDark={isDark} />;
                })}

                {/* Streaming Response Bubble */}
                {/* In-progress Response Bubble: Thinking or Streaming */}
                {(Boolean(streamingText) || companionState === "thinking") && (
                  <WorkMessage
                    message={
                      {
                        id: "showroom-streaming",
                        role: "assistant",
                        text: streamingText || "",
                        createdAt: new Date().toISOString(),
                      } as TranscriptMessage
                    }
                    isStreaming={Boolean(streamingText)}
                    isThinkingLive={companionState === "thinking" && !streamingText}
                    isDark={isDark}
                  />
                )}

                {/* Partial Transcript when user is speaking */}
                {partialTranscript && (
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "flex-end",
                      maxWidth: "100%",
                    }}
                  >
                    <div
                      style={{
                        fontSize: 10,
                        fontWeight: 650,
                        color: "#059669",
                        marginBottom: 3,
                        paddingRight: 4,
                        display: "flex",
                        alignItems: "center",
                        gap: 4,
                      }}
                    >
                      <Mic size={10} />
                      <span>Hearing you…</span>
                    </div>
                    <div
                      style={{
                        maxWidth: "88%",
                        padding: "8px 12px",
                        borderRadius: "16px 16px 4px 16px",
                        background: "rgba(16, 185, 129, 0.12)",
                        color: "#065f46",
                        fontSize: 12,
                        fontStyle: "italic",
                        border: "1px dashed #10b981",
                      }}
                    >
                      {partialTranscript}
                    </div>
                  </div>
                )}
              </div>

              {/* Drawer Composer */}
              <div
                style={{
                  padding: isMobile
                    ? "10px 14px calc(14px + env(safe-area-inset-bottom, 0px)) 14px"
                    : "12px 16px",
                  borderTop: isDark ? "1px solid rgba(255, 255, 255, 0.08)" : "1px solid rgba(23, 25, 28, 0.08)",
                  background: isDark ? "rgba(11, 14, 20, 1)" : "#ffffff",
                }}
              >
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (drawerInput.trim()) {
                      onSendText?.(drawerInput.trim());
                      setDrawerInput("");
                    }
                  }}
                  style={{ display: "flex", alignItems: "center", gap: 8 }}
                >
                  <input
                    type="text"
                    value={drawerInput}
                    onChange={(e) => setDrawerInput(e.target.value)}
                    placeholder="Type to Hina..."
                    style={{
                      flex: 1,
                      padding: "9px 14px",
                      borderRadius: 9999,
                      border: isDark ? "1px solid rgba(255, 255, 255, 0.12)" : "1px solid rgba(23, 25, 28, 0.15)",
                      fontSize: 13,
                      color: isDark ? "#ffffff" : "#17191c",
                      outline: "none",
                      background: isDark ? "rgba(20, 24, 33, 0.9)" : "rgba(247, 239, 228, 0.3)",
                    }}
                  />
                  {isVoiceActive ? (
                    <button
                      type="button"
                      onClick={onStopVoice}
                      title="Stop Voice"
                      style={{
                        width: 34,
                        height: 34,
                        borderRadius: "50%",
                        border: "none",
                        background: "#ef4444",
                        color: "#ffffff",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        cursor: "pointer",
                      }}
                    >
                      <MicOff size={14} />
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={onStartVoice}
                      title="Start Voice"
                      style={{
                        width: 34,
                        height: 34,
                        borderRadius: "50%",
                        border: isDark ? "1px solid rgba(255, 255, 255, 0.12)" : "1px solid rgba(23, 25, 28, 0.12)",
                        background: isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(255,255,255,0.8)",
                        color: isDark ? "#f5f5f5" : "#5e545d",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        cursor: "pointer",
                      }}
                    >
                      <Mic size={14} />
                    </button>
                  )}
                  <button
                    type="submit"
                    disabled={!drawerInput.trim()}
                    style={{
                      width: 34,
                      height: 34,
                      borderRadius: "50%",
                      border: "none",
                      background: drawerInput.trim() ? activeItem.accentColor : "rgba(23, 25, 28, 0.08)",
                      color: drawerInput.trim() ? "#ffffff" : "#9ca3af",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      cursor: drawerInput.trim() ? "pointer" : "default",
                      transition: "all 0.12s ease",
                    }}
                  >
                    <Send size={14} />
                  </button>
                </form>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
});
