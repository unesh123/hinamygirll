import React, { useState, useEffect, useRef, useCallback } from "react";
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
} from "lucide-react";
import { playUiSound, isSoundEnabled, setSoundEnabled, type UiSoundType } from "../../lib/uiSound";
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

// Coucou Interactive Mascot Avatar Component
export const CoucouMascot: React.FC<{
  mood?: "idle" | "happy" | "eating" | "alert" | "thinking";
  isHovered?: boolean;
  size?: number;
}> = ({ mood = "idle", isHovered = false, size = 56 }) => {
  const [blink, setBlink] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => {
      setBlink(true);
      setTimeout(() => setBlink(false), 160);
    }, 3800 + Math.random() * 2000);
    return () => clearInterval(interval);
  }, []);

  const scale = size / 64;

  return (
    <div
      style={{
        position: "relative",
        width: size,
        height: size,
        borderRadius: Math.round(16 * scale),
        overflow: "hidden",
        background: "radial-gradient(circle at 50% 35%, #1e2235 0%, #08090e 100%)",
        border: "1px solid rgba(255, 255, 255, 0.16)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        boxShadow: "inset 0 1px 1px rgba(255,255,255,0.25), 0 4px 16px rgba(0,0,0,0.5)",
        cursor: "pointer",
        flexShrink: 0,
      }}
    >
      {/* Starry Ambient Aura */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(1px 1px at 20% 30%, rgba(255,255,255,0.8) 100%, transparent), radial-gradient(1.5px 1.5px at 75% 25%, rgba(0,212,255,0.9) 100%, transparent), radial-gradient(1px 1px at 85% 75%, rgba(236,72,153,0.8) 100%, transparent), radial-gradient(1.5px 1.5px at 35% 80%, rgba(255,255,255,0.6) 100%, transparent)",
          opacity: 0.75,
        }}
      />

      {/* SVG Coucou / Hina Character */}
      <svg
        width={Math.round(42 * scale)}
        height={Math.round(42 * scale)}
        viewBox="0 0 100 100"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{
          transform: isHovered ? "scale(1.08) translateY(-1px)" : "scale(1)",
          transition: "transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1)",
        }}
      >
        {/* Soft Body */}
        <motion.ellipse
          cx="50"
          cy="54"
          rx="38"
          ry="30"
          fill="#ffffff"
          animate={{
            ry: mood === "eating" ? [30, 34, 30] : [30, 29, 30],
            cy: mood === "happy" ? [54, 51, 54] : [54, 55, 54],
          }}
          transition={{ repeat: Infinity, duration: mood === "happy" ? 1.2 : 2.8, ease: "easeInOut" }}
        />

        {/* Anime Cheeks (Blush) */}
        <ellipse cx="28" cy="58" rx="5" ry="3" fill="#ffb4c8" opacity="0.7" />
        <ellipse cx="72" cy="58" rx="5" ry="3" fill="#ffb4c8" opacity="0.7" />

        {/* Eyes */}
        {blink || mood === "happy" ? (
          // Happy / Blinking curved eyes ^ ^
          <>
            <path d="M 29 49 Q 34 43 39 49" stroke="#121215" strokeWidth="3.5" strokeLinecap="round" fill="none" />
            <path d="M 61 49 Q 66 43 71 49" stroke="#121215" strokeWidth="3.5" strokeLinecap="round" fill="none" />
          </>
        ) : (
          // Normal open expressive eyes
          <>
            <ellipse cx="34" cy="48" rx="4.5" ry="6.5" fill="#121215" />
            <circle cx="32.5" cy="46" r="1.8" fill="#ffffff" />
            <ellipse cx="66" cy="48" rx="4.5" ry="6.5" fill="#121215" />
            <circle cx="64.5" cy="46" r="1.8" fill="#ffffff" />
          </>
        )}

        {/* Mouth */}
        {mood === "eating" ? (
          // Mouth open eating dropped file
          <path d="M 44 55 Q 50 70 56 55 Z" fill="#ff5a82" />
        ) : mood === "happy" ? (
          <path d="M 45 56 Q 50 63 55 56" stroke="#121215" strokeWidth="3" strokeLinecap="round" fill="none" />
        ) : (
          // Subtle neutral/cute mouth
          <path d="M 47 57 Q 50 60 53 57" stroke="#121215" strokeWidth="2.5" strokeLinecap="round" fill="none" />
        )}

        {/* Tiny waving hands on hover */}
        {isHovered && (
          <motion.ellipse
            cx="84"
            cy="46"
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
  const [activeTab, setActiveTab] = useState<"agent" | "chat" | "stripe" | "upload" | "motion">("agent");
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
    playUiSound("buttonPress");

    const query = chatInput.trim();
    setLastUserQuery(query);
    setChatInput("");

    if (onSendMessage) {
      onSendMessage(query);
    }
  };

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
              }}
            >
              <div
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: 11,
                  background: isThinking
                    ? "radial-gradient(circle, #00d4ff 0%, #0284c7 100%)"
                    : isAgentActive
                    ? "radial-gradient(circle, #f59e0b 0%, #d97706 100%)"
                    : "radial-gradient(circle, #ec4899 0%, #a855f7 100%)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  boxShadow: "0 0 12px rgba(236,72,153,0.5)",
                  animation: isThinking ? "pulse 1.5s infinite" : "none",
                }}
              >
                {isThinking ? (
                  <Loader2 size={12} color="#fff" className="animate-spin" />
                ) : (
                  <span style={{ fontSize: 11, fontWeight: 800, color: "#fff" }}>✦</span>
                )}
              </div>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 650,
                  letterSpacing: "0.01em",
                  color: isDark ? "#ffffff" : "#0f172a",
                }}
              >
                {isDraggingFile
                  ? "Drop File to Feed Hina"
                  : isThinking
                  ? "Hina Thinking..."
                  : isAgentActive
                  ? "Agent Executing..."
                  : `${companionName} Island`}
              </span>

              {/* Status Dot */}
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: 3,
                  background: isThinking ? "#00d4ff" : "#10b981",
                  boxShadow: `0 0 6px ${isThinking ? "#00d4ff" : "#10b981"}`,
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
