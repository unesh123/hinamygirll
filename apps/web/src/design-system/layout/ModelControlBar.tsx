import { useState, useRef, useEffect, useMemo } from "react";
import { Brain, Image as ImageIcon, Mic, ChevronDown, Check, Sparkles } from "lucide-react";
import type { ProviderPreferenceMode } from "../../features/settings/types/settings";
import type { ProviderMode, ProviderOption } from "../../features/providers/types/provider";

export interface ModelPreferences {
  brainMode: ProviderPreferenceMode;
  brainModel?: string | null;
  imageEngine: string;
  voiceEngine: string;
}

export const STORAGE_KEY_MODEL_PREFS = "hinaa-model-prefs";

export interface ModelControlBarProps {
  currentMode: ProviderPreferenceMode;
  currentModel?: string | null;
  providerOptions: ProviderOption[];
  getModelOptions: (mode: ProviderMode) => Array<{ id: string; label: string; isDefault: boolean }>;
  onSelectProvider: (mode: ProviderPreferenceMode, modelId?: string | null) => void;
  imageEngine?: string;
  onSelectImageEngine?: (engine: string) => void;
  voiceEngine?: string;
  onSelectVoiceEngine?: (engine: string) => void;
  onReprobeCx?: () => Promise<void>;
  onOpenSettings?: () => void;
  isDark?: boolean;
}

export const IMAGE_ENGINES = [
  { id: "auto", label: "Auto Engine", desc: "Best available cloud or local renderer", icon: "✨" },
  { id: "gemini-3.1-flash-image", label: "Gemini 3.1 Flash", desc: "Ultra-fast text-to-image & edit", icon: "⚡" },
  { id: "gemini-3-pro-image", label: "Gemini 3 Pro", desc: "Cinematic multi-reference composition", icon: "🎨" },
  { id: "comfyui", label: "ComfyUI SDXL", desc: "Private local GPU diffusion pipeline", icon: "💻" },
  { id: "magnific", label: "Magnific / Freepik", desc: "High-fidelity hallucinatory upscale", icon: "💎" },
];

export const VOICE_ENGINES = [
  { id: "elevenlabs", label: "ElevenLabs (Aisha / Sweet Girlfriend)", desc: "Ultra-expressive streaming sweet girlfriend neural voice (Turbo v2.5)", icon: "💖" },
  { id: "auto", label: "Auto (ElevenLabs Aisha)", desc: "Sweet expressive girlfriend neural voice (ElevenLabs Aisha / Turbo v2.5)", icon: "✨" },
  { id: "fish-audio", label: "Fish Audio Studio", desc: "State-of-the-art multilingual voice (Fish Speech 1.5)", icon: "🐟" },
  { id: "deepgram", label: "Deepgram Aura (Athena / Deep Velvety)", desc: "Deep, velvety, seductive feminine voice with natural warmth", icon: "💎" },
  { id: "deepgram-thalia", label: "Deepgram Aura (Thalia / Expressive)", desc: "Expressive feminine conversational voice", icon: "🌸" },
  { id: "deepgram-luna", label: "Deepgram Aura (Luna / Anime Cute)", desc: "Playful anime-style feminine voice", icon: "⚡" },
  { id: "deepgram-asteria", label: "Deepgram Aura (Asteria / Bright)", desc: "Bright youthful feminine voice", icon: "✨" },
  { id: "gemini-live", label: "Gemini Live", desc: "Sub-300ms bidirectional speech stream", icon: "🎙" },
  { id: "azure-speech", label: "Azure Neural", desc: "Expressive high-fidelity voices", icon: "🌐" },
  { id: "browser-native", label: "Browser Native", desc: "Zero-latency offline client TTS", icon: "🔊" },
];

export interface CanonicalProvider {
  mode: ProviderMode;
  label: string;
  defaultModel: string;
  models: Array<{ id: string; label: string; isDefault?: boolean }>;
}

export const CANONICAL_PROVIDERS: CanonicalProvider[] = [
  {
    mode: "agent-router",
    label: "🔀 Agent Router (Bynara)",
    defaultModel: "agnes-2.5-flash",
    models: [
      { id: "agnes-2.5-flash", label: "Agnes 2.5 Flash", isDefault: true },
      { id: "nemotron-3.5-lightning-free", label: "Nemotron 3.5 Lightning (Free)" },
      { id: "laguna-s-2.1", label: "Laguna S 2.1" },
      { id: "deepseek-v4-flash", label: "DeepSeek V4 Flash" },
      { id: "qwen3.8-max", label: "Qwen 3.8 Max" },
      { id: "claude-fable-5", label: "Claude Fable 5" },
      { id: "gpt-5.6-sol", label: "GPT-5.6 Sol" },
      { id: "gemini-3.8-flash-high", label: "Gemini 3.8 Flash High" },
    ],
  },
  {
    mode: "codecraft",
    label: "⚡ CodeCraft AI (Frontier)",
    defaultModel: "claude-fable-5",
    models: [
      { id: "claude-fable-5", label: "Claude Fable 5", isDefault: true },
      { id: "claude-fable-5.1", label: "Claude Fable 5.1" },
      { id: "claude-sonnet-5", label: "Claude Sonnet 5" },
      { id: "claude-opus-5", label: "Claude Opus 5" },
      { id: "claude-3-7-sonnet", label: "Claude 3.7 Sonnet" },
      { id: "gpt-5.6-sol", label: "GPT-5.6 Sol" },
      { id: "qwen3.8-max", label: "Qwen 3.8 Max" },
      { id: "kimi-k3", label: "Kimi K3" },
      { id: "glm-5.3", label: "GLM 5.3" },
    ],
  },
  {
    mode: "real",
    label: "🌐 Google Gemini Cloud",
    defaultModel: "gemini-3.5-flash",
    models: [
      { id: "gemini-3.5-flash", label: "Gemini 3.5 Flash", isDefault: true },
      { id: "gemini-3.8-flash", label: "Gemini 3.8 Flash" },
      { id: "gemini-2.5-flash-lite", label: "Gemini 2.5 Flash Lite" },
      { id: "gemini-3.5-flash-lite", label: "Gemini 3.5 Flash Lite" },
      { id: "gemini-flash-latest", label: "Gemini Flash Latest" },
      { id: "gemini-pro-latest", label: "Gemini Pro Latest" },
    ],
  },
  {
    mode: "xkiro",
    label: "⚡ XKiro AI (Free)",
    defaultModel: "qwen/qwen3.8-max:free",
    models: [
      { id: "qwen/qwen3.8-max:free", label: "Qwen 3.8 Max (Free)", isDefault: true },
      { id: "qwen/qwen3.7-flash:free", label: "Qwen 3.7 Flash (Free)" },
      { id: "deepseek/deepseek-v4.1-flash:free", label: "DeepSeek V4.1 Flash (Free)" },
      { id: "minimax/minimax-m2.7:free", label: "MiniMax M2.7 (Free)" },
    ],
  },
  {
    mode: "apmix",
    label: "⚡ APMIX.AI (Free)",
    defaultModel: "deepseek-v4-flash-free",
    models: [
      { id: "deepseek-v4-flash-free", label: "DeepSeek V4 Flash (Free)", isDefault: true },
      { id: "gpt-6-luna-free", label: "GPT-6 Luna (Free)" },
    ],
  },
  {
    mode: "claude",
    label: "🧠 Anthropic Claude",
    defaultModel: "claude-3-7-sonnet-20250219",
    models: [
      { id: "claude-opus-5.5", label: "Claude Opus 5.5 (Experiential)" },
      { id: "claude-3-7-sonnet-20250219", label: "Claude 3.7 Sonnet", isDefault: true },
      { id: "claude-haiku-4-5-20251001", label: "Claude 3.5 Haiku" },
      { id: "claude-3-opus-20240229", label: "Claude 3 Opus" },
    ],
  },

  {
    mode: "cx-gateway",
    label: "⚡ CX Gateway",
    defaultModel: "cx/gpt-5.6-sol",
    models: [
      { id: "cx/gpt-5.6-sol", label: "CX GPT-5.6 Sol", isDefault: true },
    ],
  },
  {
    mode: "pgsgrove",
    label: "🌿 PGSGrove AI",
    defaultModel: "glm-5.3-flash",
    models: [
      { id: "glm-5.3-flash", label: "GLM 5.3 Flash", isDefault: true },
      { id: "deepseek-v4.1-flash", label: "DeepSeek V4.1 Flash" },
      { id: "deepseek-v4.1-flash-turbo", label: "DeepSeek V4.1 Flash Turbo" },
    ],
  },
  {
    mode: "seekai",
    label: "🔍 SeekAI Gateway",
    defaultModel: "glm-5.3-flash",
    models: [
      { id: "glm-5.3-flash", label: "GLM 5.3 Flash", isDefault: true },
      { id: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
      { id: "deepseek-v4.1-flash", label: "DeepSeek V4.1 Flash" },
    ],
  },
  {
    mode: "tokentable",
    label: "💎 TokenTable Asia",
    defaultModel: "auto",
    models: [
      { id: "auto", label: "TokenTable Auto", isDefault: true },
      { id: "claude-fable-5", label: "Claude Fable 5" },
      { id: "gpt-6-astra", label: "GPT-6 Astra" },
    ],
  },
  {
    mode: "cavoti",
    label: "✨ Cavoti AI",
    defaultModel: "claude-fable-5",
    models: [
      { id: "claude-fable-5", label: "Claude Fable 5", isDefault: true },
      { id: "claude-opus-5", label: "Claude Opus 5" },
      { id: "claude-haiku-4-5", label: "Claude Haiku 4.5" },
    ],
  },
  {
    mode: "experiential",
    label: "🧪 Experiential Labs",
    defaultModel: "claude-opus-5.5",
    models: [
      { id: "claude-opus-5.5", label: "Claude Opus 5.5", isDefault: true },
    ],
  },
  {
    mode: "ollama",
    label: "🦙 Ollama (Local Uncensored)",
    defaultModel: "dolphin-mistral:7b",
    models: [
      { id: "dolphin-mistral:7b", label: "Dolphin Mistral 7B", isDefault: true },
      { id: "llama2-uncensored:7b", label: "Llama 2 Uncensored 7B" },
    ],
  },
];


export function getStoredModelPrefs(): ModelPreferences {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_MODEL_PREFS);
    if (raw) {
      const parsed = JSON.parse(raw);
      return {
        brainMode: parsed.brainMode ?? "auto",
        brainModel: parsed.brainModel ?? null,
        imageEngine: parsed.imageEngine ?? "auto",
        voiceEngine: parsed.voiceEngine ?? "auto",
      };
    }
  } catch {}
  return { brainMode: "auto", brainModel: null, imageEngine: "auto", voiceEngine: "auto" };
}

export function saveModelPrefs(prefs: Partial<ModelPreferences>) {
  try {
    const current = getStoredModelPrefs();
    const updated = { ...current, ...prefs };
    localStorage.setItem(STORAGE_KEY_MODEL_PREFS, JSON.stringify(updated));
  } catch {}
}

export function ModelControlBar({
  currentMode = "auto",
  currentModel,
  providerOptions = [],
  getModelOptions = () => [],
  onSelectProvider = () => {},
  imageEngine = "auto",
  onSelectImageEngine,
  voiceEngine = "auto",
  onSelectVoiceEngine,
  onReprobeCx,
  onOpenSettings,
  isDark = true,
}: ModelControlBarProps) {
  const [activeDropdown, setActiveDropdown] = useState<"brain" | "image" | "voice" | null>(null);
  const [modelSearchQuery, setModelSearchQuery] = useState("");
  const barRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (barRef.current && !barRef.current.contains(e.target as Node)) {
        setActiveDropdown(null);
      }
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setActiveDropdown(null);
      }
    }
    if (activeDropdown) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleKeyDown);
      return () => {
        document.removeEventListener("mousedown", handleClickOutside);
        document.removeEventListener("keydown", handleKeyDown);
      };
    }
  }, [activeDropdown]);

  function formatModelLabel(id: string): string {
    if (!id) return "";
    if (id === "agnes-2.5-flash") return "Agnes 2.5 Flash";
    if (id === "nemotron-3.5-lightning-free") return "Nemotron 3.5 Lightning (Free)";
    if (id === "laguna-s-2.1") return "Laguna S 2.1";
    if (id === "qwen/qwen3.8-max:free") return "Qwen 3.8 Max (Free)";
    if (id === "qwen/qwen3.7-flash:free") return "Qwen 3.7 Flash (Free)";
    if (id === "deepseek-v4-flash-free") return "DeepSeek V4 Flash (Free)";
    if (id === "gpt-6-luna-free") return "GPT-6 Luna (Free)";
    if (id === "gemini-3.5-flash") return "Gemini 3.5 Flash";
    if (id === "gemini-3.8-flash") return "Gemini 3.8 Flash";
    if (id === "gemini-2.5-flash-lite") return "Gemini 2.5 Flash Lite";
    if (id === "gemini-3.5-flash-lite") return "Gemini 3.5 Flash Lite";
    if (id === "gemini-flash-latest") return "Gemini Flash Latest";
    if (id === "gemini-pro-latest") return "Gemini Pro Latest";
    if (id === "gemini-2.5-flash") return "Gemini 2.5 Flash";
    if (id === "claude-fable-5") return "Claude Fable 5";
    if (id === "claude-fable-5.1") return "Claude Fable 5.1";
    if (id === "claude-sonnet-5") return "Claude Sonnet 5";
    if (id === "claude-opus-5.5" || id === "claude-opus-5-5") return "Claude Opus 5.5";
    if (id === "claude-opus-5") return "Claude Opus 5";
    if (id === "claude-3-7-sonnet" || id === "claude-3-7-sonnet-20250219") return "Claude 3.7 Sonnet";

    if (id === "claude-haiku-4-5-20251001" || id === "claude-haiku-4-5") return "Claude 3.5 Haiku";
    if (id === "claude-3-opus-20240229") return "Claude 3 Opus";
    if (id === "cx/gpt-5.6-sol" || id === "gpt-5.6-sol") return "GPT-5.6 Sol";
    if (id === "qwen3.8-max") return "Qwen 3.8 Max";
    if (id === "deepseek-v4-flash") return "DeepSeek V4 Flash";
    if (id === "glm-5.3-flash" || id === "glm-5.3") return "GLM 5.3 Flash";
    if (id === "dolphin-mistral:7b") return "Dolphin Mistral 7B";
    if (id.includes("dolphin")) return "Dolphin Mistral 7B";
    if (id.includes("llama2-uncensored")) return "Llama 2 Uncensored 7B";
    if (id.includes("haiku")) return "Claude Haiku";
    if (id.includes("sonnet-5")) return "Claude Sonnet 5";
    if (id.includes("opus-5")) return "Claude Opus 5";
    if (id.includes("sonnet")) return "Claude Sonnet";
    if (id.includes("opus")) return "Claude Opus";
    if (id.includes("gpt-4o")) return "GPT-4o";
    if (id.includes("gpt-5")) return "GPT-5";
    return id;
  }

  // The backend catalog is authoritative; canned models may be retired or absent
  // from the configured allow-list. Canonical entries supply labels only.
  const activeProviders = useMemo(() => {
    return providerOptions
      .filter((opt) => opt.mode !== "mock" && opt.mode !== "local")
      .map((opt) => ({
          mode: opt.mode,
          label: opt.label || opt.mode,
          available: opt.available,
          health: opt.health,
          healthReason: opt.healthReason,
      }));
  }, [providerOptions]);

  // Current labels
  const brainLabel =
    currentMode === "auto"
      ? "Auto Brain"
      : currentModel
        ? formatModelLabel(currentModel)
        : currentMode === "agent-router"
          ? "Agent Router"
          : currentMode === "codecraft"
            ? "CodeCraft AI"
            : currentMode === "real"
              ? "Gemini Cloud"
              : currentMode === "xkiro"
                ? "XKiro AI"
                : currentMode === "apmix"
                  ? "APMIX.AI"
                  : providerOptions.find((p) => p.mode === currentMode)?.label || currentMode;

  const currentImageObj = IMAGE_ENGINES.find((e) => e.id === imageEngine) || IMAGE_ENGINES[0];
  const currentVoiceObj = VOICE_ENGINES.find((v) => v.id === voiceEngine) || VOICE_ENGINES[0];

  const theme = {
    btnBg: isDark ? "rgba(255, 255, 255, 0.07)" : "var(--bg-surface-raised, #ffffff)",
    btnBorder: isDark ? "rgba(255, 255, 255, 0.14)" : "var(--border-default, #e5e7eb)",
    btnText: isDark ? "#f3f4f6" : "var(--text-primary, #111827)",
    dropdownBg: isDark ? "#0d1018" : "#ffffff",
    dropdownBorder: isDark ? "rgba(255, 255, 255, 0.16)" : "rgba(0, 0, 0, 0.12)",
    dropdownShadow: isDark
      ? "0 24px 60px rgba(0, 0, 0, 0.95), 0 0 0 1px rgba(255, 255, 255, 0.14)"
      : "0 20px 60px rgba(0, 0, 0, 0.22), 0 0 0 1px rgba(0, 0, 0, 0.08)",
    headerText: isDark ? "#94a3b8" : "var(--text-muted, #6b7280)",
    subHeaderText: isDark ? "#cbd5e1" : "var(--text-secondary, #4b5563)",
    primaryText: isDark ? "#f8fafc" : "var(--text-primary, #111827)",
    mutedText: isDark ? "#64748b" : "var(--text-muted, #9ca3af)",
    inputBg: isDark ? "rgba(255, 255, 255, 0.06)" : "var(--bg-surface-secondary, #f9fafb)",
    inputBorder: isDark ? "rgba(255, 255, 255, 0.12)" : "var(--border-default, #e5e7eb)",
    inputText: isDark ? "#f8fafc" : "var(--text-primary, #111827)",
    hoverBg: isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(0, 0, 0, 0.04)",
    divider: isDark ? "rgba(255, 255, 255, 0.08)" : "var(--border-subtle, #f3f4f6)",
  };

  return (
    <div
      ref={barRef}
      data-testid="model-control-bar"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        position: "relative",
        zIndex: 100,
      }}
    >
      {/* 🧠 1. Brain Selector */}
      <div style={{ position: "relative" }}>
        <button
          type="button"
          data-testid="brain-selector-btn"
          aria-expanded={activeDropdown === "brain"}
          aria-controls="brain-provider-menu"
          onClick={() => setActiveDropdown((curr) => (curr === "brain" ? null : "brain"))}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            background: theme.btnBg,
            border: `1px solid ${activeDropdown === "brain" ? "#6366f1" : theme.btnBorder}`,
            borderRadius: "var(--radius-pill, 9999px)",
            padding: "4px 10px",
            color: theme.btnText,
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
            boxShadow: isDark ? "0 2px 8px rgba(0,0,0,0.3)" : "0 1px 3px rgba(0,0,0,0.05)",
            backdropFilter: "blur(12px)",
            WebkitBackdropFilter: "blur(12px)",
            transition: "all 0.15s ease",
          }}
          title="Active Reasoning Brain"
        >
          <Brain size={14} style={{ color: "#6366f1" }} />
          <span style={{ maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {brainLabel}
          </span>
          <ChevronDown size={12} style={{ opacity: 0.6 }} />
        </button>

        {activeDropdown === "brain" && (
          <div
            data-testid="brain-dropdown"
            id="brain-provider-menu"
            style={{
              position: "absolute",
              top: "calc(100% + 6px)",
              right: 0,
              minWidth: 290,
              maxWidth: "min(360px, calc(100vw - 24px))",
              maxHeight: 420,
              overflowY: "auto",
              background: theme.dropdownBg,
              border: `1px solid ${theme.dropdownBorder}`,
              borderRadius: 12,
              boxShadow: theme.dropdownShadow,
              backdropFilter: "blur(20px)",
              WebkitBackdropFilter: "blur(20px)",
              padding: 6,
              zIndex: 99999,
            }}
          >
            <div style={{ padding: "4px 8px", fontSize: 11, fontWeight: 700, color: theme.headerText, textTransform: "uppercase" }}>
              Reasoning Brain & Model
            </div>

            {/* Find model... search input */}
            <div style={{ padding: "4px 6px", marginBottom: 6 }}>
              <input
                type="text"
                data-testid="find-model-input"
                value={modelSearchQuery}
                onChange={(e) => setModelSearchQuery(e.target.value)}
                placeholder="Find model..."
                style={{
                  width: "100%",
                  padding: "6px 10px",
                  fontSize: 12,
                  borderRadius: 6,
                  border: `1px solid ${theme.inputBorder}`,
                  background: theme.inputBg,
                  color: theme.inputText,
                  outline: "none",
                  boxSizing: "border-box",
                }}
                onClick={(e) => e.stopPropagation()}
              />
            </div>

            {/* Auto option (shown when no search or when search matches auto) */}
            {(!modelSearchQuery.trim() || "auto smart router".includes(modelSearchQuery.toLowerCase())) && (
              <button
                type="button"
                data-testid="brain-option-auto"
                onClick={() => {
                  onSelectProvider("auto", null);
                  saveModelPrefs({ brainMode: "auto", brainModel: null });
                  setActiveDropdown(null);
                }}
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "8px 10px",
                  marginBottom: 4,
                  background: currentMode === "auto" ? "rgba(99, 102, 241, 0.16)" : "transparent",
                  border: "none",
                  borderRadius: 8,
                  cursor: "pointer",
                  textAlign: "left",
                }}
              >
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: theme.primaryText }}>✨ Auto (Smart Router)</div>
                  <div style={{ fontSize: 10, color: theme.mutedText }}>Strongest brain that answered its last live call</div>
                </div>
                {currentMode === "auto" && <Check size={14} style={{ color: "#6366f1" }} />}
              </button>
            )}

            {/* Provider options with models */}
            {activeProviders.map((p) => {
              const isSelectedProvider = currentMode === p.mode;
              const rawModels = getModelOptions(p.mode);
              const modelMap = new Map<string, { id: string; label: string; isDefault?: boolean }>();
              rawModels.forEach((m) => {
                if (m.id) {
                  modelMap.set(m.id, { id: m.id, label: formatModelLabel(m.id), isDefault: m.isDefault });
                }
              });
              const allModels = Array.from(modelMap.values());
              const query = modelSearchQuery.trim().toLowerCase();
              const models = query
                ? allModels.filter(
                    (m) =>
                      m.id.toLowerCase().includes(query) ||
                      m.label.toLowerCase().includes(query) ||
                      formatModelLabel(m.id).toLowerCase().includes(query) ||
                      p.label.toLowerCase().includes(query)
                  )
                : allModels;

              if (models.length === 0) return null;

              return (
                <div key={p.mode} style={{ marginBottom: 6 }}>
                  <div style={{ padding: "4px 8px", fontSize: 10, fontWeight: 700, color: theme.subHeaderText }}>
                    {p.label}
                    {p.health !== "healthy" && <span style={{ marginLeft: 6, fontWeight: 400 }}>{p.health === "untested" ? "Not tested yet" : p.health}</span>}
                  </div>
                  {models.map((m) => {
                    const isSelectedModel = isSelectedProvider && (currentModel === m.id || (!currentModel && m.isDefault));
                    return (
                      <button
                        key={m.id}
                        type="button"
                        data-testid={`brain-option-${p.mode}-${m.id}`}
                        disabled={!p.available}
                        title={p.healthReason}
                        aria-pressed={isSelectedModel}
                        onClick={() => {
                          onSelectProvider(p.mode, m.id);
                          saveModelPrefs({ brainMode: p.mode, brainModel: m.id });
                          setActiveDropdown(null);
                        }}
                        style={{
                          width: "100%",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          padding: "6px 10px 6px 16px",
                          background: isSelectedModel ? "rgba(99, 102, 241, 0.16)" : "transparent",
                          border: "none",
                          borderRadius: 6,
                          cursor: p.available ? "pointer" : "not-allowed",
                          opacity: p.available ? 1 : 0.45,
                          textAlign: "left",
                        }}
                      >
                        <div>
                          <div style={{ fontSize: 12, fontWeight: isSelectedModel ? 650 : 500, color: isSelectedModel ? "#6366f1" : theme.primaryText }}>
                            {formatModelLabel(m.id)}
                          </div>
                          <div style={{ fontSize: 9, color: theme.mutedText, fontFamily: "monospace" }}>
                            {m.id}
                          </div>
                        </div>
                        {isSelectedModel && <Check size={14} style={{ color: "#6366f1", flexShrink: 0 }} />}
                      </button>
                    );
                  })}
                </div>
              );
            })}

            {/* Bottom link to full settings */}
            {onOpenSettings && (
              <div style={{ borderTop: `1px solid ${theme.divider}`, marginTop: 4, paddingTop: 4 }}>
                <button
                  type="button"
                  onClick={() => {
                    setActiveDropdown(null);
                    onOpenSettings();
                  }}
                  style={{
                    width: "100%",
                    padding: "6px 10px",
                    background: "transparent",
                    border: "none",
                    borderRadius: 6,
                    color: theme.subHeaderText,
                    fontSize: 11,
                    fontWeight: 650,
                    cursor: "pointer",
                    textAlign: "center",
                  }}
                >
                  ⚙️ Advanced Provider Settings
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* 🎨 2. Image Engine Selector */}
      <div style={{ position: "relative" }}>
        <button
          type="button"
          data-testid="image-selector-btn"
          onClick={() => setActiveDropdown((curr) => (curr === "image" ? null : "image"))}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            background: theme.btnBg,
            border: `1px solid ${activeDropdown === "image" ? "#ec4899" : theme.btnBorder}`,
            borderRadius: "var(--radius-pill, 9999px)",
            padding: "4px 10px",
            color: theme.btnText,
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
            boxShadow: isDark ? "0 2px 8px rgba(0,0,0,0.3)" : "0 1px 3px rgba(0,0,0,0.05)",
            backdropFilter: "blur(12px)",
            WebkitBackdropFilter: "blur(12px)",
            transition: "all 0.15s ease",
          }}
          title="Active Image Generator"
        >
          <ImageIcon size={14} style={{ color: "#ec4899" }} />
          <span style={{ maxWidth: 100, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {currentImageObj.label}
          </span>
          <ChevronDown size={12} style={{ opacity: 0.6 }} />
        </button>

        {activeDropdown === "image" && (
          <div
            data-testid="image-dropdown"
            style={{
              position: "absolute",
              top: "calc(100% + 6px)",
              right: 0,
              minWidth: 260,
              maxWidth: "min(320px, calc(100vw - 24px))",
              background: theme.dropdownBg,
              border: `1px solid ${theme.dropdownBorder}`,
              borderRadius: 12,
              boxShadow: theme.dropdownShadow,
              backdropFilter: "blur(20px)",
              WebkitBackdropFilter: "blur(20px)",
              padding: 6,
              zIndex: 99999,
            }}
          >
            <div style={{ padding: "4px 8px", fontSize: 11, fontWeight: 700, color: theme.headerText, textTransform: "uppercase" }}>
              Image Engine
            </div>
            {IMAGE_ENGINES.map((engine) => {
              const isSelected = imageEngine === engine.id;
              return (
                <button
                  key={engine.id}
                  type="button"
                  data-testid={`image-option-${engine.id}`}
                  onClick={() => {
                    onSelectImageEngine?.(engine.id);
                    saveModelPrefs({ imageEngine: engine.id });
                    setActiveDropdown(null);
                  }}
                  style={{
                    width: "100%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "8px 10px",
                    background: isSelected ? "rgba(236, 72, 153, 0.16)" : "transparent",
                    border: "none",
                    borderRadius: 8,
                    cursor: "pointer",
                    textAlign: "left",
                  }}
                >
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: theme.primaryText }}>
                      {engine.icon} {engine.label}
                    </div>
                    <div style={{ fontSize: 10, color: theme.mutedText }}>{engine.desc}</div>
                  </div>
                  {isSelected && <Check size={14} style={{ color: "#ec4899" }} />}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* 🎙 3. Voice Engine Selector */}
      <div style={{ position: "relative" }}>
        <button
          type="button"
          data-testid="voice-selector-btn"
          onClick={() => setActiveDropdown((curr) => (curr === "voice" ? null : "voice"))}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            background: theme.btnBg,
            border: `1px solid ${activeDropdown === "voice" ? "#10b981" : theme.btnBorder}`,
            borderRadius: "var(--radius-pill, 9999px)",
            padding: "4px 10px",
            color: theme.btnText,
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
            boxShadow: isDark ? "0 2px 8px rgba(0,0,0,0.3)" : "0 1px 3px rgba(0,0,0,0.05)",
            backdropFilter: "blur(12px)",
            WebkitBackdropFilter: "blur(12px)",
            transition: "all 0.15s ease",
          }}
          title="Active Voice & Speech Engine"
        >
          <Mic size={14} style={{ color: "#10b981" }} />
          <span style={{ maxWidth: 100, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {currentVoiceObj.label}
          </span>
          <ChevronDown size={12} style={{ opacity: 0.6 }} />
        </button>

        {activeDropdown === "voice" && (
          <div
            data-testid="voice-dropdown"
            style={{
              position: "absolute",
              top: "calc(100% + 6px)",
              right: 0,
              minWidth: 260,
              maxWidth: "min(320px, calc(100vw - 24px))",
              background: theme.dropdownBg,
              border: `1px solid ${theme.dropdownBorder}`,
              borderRadius: 12,
              boxShadow: theme.dropdownShadow,
              backdropFilter: "blur(20px)",
              WebkitBackdropFilter: "blur(20px)",
              padding: 6,
              zIndex: 99999,
            }}
          >
            <div style={{ padding: "4px 8px", fontSize: 11, fontWeight: 700, color: theme.headerText, textTransform: "uppercase" }}>
              Voice & Speech Engine
            </div>
            {VOICE_ENGINES.map((voice) => {
              const isSelected = voiceEngine === voice.id;
              return (
                <button
                  key={voice.id}
                  type="button"
                  data-testid={`voice-option-${voice.id}`}
                  onClick={() => {
                    onSelectVoiceEngine?.(voice.id);
                    saveModelPrefs({ voiceEngine: voice.id });
                    setActiveDropdown(null);
                  }}
                  style={{
                    width: "100%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "8px 10px",
                    background: isSelected ? "rgba(16, 185, 129, 0.16)" : "transparent",
                    border: "none",
                    borderRadius: 8,
                    cursor: "pointer",
                    textAlign: "left",
                  }}
                >
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: theme.primaryText }}>
                      {voice.icon} {voice.label}
                    </div>
                    <div style={{ fontSize: 10, color: theme.mutedText }}>{voice.desc}</div>
                  </div>
                  {isSelected && <Check size={14} style={{ color: "#10b981" }} />}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
