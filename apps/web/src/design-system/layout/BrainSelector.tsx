import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Brain, ChevronDown, Check, Sparkles, RefreshCw, Settings2 } from "lucide-react";
import type { ProviderPreferenceMode } from "../../features/settings/types/settings";
import type { ProviderMode, ProviderOption } from "../../features/providers/types/provider";

interface BrainSelectorProps {
  currentMode: ProviderPreferenceMode;
  currentModel?: string | null;
  providerOptions: ProviderOption[];
  getModelOptions: (mode: ProviderMode) => Array<{ id: string; label: string; isDefault: boolean }>;
  onSelectProvider: (mode: ProviderPreferenceMode, modelId?: string | null) => void;
  onReprobeCx?: () => Promise<void>;
  onOpenSettings?: () => void;
}

interface ProviderMeta {
  label: string;
  desc: string;
  icon: string;
  featured?: boolean;
}

const FEATURED_PROVIDERS: Record<string, ProviderMeta> = {
  auto: { label: "Auto", desc: "Intelligently routes to fastest healthy model", icon: "✨", featured: true },
  "cx-gateway": { label: "CX Gateway", desc: "cx/gpt-5.6-sol — private premium gateway", icon: "⚡", featured: true },
  real: { label: "Gemini", desc: "Google Gemini Multimodal Flash", icon: "🌐", featured: true },
  claude: { label: "Claude", desc: "Anthropic Messages / Deep Reasoning", icon: "🧠", featured: true },
  qwen: { label: "Qwen", desc: "Multilingual & Coding Specialist", icon: "🏮", featured: true },
  ollama: { label: "Ollama (Local)", desc: "Fast uncensored local models (dolphin-mistral, etc.)", icon: "🦙", featured: true },
  local: { label: "Local", desc: "Zero-credit on-device model (offline)", icon: "💻", featured: true },
  mock: { label: "Demo", desc: "Deterministic testing without API keys", icon: "🧪", featured: true },
};

export function BrainSelector({
  currentMode,
  currentModel,
  providerOptions,
  getModelOptions,
  onSelectProvider,
  onReprobeCx,
  onOpenSettings,
}: BrainSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isReprobing, setIsReprobing] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [isOpen]);

  const activeOption = providerOptions.find((p) => p.mode === currentMode);
  const activeLabel =
    currentMode === "auto"
      ? "Auto"
      : activeOption?.label || currentMode;

  const isHealthy =
    currentMode === "auto"
      ? providerOptions.some((p) => p.available)
      : activeOption?.available;

  const handleReprobe = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!onReprobeCx || isReprobing) return;
    setIsReprobing(true);
    try {
      await onReprobeCx();
    } finally {
      setIsReprobing(false);
    }
  };

  return (
    <div ref={containerRef} style={{ position: "relative", zIndex: 100 }}>
      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 7,
          background: "var(--bg-surface-raised, #ffffff)",
          border: `1px solid ${isOpen ? "var(--accent)" : "var(--border-default, #e5e7eb)"}`,
          borderRadius: "var(--radius-pill, 9999px)",
          padding: "4px 12px",
          color: "var(--text-primary, #111827)",
          fontSize: 12,
          fontWeight: 600,
          cursor: "pointer",
          boxShadow: isOpen ? "0 0 0 2px var(--accent-glow, rgba(244,114,182,0.25))" : "var(--shadow-sm)",
          transition: "all 0.15s ease",
          outline: "none",
        }}
        aria-expanded={isOpen}
        title="Switch AI Brain & Provider"
      >
        <span
          style={{
            width: 7,
            height: 7,
            borderRadius: "50%",
            background: isHealthy ? "var(--success, #10b981)" : "var(--danger, #ef4444)",
            boxShadow: isHealthy ? "0 0 6px var(--success, #10b981)" : "none",
          }}
        />
        <Brain size={13} color="var(--accent, #ec4899)" />
        <span style={{ color: "var(--text-secondary, #4b5563)", fontWeight: 500 }}>Brain:</span>
        <span style={{ color: "var(--text-primary, #111827)", fontWeight: 700 }}>
          {activeLabel}
        </span>
        {currentModel && currentMode !== "auto" && (
          <span
            style={{
              fontSize: 10,
              background: "var(--accent-pale, #fdf2f8)",
              color: "var(--accent, #ec4899)",
              padding: "1px 5px",
              borderRadius: 6,
              maxWidth: 90,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {currentModel.replace("cx/", "")}
          </span>
        )}
        <ChevronDown
          size={12}
          style={{
            transform: isOpen ? "rotate(180deg)" : "rotate(0deg)",
            transition: "transform 0.2s ease",
            color: "var(--text-tertiary, #9ca3af)",
          }}
        />
      </button>

      {/* Popover Card */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 6, scale: 0.98 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            style={{
              position: "absolute",
              top: "calc(100% + 8px)",
              right: 0,
              width: 320,
              maxHeight: "80vh",
              overflowY: "auto",
              background: "var(--bg-surface-raised, #ffffff)",
              border: "1px solid var(--border-default, #e5e7eb)",
              borderRadius: "var(--radius-xl, 16px)",
              boxShadow: "0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)",
              padding: "10px",
              display: "flex",
              flexDirection: "column",
              gap: 4,
            }}
          >
            {/* Header */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "4px 8px 8px",
                borderBottom: "1px solid var(--border-subtle, #f3f4f6)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <Sparkles size={13} color="var(--accent, #ec4899)" />
                <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-primary, #111827)" }}>
                  Select AI Brain
                </span>
              </div>
              <span style={{ fontSize: 11, color: "var(--text-tertiary, #9ca3af)" }}>
                {providerOptions.filter((p) => p.available).length} online
              </span>
            </div>

            {/* 1. Auto Option (Default) */}
            <div
              style={{
                borderRadius: 10,
                border: currentMode === "auto" ? "1px solid var(--accent, #ec4899)" : "1px solid transparent",
                background: currentMode === "auto" ? "var(--accent-pale, #fdf2f8)" : "transparent",
                transition: "all 0.12s ease",
              }}
            >
              <button
                type="button"
                onClick={() => {
                  onSelectProvider("auto");
                  setIsOpen(false);
                }}
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "8px 10px",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  textAlign: "left",
                  outline: "none",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: "1rem" }}>✨</span>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ fontSize: 12, fontWeight: 700, color: currentMode === "auto" ? "var(--accent)" : "var(--text-primary)" }}>
                        Auto (Recommended)
                      </span>
                      <span style={{ fontSize: 10, background: "rgba(16, 185, 129, 0.12)", color: "var(--success, #059669)", padding: "1px 5px", borderRadius: 4, fontWeight: 600 }}>
                        Best Available
                      </span>
                    </div>
                    <div style={{ fontSize: 11, color: "var(--text-tertiary, #6b7280)" }}>
                      Automatically selects the fastest healthy provider
                    </div>
                  </div>
                </div>
                {currentMode === "auto" && <Check size={14} color="var(--accent)" />}
              </button>
            </div>

            {/* Separator */}
            <div style={{ height: 1, background: "var(--border-subtle, #f3f4f6)", margin: "4px 0" }} />

            {/* 2. Primary Providers List */}
            {providerOptions
              .filter((opt) => ["cx-gateway", "real", "claude", "qwen", "ollama", "local", "mock"].includes(opt.mode))
              .map((opt) => {
                const isSelected = opt.mode === currentMode;
                const meta = FEATURED_PROVIDERS[opt.mode] || { label: opt.label, desc: opt.description, icon: "🤖" };
                const isDegraded = opt.health === "degraded";
                const isOffline = !opt.available;
                const isRateLimited = (opt.health as string) === "rate_limited" || Boolean(opt.healthReason?.toLowerCase().includes("rate"));
                const models = getModelOptions(opt.mode);

                return (
                  <div
                    key={opt.mode}
                    style={{
                      borderRadius: 10,
                      border: isSelected ? "1px solid var(--accent, #ec4899)" : "1px solid transparent",
                      background: isSelected ? "var(--accent-pale, #fdf2f8)" : "transparent",
                      transition: "all 0.12s ease",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "6px 10px",
                      }}
                    >
                      <button
                        type="button"
                        disabled={isOffline}
                        onClick={() => {
                          const def = models.length > 0 ? models[0].id : null;
                          onSelectProvider(opt.mode as ProviderPreferenceMode, def);
                          setIsOpen(false);
                        }}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          background: "none",
                          border: "none",
                          cursor: isOffline ? "not-allowed" : "pointer",
                          opacity: isOffline ? 0.5 : 1,
                          textAlign: "left",
                          outline: "none",
                          flex: 1,
                          padding: 0,
                        }}
                      >
                        <span style={{ fontSize: "0.95rem" }}>{meta.icon}</span>
                        <div>
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <span style={{ fontSize: 12, fontWeight: isSelected ? 700 : 600, color: isSelected ? "var(--accent)" : "var(--text-primary)" }}>
                              {opt.label}
                            </span>

                            {/* Status Dot / Badge */}
                            {opt.available && !isDegraded && (
                              <span style={{ fontSize: 10, color: "var(--success, #059669)", display: "flex", alignItems: "center", gap: 3 }}>
                                <span style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--success, #10b981)" }} />
                                Ready
                              </span>
                            )}
                            {isDegraded && (
                              <span style={{ fontSize: 10, color: "var(--warning, #d97706)", display: "flex", alignItems: "center", gap: 3 }}>
                                <span style={{ width: 5, height: 5, borderRadius: "50%", background: "var(--warning, #f59e0b)" }} />
                                Busy
                              </span>
                            )}
                            {isRateLimited && (
                              <span style={{ fontSize: 10, color: "var(--warning, #d97706)", background: "rgba(245,158,11,0.1)", padding: "1px 4px", borderRadius: 4 }}>
                                Rate Limited
                              </span>
                            )}
                            {isOffline && (
                              <span style={{ fontSize: 10, color: "var(--danger, #dc2626)", background: "rgba(239,68,68,0.1)", padding: "1px 4px", borderRadius: 4 }}>
                                Offline
                              </span>
                            )}
                          </div>
                          <div style={{ fontSize: 11, color: "var(--text-tertiary, #6b7280)" }}>
                            {meta.desc}
                          </div>
                        </div>
                      </button>

                      {/* Right side actions: Recheck button for CX if offline or degraded, or Checkmark if selected */}
                      <div style={{ display: "flex", alignItems: "center", gap: 4, marginLeft: 6 }}>
                        {opt.mode === "cx-gateway" && onReprobeCx && (
                          <button
                            type="button"
                            onClick={handleReprobe}
                            title="Perform live probe of CX Gateway"
                            disabled={isReprobing}
                            style={{
                              padding: "2px 6px",
                              fontSize: 10,
                              borderRadius: 6,
                              border: "1px solid var(--border-default, #e5e7eb)",
                              background: "var(--bg-secondary, #f9fafb)",
                              color: "var(--text-secondary, #4b5563)",
                              cursor: "pointer",
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 3,
                            }}
                          >
                            <RefreshCw size={10} style={{ animation: isReprobing ? "spin 1s linear infinite" : "none" }} />
                            <span>{isReprobing ? "Testing..." : "Recheck"}</span>
                          </button>
                        )}

                        {isSelected && (
                          <Check size={14} color="var(--accent)" style={{ flexShrink: 0 }} />
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}

            {/* Advanced & Settings Link */}
            <div
              style={{
                marginTop: 6,
                paddingTop: 6,
                borderTop: "1px solid var(--border-subtle, #f3f4f6)",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                paddingLeft: 4,
                paddingRight: 4,
              }}
            >
              <button
                type="button"
                onClick={() => setShowAdvanced(!showAdvanced)}
                style={{
                  fontSize: 11,
                  color: "var(--text-tertiary, #6b7280)",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  padding: 0,
                }}
              >
                {showAdvanced ? "▲ Hide other models" : "▼ Other gateways"}
              </button>

              {onOpenSettings && (
                <button
                  type="button"
                  onClick={() => {
                    setIsOpen(false);
                    onOpenSettings();
                  }}
                  style={{
                    fontSize: 11,
                    fontWeight: 500,
                    color: "var(--accent, #ec4899)",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 3,
                    padding: 0,
                  }}
                >
                  <Settings2 size={11} />
                  <span>Configure keys →</span>
                </button>
              )}
            </div>

            {/* Other Gateways (Custom, OpenAI, Groq, Agent Router) when expanded */}
            {showAdvanced && (
              <div style={{ display: "flex", flexDirection: "column", gap: 3, marginTop: 4 }}>
                {providerOptions
                  .filter((opt) => !["cx-gateway", "real", "claude", "qwen", "ollama", "local", "mock"].includes(opt.mode))
                  .map((opt) => {
                    const isSelected = opt.mode === currentMode;
                    return (
                      <button
                        key={opt.mode}
                        type="button"
                        disabled={!opt.available}
                        onClick={() => {
                          onSelectProvider(opt.mode as ProviderPreferenceMode);
                          setIsOpen(false);
                        }}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          padding: "5px 8px",
                          borderRadius: 6,
                          background: isSelected ? "var(--accent-pale)" : "transparent",
                          border: "none",
                          cursor: opt.available ? "pointer" : "not-allowed",
                          opacity: opt.available ? 1 : 0.45,
                          textAlign: "left",
                          fontSize: 11,
                        }}
                      >
                        <span style={{ color: isSelected ? "var(--accent)" : "var(--text-primary)", fontWeight: isSelected ? 600 : 500 }}>
                          {opt.label}
                        </span>
                        <span style={{ fontSize: 10, color: opt.available ? "var(--success)" : "var(--text-tertiary)" }}>
                          {opt.available ? "Ready" : "Offline"}
                        </span>
                      </button>
                    );
                  })}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
