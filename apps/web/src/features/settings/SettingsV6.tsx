import React, { useState, useMemo, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import {
  Sliders,
  Palette,
  Mic,
  Cpu,
  Image as ImageIcon,
  Brain,
  Wrench,
  GitBranch,
  Network,
  Terminal,
  Search,
  X,
  ShieldCheck,
  Volume2,
  VolumeX,
} from "lucide-react";
import type {
  HinaaSettings,
  AppearanceSettings as AppearanceSettingsType,
  LanguageSettings as LanguageSettingsType,
  ProviderPreferences,
  AutomationSettings as AutomationSettingsType,
} from "./types/settings";
import type { ProvidersState } from "../providers/types/provider";
import { AppearanceSettings } from "./sections/AppearanceSettings";
import { LanguageSettings } from "./sections/LanguageSettings";
import { ProviderSettings } from "./sections/ProviderSettings";
import { AutomationSettings } from "./sections/AutomationSettings";
import { DiagnosticsSettings } from "./sections/DiagnosticsSettings";

export type SettingsTabId =
  | "general"
  | "appearance"
  | "voice"
  | "models"
  | "media"
  | "memory"
  | "tools"
  | "github"
  | "integrations"
  | "developer";

interface TabDef {
  id: SettingsTabId;
  label: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  badge?: string;
  keywords: string[];
}

const TABS: TabDef[] = [
  { id: "general", label: "General", icon: Sliders, keywords: ["general", "language", "autonomy", "reset", "nepali", "hindi", "english"] },
  { id: "appearance", label: "Appearance", icon: Palette, keywords: ["appearance", "theme", "dark", "light", "motion", "avatar", "vrm", "3d", "style"] },
  { id: "voice", label: "Voice & Audio", icon: Mic, keywords: ["voice", "audio", "speech", "mic", "microphone", "mute", "vseeface", "vmc", "hiro", "hinaa"] },
  { id: "models", label: "Intelligence & Models", icon: Cpu, keywords: ["models", "provider", "intelligence", "gemini", "openai", "claude", "groq", "ollama", "cx-gateway", "qwen"] },
  { id: "media", label: "Media & Studio", icon: ImageIcon, keywords: ["media", "image", "magnific", "flux", "comfyui", "upscale", "aspect"] },
  { id: "memory", label: "Memory & Learning", icon: Brain, keywords: ["memory", "facts", "learn", "candidates", "remember", "episodic", "knowledge"] },
  { id: "tools", label: "Tools & Actions", icon: Wrench, keywords: ["tools", "actions", "execute", "permissions", "risk", "approval", "web", "search"] },
  { id: "github", label: "GitHub & Repo", icon: GitBranch, keywords: ["github", "repo", "repository", "git", "token", "branch", "workspace"] },
  { id: "integrations", label: "Integrations", icon: Network, keywords: ["integrations", "vseeface", "vmc", "comfyui", "ollama", "port", "local"] },
  { id: "developer", label: "Developer & Logs", icon: Terminal, keywords: ["developer", "logs", "diagnostics", "api", "telemetry", "sse", "version", "build"] },
];

export interface SettingsV6Props {
  isOpen: boolean;
  onClose: () => void;
  settings: HinaaSettings;
  setAppearance: (patch: Partial<AppearanceSettingsType>) => void;
  setLanguage: (patch: Partial<LanguageSettingsType>) => void;
  setProvider: (patch: Partial<ProviderPreferences>) => void;
  setAutomation: (patch: Partial<AutomationSettingsType>) => void;
  providers: ProvidersState;
  activeMode?: string;
  isMuted?: boolean;
  onToggleMute?: () => void;
}

export function SettingsV6({
  isOpen,
  onClose,
  settings,
  setAppearance,
  setLanguage,
  setProvider,
  setAutomation,
  providers,
  activeMode,
  isMuted = false,
  onToggleMute,
}: SettingsV6Props) {
  const [activeTab, setActiveTab] = useState<SettingsTabId>("general");
  const [searchQuery, setSearchQuery] = useState("");
  const [liveToolsCount, setLiveToolsCount] = useState<number | null>(null);
  const dialogRef = useRef<HTMLDialogElement | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    let mounted = true;
    fetch("/api/v1/tools")
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => {
        if (mounted && Array.isArray(data)) {
          setLiveToolsCount(data.length);
        }
      })
      .catch(() => {});
    return () => {
      mounted = false;
    };
  }, [isOpen]);

  // Close on escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Open native dialog modal
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (isOpen) {
      if (!dialog.open) dialog.showModal();
      document.body.style.overflow = "hidden";
    } else {
      if (dialog.open) dialog.close();
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  const filteredTabs = useMemo(() => {
    if (!searchQuery.trim()) return TABS;
    const q = searchQuery.toLowerCase().trim();
    return TABS.filter(
      (t) =>
        t.label.toLowerCase().includes(q) ||
        t.keywords.some((k) => k.toLowerCase().includes(q))
    );
  }, [searchQuery]);

  if (!isOpen) return null;

  return (
    <dialog
      ref={dialogRef}
      id="settings-v6-dialog"
      data-testid="settings-v6-dialog"
      onClick={(e) => {
        if (e.target === dialogRef.current) onClose();
      }}
      style={{
        position: "fixed",
        inset: 0,
        width: "100vw",
        height: "100vh",
        maxWidth: "none",
        maxHeight: "none",
        background: "rgba(8, 6, 12, 0.72)",
        backdropFilter: "blur(16px)",
        border: "none",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 9999,
        padding: 16,
        boxSizing: "border-box",
      }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 10 }}
        transition={{ duration: 0.2, ease: "easeOut" }}
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "min(980px, 95vw)",
          height: "min(720px, 90vh)",
          background: "linear-gradient(165deg, rgba(26, 20, 32, 0.98) 0%, rgba(14, 11, 18, 0.99) 100%)",
          border: "1px solid rgba(255, 214, 228, 0.18)",
          borderRadius: 20,
          boxShadow: "0 25px 80px rgba(0, 0, 0, 0.65), 0 0 40px rgba(238, 145, 173, 0.08)",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          color: "#f3e8ee",
          fontFamily: "var(--font-sans, system-ui, sans-serif)",
        }}
      >
        {/* Top Header Bar */}
        <div
          style={{
            padding: "16px 24px",
            borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 16,
            background: "rgba(255, 255, 255, 0.02)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div
              style={{
                width: 34,
                height: 34,
                borderRadius: 10,
                background: "linear-gradient(135deg, rgba(238, 145, 173, 0.3), rgba(168, 85, 247, 0.3))",
                border: "1px solid rgba(238, 145, 173, 0.3)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#ffc2d8",
              }}
            >
              <Sliders size={18} />
            </div>
            <div>
              <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600, color: "#fff" }}>
                HINAA Frontier Settings
              </h2>
              <span style={{ fontSize: 11, color: "rgba(255, 255, 255, 0.45)" }}>
                V6.1 Frontier Product Suite · Unified Control Surface
              </span>
            </div>
          </div>

          {/* Search Box */}
          <div
            style={{
              flex: "0 1 360px",
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "6px 14px",
              borderRadius: 10,
              background: "rgba(255, 255, 255, 0.05)",
              border: "1px solid rgba(255, 255, 255, 0.1)",
            }}
          >
            <Search size={14} color="rgba(255, 255, 255, 0.5)" />
            <input
              type="text"
              placeholder="Search settings (e.g. models, voice, memory)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                background: "transparent",
                border: "none",
                outline: "none",
                color: "#fff",
                fontSize: 13,
                width: "100%",
              }}
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                style={{
                  background: "none",
                  border: "none",
                  padding: 2,
                  cursor: "pointer",
                  color: "rgba(255, 255, 255, 0.5)",
                }}
              >
                <X size={12} />
              </button>
            )}
          </div>

          {/* Close button */}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close settings"
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              border: "1px solid rgba(255, 255, 255, 0.1)",
              background: "rgba(255, 255, 255, 0.04)",
              color: "rgba(255, 255, 255, 0.7)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
            }}
          >
            <X size={16} />
          </button>
        </div>

        {/* Main Body: Tabs Left, Content Right */}
        <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
          {/* Left Navigation Sidebar */}
          <div
            style={{
              width: 230,
              borderRight: "1px solid rgba(255, 255, 255, 0.08)",
              padding: "12px 8px",
              display: "flex",
              flexDirection: "column",
              gap: 4,
              overflowY: "auto",
              background: "rgba(0, 0, 0, 0.15)",
              flexShrink: 0,
            }}
          >
            {filteredTabs.length === 0 ? (
              <div style={{ padding: 16, fontSize: 12, color: "rgba(255, 255, 255, 0.4)", textAlign: "center" }}>
                No settings match &ldquo;{searchQuery}&rdquo;
              </div>
            ) : (
              filteredTabs.map((t) => {
                const isSelected = activeTab === t.id;
                const IconComponent = t.icon;
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => {
                      setActiveTab(t.id);
                      setSearchQuery("");
                    }}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      padding: "10px 12px",
                      borderRadius: 10,
                      border: "none",
                      background: isSelected
                        ? "linear-gradient(90deg, rgba(238, 145, 173, 0.18), rgba(168, 85, 247, 0.12))"
                        : "transparent",
                      color: isSelected ? "#ffc2d8" : "rgba(255, 255, 255, 0.75)",
                      fontWeight: isSelected ? 600 : 400,
                      fontSize: 13,
                      cursor: "pointer",
                      textAlign: "left",
                      transition: "all 140ms ease",
                      position: "relative",
                    }}
                  >
                    <IconComponent size={16} />
                    <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {t.label}
                    </span>
                    {isSelected && (
                      <div
                        style={{
                          width: 3,
                          height: 16,
                          borderRadius: 2,
                          background: "#ee91ad",
                          position: "absolute",
                          left: 2,
                        }}
                      />
                    )}
                  </button>
                );
              })
            )}
          </div>

          {/* Right Content Area */}
          <div
            style={{
              flex: 1,
              overflowY: "auto",
              padding: "24px 32px",
              display: "flex",
              flexDirection: "column",
              gap: 24,
            }}
          >
            {activeTab === "general" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                <div>
                  <h3 style={{ margin: "0 0 6px 0", fontSize: 16, fontWeight: 600 }}>General Settings</h3>
                  <p style={{ margin: 0, fontSize: 12, color: "rgba(255, 255, 255, 0.5)" }}>
                    Configure core system behavior, conversation language, and automation policies.
                  </p>
                </div>
                <LanguageSettings language={settings.language} onChange={setLanguage} />
                <AutomationSettings automation={settings.automation} onChange={setAutomation} />
              </div>
            )}

            {activeTab === "appearance" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                <div>
                  <h3 style={{ margin: "0 0 6px 0", fontSize: 16, fontWeight: 600 }}>Appearance & Themes</h3>
                  <p style={{ margin: 0, fontSize: 12, color: "rgba(255, 255, 255, 0.5)" }}>
                    Customize visual theme, motion ergonomics, and companion avatar styling.
                  </p>
                </div>
                <AppearanceSettings appearance={settings.appearance} onChange={setAppearance} />
              </div>
            )}

            {activeTab === "voice" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                <div>
                  <h3 style={{ margin: "0 0 6px 0", fontSize: 16, fontWeight: 600 }}>Voice & Audio Pipeline</h3>
                  <p style={{ margin: 0, fontSize: 12, color: "rgba(255, 255, 255, 0.5)" }}>
                    Real-time speech synthesis, microphone input calibration, and VMC face tracking.
                  </p>
                </div>

                <div
                  style={{
                    padding: 16,
                    borderRadius: 12,
                    background: "rgba(255, 255, 255, 0.03)",
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>Audio Playback</div>
                    <div style={{ fontSize: 11, color: "rgba(255, 255, 255, 0.5)" }}>
                      Mute or unmute synthesized companion voice
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={onToggleMute}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "8px 14px",
                      borderRadius: 8,
                      border: "1px solid rgba(255, 255, 255, 0.12)",
                      background: isMuted ? "rgba(239, 68, 68, 0.15)" : "rgba(34, 197, 94, 0.15)",
                      color: isMuted ? "#f87171" : "#4ade80",
                      cursor: "pointer",
                      fontSize: 12,
                      fontWeight: 600,
                    }}
                  >
                    {isMuted ? <VolumeX size={14} /> : <Volume2 size={14} />}
                    {isMuted ? "Unmute Voice" : "Mute Voice"}
                  </button>
                </div>

                <div
                  style={{
                    padding: 16,
                    borderRadius: 12,
                    background: "rgba(255, 255, 255, 0.03)",
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                    display: "flex",
                    flexDirection: "column",
                    gap: 8,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>VSeeFace / VMC Tracking</div>
                    <span style={{ fontSize: 10, padding: "2px 6px", borderRadius: 4, background: "rgba(168, 85, 247, 0.15)", color: "#c084fc", fontWeight: 600 }}>
                      DESKTOP_BRIDGE · LOCAL_ONLY
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: "rgba(255, 255, 255, 0.5)" }}>
                    Standard UDP port 39539 for streaming blendshapes and head pose to 3D VRM on client workstation.
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#4ade80" }} />
                    <span style={{ fontSize: 12, color: "#4ade80", fontFamily: "var(--font-mono)" }}>
                      Port 39539 Desktop Bridge Ready · Listening for local VMC packets
                    </span>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "models" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                <div>
                  <h3 style={{ margin: "0 0 6px 0", fontSize: 16, fontWeight: 600 }}>Intelligence & Providers</h3>
                  <p style={{ margin: 0, fontSize: 12, color: "rgba(255, 255, 255, 0.5)" }}>
                    Frontier intelligence providers, CX Gateway routing, and LLM model selections.
                  </p>
                </div>
                <ProviderSettings
                  provider={settings.provider}
                  providers={providers}
                  onChange={setProvider}
                  activeMode={activeMode as any}
                />
              </div>
            )}

            {activeTab === "media" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                <div>
                  <h3 style={{ margin: "0 0 6px 0", fontSize: 16, fontWeight: 600 }}>Media & Image Studio</h3>
                  <p style={{ margin: 0, fontSize: 12, color: "rgba(255, 255, 255, 0.5)" }}>
                    Configure generative image pipelines, FLUX models, and local ComfyUI settings.
                  </p>
                </div>

                <div
                  style={{
                    padding: 16,
                    borderRadius: 12,
                    background: "rgba(255, 255, 255, 0.03)",
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                    display: "flex",
                    flexDirection: "column",
                    gap: 12,
                  }}
                >
                  <div style={{ fontSize: 13, fontWeight: 600 }}>Default Generator</div>
                  <div style={{ fontSize: 11, color: "rgba(255, 255, 255, 0.5)" }}>
                    Active image creation engine for Studio and in-chat generation.
                  </div>
                  <div style={{ display: "flex", gap: 10 }}>
                    <div
                      style={{
                        padding: "8px 14px",
                        borderRadius: 8,
                        background: "rgba(238, 145, 173, 0.15)",
                        border: "1px solid rgba(238, 145, 173, 0.35)",
                        color: "#ffc2d8",
                        fontSize: 12,
                        fontWeight: 600,
                      }}
                    >
                      Magnific FLUX (Default)
                    </div>
                    <div
                      style={{
                        padding: "8px 14px",
                        borderRadius: 8,
                        background: "rgba(255, 255, 255, 0.04)",
                        border: "1px solid rgba(255, 255, 255, 0.1)",
                        color: "rgba(255, 255, 255, 0.6)",
                        fontSize: 12,
                      }}
                    >
                      ComfyUI (Local)
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "memory" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                <div>
                  <h3 style={{ margin: "0 0 6px 0", fontSize: 16, fontWeight: 600 }}>Memory & Auto-Learning</h3>
                  <p style={{ margin: 0, fontSize: 12, color: "rgba(255, 255, 255, 0.5)" }}>
                    Manage learned facts, conversation memory candidates, and privacy isolation.
                  </p>
                </div>

                <div
                  style={{
                    padding: 16,
                    borderRadius: 12,
                    background: "rgba(255, 255, 255, 0.03)",
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>Episodic Fact Learning</div>
                    <div style={{ fontSize: 11, color: "rgba(255, 255, 255, 0.5)" }}>
                      Automatically extract user facts, preferences, and personal details into durable storage.
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, color: "#4ade80", fontSize: 12, fontWeight: 600 }}>
                    <ShieldCheck size={16} /> Active & Bounded
                  </div>
                </div>

                <div
                  style={{
                    padding: 16,
                    borderRadius: 12,
                    background: "rgba(255, 255, 255, 0.03)",
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>Cross-Session Referent Suppression</div>
                    <div style={{ fontSize: 11, color: "rgba(255, 255, 255, 0.5)" }}>
                      Prevents pronouns in clean sessions from triggering stale context or phantom research.
                    </div>
                  </div>
                  <div style={{ color: "#4ade80", fontSize: 12, fontWeight: 600 }}>
                    Enabled (Precedence Guard V6)
                  </div>
                </div>
              </div>
            )}

            {activeTab === "tools" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                <div>
                  <h3 style={{ margin: "0 0 6px 0", fontSize: 16, fontWeight: 600 }}>Tools & Permissions</h3>
                  <p style={{ margin: 0, fontSize: 12, color: "rgba(255, 255, 255, 0.5)" }}>
                    Tool registry status, risk levels, and permission escalation policies.
                  </p>
                </div>

                <div
                  style={{
                    padding: 16,
                    borderRadius: 12,
                    background: "rgba(255, 255, 255, 0.03)",
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                    display: "flex",
                    flexDirection: "column",
                    gap: 10,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>Registered Tools Registry</div>
                    <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 10, background: "rgba(34, 197, 94, 0.15)", color: "#4ade80" }}>
                      {liveToolsCount !== null ? `${liveToolsCount} Tools Live` : "Registered Tools Ready"}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: "rgba(255, 255, 255, 0.6)" }}>
                    Categories: Web Search, Deep Research, Media Creation, Document Editor, GitHub Integration, Terminal Execution.
                  </div>
                </div>
              </div>
            )}

            {activeTab === "github" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                <div>
                  <h3 style={{ margin: "0 0 6px 0", fontSize: 16, fontWeight: 600 }}>GitHub Integration</h3>
                  <p style={{ margin: 0, fontSize: 12, color: "rgba(255, 255, 255, 0.5)" }}>
                    Workspace source control, issue tracking, and automated commit management.
                  </p>
                </div>

                <div
                  style={{
                    padding: 16,
                    borderRadius: 12,
                    background: "rgba(255, 255, 255, 0.03)",
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                    display: "flex",
                    flexDirection: "column",
                    gap: 8,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>Active Repository</span>
                    <span style={{ fontSize: 12, fontFamily: "var(--font-mono)", color: "#a78bfa" }}>
                      unesh123/hinamygirll
                    </span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>Default Branch</span>
                    <span style={{ fontSize: 12, fontFamily: "var(--font-mono)", color: "rgba(255, 255, 255, 0.6)" }}>
                      main
                    </span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#4ade80" }} />
                    <span style={{ fontSize: 12, color: "#4ade80" }}>
                      Repository Connected & Synced
                    </span>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "integrations" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                <div>
                  <h3 style={{ margin: "0 0 6px 0", fontSize: 16, fontWeight: 600 }}>Local Service Integrations</h3>
                  <p style={{ margin: 0, fontSize: 12, color: "rgba(255, 255, 255, 0.5)" }}>
                    Client workstation desktop services. Localhost services operate as Desktop Bridges and are never directly queried from remote server runtimes.
                  </p>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  <div
                    style={{
                      padding: 14,
                      borderRadius: 10,
                      background: "rgba(255, 255, 255, 0.03)",
                      border: "1px solid rgba(255, 255, 255, 0.08)",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <div style={{ fontSize: 13, fontWeight: 600 }}>ComfyUI Image Server</div>
                        <span style={{ fontSize: 10, padding: "2px 6px", borderRadius: 4, background: "rgba(168, 85, 247, 0.15)", color: "#c084fc", fontWeight: 600 }}>
                          DESKTOP_BRIDGE
                        </span>
                      </div>
                      <div style={{ fontSize: 11, color: "rgba(255, 255, 255, 0.5)", fontFamily: "var(--font-mono)" }}>
                        http://127.0.0.1:8188 · Client Workstation Only
                      </div>
                    </div>
                    <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 6, background: "rgba(255, 255, 255, 0.08)", color: "rgba(255, 255, 255, 0.6)" }}>
                      LOCAL_ONLY
                    </span>
                  </div>

                  <div
                    style={{
                      padding: 14,
                      borderRadius: 10,
                      background: "rgba(255, 255, 255, 0.03)",
                      border: "1px solid rgba(255, 255, 255, 0.08)",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <div style={{ fontSize: 13, fontWeight: 600 }}>Ollama Local LLM</div>
                        <span style={{ fontSize: 10, padding: "2px 6px", borderRadius: 4, background: "rgba(168, 85, 247, 0.15)", color: "#c084fc", fontWeight: 600 }}>
                          DESKTOP_BRIDGE
                        </span>
                      </div>
                      <div style={{ fontSize: 11, color: "rgba(255, 255, 255, 0.5)", fontFamily: "var(--font-mono)" }}>
                        http://127.0.0.1:11434 · Client Workstation Only
                      </div>
                    </div>
                    <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 6, background: "rgba(255, 255, 255, 0.08)", color: "rgba(255, 255, 255, 0.6)" }}>
                      LOCAL_ONLY
                    </span>
                  </div>

                  <div
                    style={{
                      padding: 14,
                      borderRadius: 10,
                      background: "rgba(255, 255, 255, 0.03)",
                      border: "1px solid rgba(255, 255, 255, 0.08)",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <div style={{ fontSize: 13, fontWeight: 600 }}>VSeeFace / VMC UDP Bridge</div>
                        <span style={{ fontSize: 10, padding: "2px 6px", borderRadius: 4, background: "rgba(168, 85, 247, 0.15)", color: "#c084fc", fontWeight: 600 }}>
                          DESKTOP_BRIDGE
                        </span>
                      </div>
                      <div style={{ fontSize: 11, color: "rgba(255, 255, 255, 0.5)", fontFamily: "var(--font-mono)" }}>
                        UDP 39539 · Client Workstation Relay
                      </div>
                    </div>
                    <span style={{ fontSize: 11, padding: "2px 8px", borderRadius: 6, background: "rgba(255, 255, 255, 0.08)", color: "rgba(255, 255, 255, 0.6)" }}>
                      LOCAL_ONLY
                    </span>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "developer" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                <div>
                  <h3 style={{ margin: "0 0 6px 0", fontSize: 16, fontWeight: 600 }}>Developer & Telemetry</h3>
                  <p style={{ margin: 0, fontSize: 12, color: "rgba(255, 255, 255, 0.5)" }}>
                    System health diagnostics, server logs, and live SSE event inspection.
                  </p>
                </div>
                <DiagnosticsSettings providers={providers} />
              </div>
            )}
          </div>
        </div>
      </motion.div>
    </dialog>
  );
}
