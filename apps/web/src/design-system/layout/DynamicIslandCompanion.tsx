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
} from "lucide-react";

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
  isThinking?: boolean;
  activeProviderModel?: string | null;
  companionName?: string;
}

// Delightful Web Audio UI Sound Synthesizer (Zero asset dependencies)
function playUiSound(type: "pop" | "click" | "whoosh" | "success" | "deny") {
  try {
    const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioContextClass) return;
    const ctx = new AudioContextClass();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);

    const now = ctx.currentTime;
    if (type === "pop") {
      osc.type = "sine";
      osc.frequency.setValueAtTime(580, now);
      osc.frequency.exponentialRampToValueAtTime(880, now + 0.08);
      gain.gain.setValueAtTime(0.12, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.08);
      osc.start(now);
      osc.stop(now + 0.08);
    } else if (type === "click") {
      osc.type = "triangle";
      osc.frequency.setValueAtTime(800, now);
      gain.gain.setValueAtTime(0.08, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.04);
      osc.start(now);
      osc.stop(now + 0.04);
    } else if (type === "whoosh") {
      osc.type = "sine";
      osc.frequency.setValueAtTime(320, now);
      osc.frequency.exponentialRampToValueAtTime(640, now + 0.14);
      gain.gain.setValueAtTime(0.1, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.14);
      osc.start(now);
      osc.stop(now + 0.14);
    } else if (type === "success") {
      osc.type = "sine";
      osc.frequency.setValueAtTime(523.25, now); // C5
      osc.frequency.setValueAtTime(659.25, now + 0.07); // E5
      osc.frequency.setValueAtTime(783.99, now + 0.14); // G5
      gain.gain.setValueAtTime(0.12, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.28);
      osc.start(now);
      osc.stop(now + 0.28);
    } else if (type === "deny") {
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(220, now);
      osc.frequency.setValueAtTime(180, now + 0.09);
      gain.gain.setValueAtTime(0.1, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.18);
      osc.start(now);
      osc.stop(now + 0.18);
    }
  } catch {
    // Audio autoplay or web audio restriction fallback
  }
}

// Coucou Interactive Mascot Avatar Component
const CoucouMascot: React.FC<{
  mood?: "idle" | "happy" | "eating" | "alert" | "thinking";
  isHovered?: boolean;
}> = ({ mood = "idle", isHovered = false }) => {
  const [blink, setBlink] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => {
      setBlink(true);
      setTimeout(() => setBlink(false), 160);
    }, 3800 + Math.random() * 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div
      style={{
        position: "relative",
        width: 64,
        height: 64,
        borderRadius: 16,
        overflow: "hidden",
        background: "radial-gradient(circle at 50% 40%, #1e1e28 0%, #0c0d12 100%)",
        border: "1px solid rgba(255, 255, 255, 0.12)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        boxShadow: "inset 0 1px 1px rgba(255,255,255,0.2), 0 4px 14px rgba(0,0,0,0.4)",
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
            "radial-gradient(1px 1px at 20% 30%, rgba(255,255,255,0.7) 100%, transparent), radial-gradient(1.5px 1.5px at 75% 25%, rgba(255,255,255,0.8) 100%, transparent), radial-gradient(1px 1px at 85% 75%, rgba(255,255,255,0.6) 100%, transparent), radial-gradient(1.5px 1.5px at 35% 80%, rgba(255,255,255,0.5) 100%, transparent)",
          opacity: 0.65,
        }}
      />

      {/* SVG Coucou / Hina Character */}
      <svg
        width="46"
        height="46"
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
            ry: mood === "eating" ? [30, 33, 30] : [30, 29, 30],
            cy: mood === "happy" ? [54, 51, 54] : [54, 55, 54],
          }}
          transition={{ repeat: Infinity, duration: mood === "happy" ? 1.2 : 2.8, ease: "easeInOut" }}
        />

        {/* Anime Cheeks (Blush) */}
        <ellipse cx="28" cy="58" rx="5" ry="3" fill="#ffb4c8" opacity="0.6" />
        <ellipse cx="72" cy="58" rx="5" ry="3" fill="#ffb4c8" opacity="0.6" />

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
          <path d="M 44 56 Q 50 68 56 56 Z" fill="#ff5a82" />
        ) : mood === "happy" ? (
          <path d="M 45 56 Q 50 62 55 56" stroke="#121215" strokeWidth="3" strokeLinecap="round" fill="none" />
        ) : (
          // Subtle neutral/cute mouth
          <path d="M 47 57 Q 50 59 53 57" stroke="#121215" strokeWidth="2.5" strokeLinecap="round" fill="none" />
        )}

        {/* Tiny waving hands on hover or celebrate */}
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
  isThinking = false,
  activeProviderModel,
  companionName = "Hina",
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [activeTab, setActiveTab] = useState<"agent" | "chat" | "stripe" | "upload">("agent");
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [isDraggingFile, setIsDraggingFile] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [chatInput, setChatInput] = useState("");
  const [chatResponse, setChatResponse] = useState<string | null>(null);
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);
  const [selectedModel, setSelectedModel] = useState("claude-sonnet-4-6");
  const [isHovered, setIsHovered] = useState(false);
  const [simulatedStepIndex, setSimulatedStepIndex] = useState(2);

  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-expand island when interactive permission is requested
  useEffect(() => {
    if (pendingApproval) {
      setIsExpanded(true);
      setActiveTab("agent");
      if (soundEnabled) playUiSound("whoosh");
    }
  }, [pendingApproval, soundEnabled]);

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
        handleFileDropped(file.name);
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

  const handleFileDropped = (fileName: string) => {
    setIsExpanded(true);
    setActiveTab("upload");
    setUploadedFileName(fileName);
    setUploadProgress(0);
    if (soundEnabled) playUiSound("pop");

    // Simulate animated upload progress bar matching video 00:30
    let current = 0;
    const interval = setInterval(() => {
      current += 20;
      setUploadProgress(current);
      if (current >= 100) {
        clearInterval(interval);
        if (soundEnabled) playUiSound("success");
      }
    }, 150);
  };

  const handleSendQuickChat = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!chatInput.trim()) return;
    if (soundEnabled) playUiSound("pop");

    const query = chatInput.trim();
    setChatInput("");

    if (onSendMessage) {
      onSendMessage(query);
    }

    // Immediate inline feedback matching video 00:38
    setChatResponse("The total is €1,240 excl. VAT (€1,488 incl. VAT) for Atelier Brun — valid until October 30.");
  };

  const toggleSound = () => {
    setSoundEnabled((prev) => {
      const next = !prev;
      if (next) playUiSound("pop");
      return next;
    });
  };

  // Check if active agent steps are present
  const isAgentActive = agentSteps.some((s) => s.status === "active" || s.status === "pending") || Boolean(pendingApproval);

  return (
    <div
      ref={containerRef}
      style={{
        position: "fixed",
        top: 12,
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 9999,
        fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'SF Pro Display', 'Segoe UI', sans-serif",
      }}
    >
      <motion.div
        layout
        transition={{ type: "spring", stiffness: 420, damping: 32 }}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        style={{
          background: isDark ? "rgba(10, 10, 13, 0.94)" : "rgba(255, 255, 255, 0.96)",
          backdropFilter: "blur(24px)",
          WebkitBackdropFilter: "blur(24px)",
          border: isDraggingFile
            ? "2px dashed #10b981"
            : isDark
            ? "1px solid rgba(255, 255, 255, 0.12)"
            : "1px solid rgba(0, 0, 0, 0.1)",
          boxShadow: isDark
            ? "0 12px 48px rgba(0, 0, 0, 0.65), 0 0 0 1px rgba(255,255,255,0.06)"
            : "0 12px 40px rgba(0, 0, 0, 0.15), 0 0 0 1px rgba(0,0,0,0.04)",
          borderRadius: isExpanded ? 24 : 32,
          padding: isExpanded ? "12px 16px" : "6px 14px",
          width: isExpanded ? 640 : isAgentActive ? 340 : 260,
          color: isDark ? "#ffffff" : "#111827",
          display: "flex",
          flexDirection: "column",
          gap: isExpanded ? 10 : 0,
          overflow: "hidden",
        }}
      >
        {/* ── Top Bar / Header of Dynamic Island ──────────────────────── */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            width: "100%",
            height: isExpanded ? 32 : 36,
          }}
        >
          {/* Left: Quick Navigation Icons */}
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <button
              type="button"
              onClick={() => {
                if (soundEnabled) playUiSound("click");
                setIsExpanded((v) => !v);
              }}
              title="Home / Expand Island"
              style={{
                background: "transparent",
                border: "none",
                color: isDark ? "rgba(255, 255, 255, 0.7)" : "#4b5563",
                cursor: "pointer",
                padding: 4,
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
                if (soundEnabled) playUiSound("click");
                setIsExpanded(true);
                setActiveTab("chat");
              }}
              title="Quick Chat"
              style={{
                background: activeTab === "chat" && isExpanded ? "rgba(236,72,153,0.2)" : "transparent",
                border: "none",
                color: activeTab === "chat" && isExpanded ? "#ec4899" : isDark ? "rgba(255,255,255,0.7)" : "#4b5563",
                cursor: "pointer",
                padding: 4,
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
                if (soundEnabled) playUiSound("pop");
                onNewChat?.();
              }}
              title="New Session (+)"
              style={{
                background: "transparent",
                border: "none",
                color: isDark ? "rgba(255, 255, 255, 0.7)" : "#4b5563",
                cursor: "pointer",
                padding: 4,
                display: "flex",
                alignItems: "center",
                borderRadius: 8,
              }}
            >
              <Plus size={15} />
            </button>
          </div>

          {/* Center Mascot (When Collapsed) */}
          {!isExpanded && (
            <div
              onClick={() => {
                if (soundEnabled) playUiSound("whoosh");
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
                  width: 24,
                  height: 24,
                  borderRadius: 12,
                  background: "radial-gradient(circle, #ec4899 0%, #a855f7 100%)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  boxShadow: "0 0 10px rgba(236,72,153,0.5)",
                }}
              >
                <span style={{ fontSize: 11, fontWeight: 800, color: "#fff" }}>✦</span>
              </div>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  letterSpacing: "0.02em",
                  color: isDark ? "#ffffff" : "#111827",
                }}
              >
                {isAgentActive
                  ? "Hina Claude Code"
                  : isDraggingFile
                  ? "Drop File Here"
                  : `${companionName} Island`}
              </span>
            </div>
          )}

          {/* Right: Sound, Settings, Expand/Collapse */}
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <button
              type="button"
              onClick={toggleSound}
              title={soundEnabled ? "Mute UI Sounds" : "Enable UI Sounds"}
              style={{
                background: "transparent",
                border: "none",
                color: isDark ? "rgba(255, 255, 255, 0.65)" : "#6b7280",
                cursor: "pointer",
                padding: 4,
                display: "flex",
                alignItems: "center",
                borderRadius: 8,
              }}
            >
              {soundEnabled ? <Volume2 size={15} /> : <VolumeX size={15} />}
            </button>

            <button
              type="button"
              onClick={() => {
                if (soundEnabled) playUiSound("click");
                onOpenSettings?.();
              }}
              title="Settings"
              style={{
                background: "transparent",
                border: "none",
                color: isDark ? "rgba(255, 255, 255, 0.65)" : "#6b7280",
                cursor: "pointer",
                padding: 4,
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
                if (soundEnabled) playUiSound("whoosh");
                setIsExpanded((v) => !v);
              }}
              title={isExpanded ? "Collapse Island" : "Expand Island"}
              style={{
                background: "transparent",
                border: "none",
                color: isDark ? "rgba(255, 255, 255, 0.75)" : "#374151",
                cursor: "pointer",
                padding: 4,
                display: "flex",
                alignItems: "center",
                borderRadius: 8,
              }}
            >
              {isExpanded ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
            </button>
          </div>
        </div>

        {/* ── Expanded Island Content ─────────────────────────────────── */}
        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              style={{ display: "flex", gap: 14, paddingTop: 4 }}
            >
              {/* Left Column: Mascot Avatar */}
              <div
                onClick={() => {
                  if (soundEnabled) playUiSound("pop");
                }}
              >
                <CoucouMascot
                  mood={isDraggingFile ? "eating" : pendingApproval ? "alert" : isThinking ? "thinking" : "happy"}
                  isHovered={isHovered}
                />
              </div>

              {/* Center & Right Column: Interactive Hub */}
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 10, minWidth: 0 }}>
                {/* 1. Drag & Drop File Zone (When File Dragged) */}
                {isDraggingFile || activeTab === "upload" ? (
                  <div
                    style={{
                      background: "rgba(16, 185, 129, 0.08)",
                      border: "1px solid rgba(16, 185, 129, 0.3)",
                      borderRadius: 14,
                      padding: "10px 14px",
                      display: "flex",
                      flexDirection: "column",
                      gap: 8,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <span style={{ fontSize: 12, fontWeight: 700, color: "#10b981" }}>
                        Drop your files here (PDF, Images, Code, Docs)
                      </span>
                      {uploadedFileName && (
                        <span style={{ fontSize: 11, color: "rgba(255,255,255,0.7)" }}>
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
                        <span style={{ fontSize: 11, fontWeight: 600, color: "#10b981" }}>
                          {uploadProgress}%
                        </span>
                      </div>
                    )}

                    {uploadProgress === 100 && (
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
                        <button
                          type="button"
                          onClick={() => {
                            if (soundEnabled) playUiSound("click");
                            setActiveTab("chat");
                            setChatInput(`Ask a question about ${uploadedFileName}: `);
                          }}
                          style={{
                            background: "#10b981",
                            color: "#fff",
                            border: "none",
                            borderRadius: 8,
                            padding: "4px 10px",
                            fontSize: 11,
                            fontWeight: 650,
                            cursor: "pointer",
                          }}
                        >
                          Ask a question about it
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
                            color: "rgba(255,255,255,0.7)",
                            borderRadius: 8,
                            padding: "4px 10px",
                            fontSize: 11,
                            cursor: "pointer",
                          }}
                        >
                          Cancel
                        </button>
                      </div>
                    )}
                  </div>
                ) : activeTab === "stripe" ? (
                  /* 2. Stripe Payments Live Financial Card (Matching Video 00:18) */
                  <div
                    style={{
                      background: "rgba(99, 91, 255, 0.12)",
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
                        <CreditCard size={14} color="#635bff" />
                        <span style={{ fontSize: 12, fontWeight: 700, color: "#fff" }}>Stripe Payments</span>
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
                        +34% live
                      </span>
                    </div>
                    <div style={{ fontSize: 18, fontWeight: 800, color: "#fff", letterSpacing: "-0.02em" }}>
                      € 4,652.50 <span style={{ fontSize: 12, fontWeight: 500, color: "rgba(255,255,255,0.6)" }}>EUR</span>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "rgba(255,255,255,0.65)" }}>
                      <span>Atelier Brun: +1,240.00</span>
                      <span>Camille R.: +49.00</span>
                      <span>Hugo M.: +19.00</span>
                    </div>
                  </div>
                ) : (
                  /* 3. Claude Code / Terminal Agent Live Monitor (Matching Video 00:08 - 00:16) */
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {/* Header Step Counter */}
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span style={{ fontSize: 12, fontWeight: 700, color: "#fff" }}>
                          ✦ {companionName} Claude Code
                        </span>
                        <span
                          style={{
                            fontSize: 10,
                            fontWeight: 700,
                            color: "rgba(255,255,255,0.5)",
                            background: "rgba(255,255,255,0.08)",
                            padding: "2px 6px",
                            borderRadius: 6,
                          }}
                        >
                          {simulatedStepIndex}/4
                        </span>
                      </div>

                      {/* Model Selector Pill */}
                      <button
                        type="button"
                        onClick={() => setModelDropdownOpen((v) => !v)}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 4,
                          background: "rgba(255,255,255,0.08)",
                          border: "1px solid rgba(255,255,255,0.12)",
                          borderRadius: 8,
                          padding: "2px 8px",
                          fontSize: 10,
                          fontWeight: 650,
                          color: "rgba(255,255,255,0.85)",
                          cursor: "pointer",
                        }}
                      >
                        <span>{selectedModel}</span>
                        <ChevronDown size={10} />
                      </button>
                    </div>

                    {/* Pending Permission Approval Gate (Video 00:12) */}
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
                            Needs permission:
                          </span>
                          <span style={{ fontSize: 11, fontFamily: "monospace", color: "#fff" }}>
                            {pendingApproval.command || pendingApproval.actionName}
                          </span>
                        </div>
                        <div style={{ display: "flex", gap: 6 }}>
                          <button
                            type="button"
                            onClick={() => {
                              if (soundEnabled) playUiSound("deny");
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
                              if (soundEnabled) playUiSound("success");
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
                    ) : (
                      /* Live Step Execution Pills */
                      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                            fontSize: 11,
                            fontFamily: "monospace",
                            background: "rgba(255,255,255,0.04)",
                            padding: "4px 8px",
                            borderRadius: 6,
                            color: "rgba(255,255,255,0.8)",
                          }}
                        >
                          <span style={{ color: "#ec4899" }}>✦</span>
                          <span>Modify • billing.ts</span>
                        </div>
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: 8,
                            fontSize: 11,
                            fontFamily: "monospace",
                            background: "rgba(255,255,255,0.04)",
                            padding: "4px 8px",
                            borderRadius: 6,
                            color: "rgba(255,255,255,0.8)",
                          }}
                        >
                          <span style={{ color: "#10b981" }}>✓</span>
                          <span>Execute • npm test (48 passed)</span>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* 4. Quick Integration Grid & Action Controls */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: 4 }}>
                  {/* Quick Launcher Icons */}
                  <div style={{ display: "flex", gap: 6 }}>
                    <button
                      type="button"
                      onClick={() => {
                        if (soundEnabled) playUiSound("click");
                        setActiveTab("stripe");
                      }}
                      style={{
                        background: activeTab === "stripe" ? "rgba(99,91,255,0.25)" : "rgba(255,255,255,0.06)",
                        border: "1px solid rgba(255,255,255,0.1)",
                        borderRadius: 8,
                        padding: "3px 8px",
                        fontSize: 11,
                        fontWeight: 600,
                        color: activeTab === "stripe" ? "#a5b4fc" : "rgba(255,255,255,0.8)",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: 4,
                      }}
                    >
                      <CreditCard size={12} />
                      <span>Stripe</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        if (soundEnabled) playUiSound("click");
                        onOpenTerminal?.();
                      }}
                      style={{
                        background: "rgba(255,255,255,0.06)",
                        border: "1px solid rgba(255,255,255,0.1)",
                        borderRadius: 8,
                        padding: "3px 8px",
                        fontSize: 11,
                        fontWeight: 600,
                        color: "rgba(255,255,255,0.8)",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: 4,
                      }}
                    >
                      <Terminal size={12} />
                      <span>Terminal</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        if (soundEnabled) playUiSound("click");
                        setActiveTab("upload");
                      }}
                      style={{
                        background: activeTab === "upload" ? "rgba(16,185,129,0.2)" : "rgba(255,255,255,0.06)",
                        border: "1px solid rgba(255,255,255,0.1)",
                        borderRadius: 8,
                        padding: "3px 8px",
                        fontSize: 11,
                        fontWeight: 600,
                        color: activeTab === "upload" ? "#10b981" : "rgba(255,255,255,0.8)",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: 4,
                      }}
                    >
                      <Upload size={12} />
                      <span>Upload</span>
                    </button>
                  </div>

                  {/* Open Terminal Execution Button */}
                  <button
                    type="button"
                    onClick={() => {
                      if (soundEnabled) playUiSound("click");
                      onOpenTerminal?.();
                    }}
                    style={{
                      background: "rgba(255,255,255,0.1)",
                      border: "none",
                      borderRadius: 8,
                      padding: "4px 10px",
                      fontSize: 11,
                      fontWeight: 600,
                      color: "#fff",
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

                {/* 5. Inline Chat Composer (Video 00:36) */}
                <form
                  onSubmit={handleSendQuickChat}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    background: "rgba(255,255,255,0.06)",
                    borderRadius: 12,
                    padding: "4px 8px",
                    border: "1px solid rgba(255,255,255,0.1)",
                  }}
                >
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Ask me anything..."
                    style={{
                      flex: 1,
                      background: "transparent",
                      border: "none",
                      outline: "none",
                      color: "#fff",
                      fontSize: 12,
                    }}
                  />
                  <button
                    type="submit"
                    style={{
                      background: chatInput.trim() ? "#ec4899" : "transparent",
                      border: "none",
                      borderRadius: 8,
                      width: 24,
                      height: 24,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "#fff",
                      cursor: "pointer",
                      opacity: chatInput.trim() ? 1 : 0.4,
                    }}
                  >
                    <Send size={12} />
                  </button>
                </form>

                {/* Instant Response Bubble */}
                {chatResponse && (
                  <motion.div
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    style={{
                      background: "rgba(236,72,153,0.12)",
                      border: "1px solid rgba(236,72,153,0.3)",
                      borderRadius: 10,
                      padding: "6px 10px",
                      fontSize: 11,
                      color: "#fbcfe8",
                      lineHeight: 1.4,
                    }}
                  >
                    {chatResponse}
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
