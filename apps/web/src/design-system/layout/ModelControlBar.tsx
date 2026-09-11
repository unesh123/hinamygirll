import { useState, useRef, useEffect } from "react";
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
}

export const IMAGE_ENGINES = [
  { id: "auto", label: "Auto Engine", desc: "Best available cloud or local renderer", icon: "✨" },
  { id: "gemini-3.1-flash-image", label: "Gemini 3.1 Flash", desc: "Ultra-fast text-to-image & edit", icon: "⚡" },
  { id: "gemini-3-pro-image", label: "Gemini 3 Pro", desc: "Cinematic multi-reference composition", icon: "🎨" },
  { id: "comfyui", label: "ComfyUI SDXL", desc: "Private local GPU diffusion pipeline", icon: "💻" },
  { id: "magnific", label: "Magnific / Freepik", desc: "High-fidelity hallucinatory upscale", icon: "💎" },
];

export const VOICE_ENGINES = [
  { id: "auto", label: "Auto Voice", desc: "Fastest responsive neural speech (ElevenLabs / Azure)", icon: "✨" },
  { id: "elevenlabs", label: "ElevenLabs Neural", desc: "Ultra-expressive streaming neural voice (Turbo v2.5)", icon: "🎙" },
  { id: "gemini-live", label: "Gemini Live", desc: "Sub-300ms bidirectional speech stream", icon: "🎙" },
  { id: "azure-speech", label: "Azure Neural", desc: "Expressive high-fidelity voices", icon: "🌐" },
  { id: "browser-native", label: "Browser Native", desc: "Zero-latency offline client TTS", icon: "🔊" },
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
}: ModelControlBarProps) {
  const [activeDropdown, setActiveDropdown] = useState<"brain" | "image" | "voice" | null>(null);
  const barRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (barRef.current && !barRef.current.contains(e.target as Node)) {
        setActiveDropdown(null);
      }
    }
    if (activeDropdown) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [activeDropdown]);

  function formatModelLabel(id: string): string {
    // Claude models — specific first, generic fallback
    if (id === "claude-opus-5") return "Claude Opus 5";
    if (id === "claude-sonnet-5") return "Claude Sonnet 5";
    if (id === "claude-opus-4-8") return "Claude Opus 4.8";
    if (id === "claude-opus-4-7") return "Claude Opus 4.7";
    if (id === "claude-opus-4-6") return "Claude Opus 4.6";
    if (id === "claude-sonnet-4-6") return "Claude Sonnet 4.6";
    if (id.includes("haiku")) return "Claude Haiku";
    if (id.includes("sonnet-5")) return "Claude Sonnet 5";
    if (id.includes("opus-5")) return "Claude Opus 5";
    if (id.includes("sonnet")) return "Claude Sonnet";
    if (id.includes("opus")) return "Claude Opus";
    if (id.includes("gemini-3.5-flash-lite")) return "Gemini 3.5 Flash Lite";
    if (id.includes("gemini-3.1-flash-lite")) return "Gemini 3.1 Flash Lite";
    if (id.includes("gemini-3.6")) return "Gemini 3.6 Flash";
    if (id.includes("gemini-3.8")) return "Gemini 3.8 Flash";
    if (id.includes("gemini-3.5")) return "Gemini 3.5 Flash";
    if (id.includes("gemini-flash-latest")) return "Gemini Flash Latest";
    if (id.includes("gpt-4o")) return "GPT-4o";
    if (id.includes("gpt-5")) return "GPT-5";
    return id;
  }

  // Current labels
  const brainLabel =
    currentMode === "auto"
      ? "Auto Brain"
      : currentModel
        ? formatModelLabel(currentModel)
        : providerOptions.find((p) => p.mode === currentMode)?.label || currentMode;

  const currentImageObj = IMAGE_ENGINES.find((e) => e.id === imageEngine) || IMAGE_ENGINES[0];
  const currentVoiceObj = VOICE_ENGINES.find((v) => v.id === voiceEngine) || VOICE_ENGINES[0];

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
          onClick={() => setActiveDropdown((curr) => (curr === "brain" ? null : "brain"))}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            background: "var(--bg-surface-raised, #ffffff)",
            border: `1px solid ${activeDropdown === "brain" ? "var(--accent, #6366f1)" : "var(--border-default, #e5e7eb)"}`,
            borderRadius: "var(--radius-pill, 9999px)",
            padding: "4px 10px",
            color: "var(--text-primary, #111827)",
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
            boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
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
            style={{
              position: "absolute",
              top: "calc(100% + 6px)",
              left: 0,
              minWidth: 290,
              maxHeight: 380,
              overflowY: "auto",
              background: "var(--bg-surface-raised, #ffffff)",
              border: "1px solid var(--border-default, #e5e7eb)",
              borderRadius: 12,
              boxShadow: "0 10px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1)",
              padding: 6,
              zIndex: 200,
            }}
          >
            <div style={{ padding: "4px 8px", fontSize: 11, fontWeight: 700, color: "var(--text-muted, #6b7280)", textTransform: "uppercase" }}>
              Reasoning Brain & Model
            </div>
            {/* Auto option */}
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
                background: currentMode === "auto" ? "rgba(99, 102, 241, 0.08)" : "transparent",
                border: "none",
                borderRadius: 8,
                cursor: "pointer",
                textAlign: "left",
              }}
            >
              <div>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary, #111827)" }}>✨ Auto (Smart Router)</div>
                <div style={{ fontSize: 10, color: "var(--text-muted, #6b7280)" }}>Fastest healthy model automatically</div>
              </div>
              {currentMode === "auto" && <Check size={14} style={{ color: "#6366f1" }} />}
            </button>

            {/* Provider options with models */}
            {providerOptions
              .filter((p) => p.mode !== "mock" && p.mode !== "local")
              .map((p) => {
                const isSelectedProvider = currentMode === p.mode;
                const rawModels = getModelOptions(p.mode);
                const fallbackModels: Record<string, Array<{ id: string; label: string; isDefault: boolean }>> = {
                  claude: [
                    { id: "claude-haiku-4-5-20251001", label: "Claude 3.5 Haiku", isDefault: true },
                    { id: "claude-3-7-sonnet-20250219", label: "Claude 3.7 Sonnet", isDefault: false },
                    { id: "claude-3-opus-20240229", label: "Claude 3 Opus", isDefault: false },
                  ],
                  real: [
                    { id: "gemini-3.5-flash-lite", label: "Gemini 3.5 Flash Lite", isDefault: true },
                    { id: "gemini-3.1-flash-lite", label: "Gemini 3.1 Flash Lite", isDefault: false },
                    { id: "gemini-3.6-flash", label: "Gemini 3.6 Flash", isDefault: false },
                    { id: "gemini-flash-latest", label: "Gemini Flash Latest", isDefault: false },
                  ],
                };
                const models = rawModels.length > 0 ? rawModels : (fallbackModels[p.mode] ?? [{ id: p.mode, label: p.label, isDefault: true }]);
                const providerTitle =
                  p.mode === "claude" ? "🧠 Claude" :
                  p.mode === "real" ? "🌐 Gemini" :
                  p.mode === "openai" ? "🤖 OpenAI" :
                  p.mode === "cx-gateway" ? "⚡ CX Gateway" :
                  p.mode === "qwen" ? "🇨🇳 Qwen" : p.label;

                if (!p.available) return null;

                return (
                  <div key={p.mode} style={{ marginBottom: 6 }}>
                    <div style={{ padding: "4px 8px", fontSize: 10, fontWeight: 700, color: "var(--text-secondary, #4b5563)" }}>
                      {providerTitle}
                    </div>
                    {models.map((m) => {
                      const isSelectedModel = isSelectedProvider && (currentModel === m.id || (!currentModel && m.isDefault));
                      return (
                        <button
                          key={m.id}
                          type="button"
                          data-testid={`brain-option-${p.mode}-${m.id}`}
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
                            background: isSelectedModel ? "rgba(99, 102, 241, 0.08)" : "transparent",
                            border: "none",
                            borderRadius: 6,
                            cursor: "pointer",
                            textAlign: "left",
                          }}
                        >
                          <div>
                            <div style={{ fontSize: 12, fontWeight: isSelectedModel ? 650 : 500, color: isSelectedModel ? "var(--accent, #6366f1)" : "var(--text-primary, #111827)" }}>
                              {formatModelLabel(m.id)}
                            </div>
                            <div style={{ fontSize: 9, color: "var(--text-muted, #9ca3af)", fontFamily: "monospace" }}>
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
              <div style={{ borderTop: "1px solid var(--border-subtle, #f3f4f6)", marginTop: 4, paddingTop: 4 }}>
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
                    color: "var(--text-secondary, #6b7280)",
                    fontSize: 11,
                    fontWeight: 600,
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
            background: "var(--bg-surface-raised, #ffffff)",
            border: `1px solid ${activeDropdown === "image" ? "var(--accent, #ec4899)" : "var(--border-default, #e5e7eb)"}`,
            borderRadius: "var(--radius-pill, 9999px)",
            padding: "4px 10px",
            color: "var(--text-primary, #111827)",
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
            boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
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
              left: 0,
              minWidth: 260,
              background: "var(--bg-surface-raised, #ffffff)",
              border: "1px solid var(--border-default, #e5e7eb)",
              borderRadius: 12,
              boxShadow: "0 10px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1)",
              padding: 6,
              zIndex: 200,
            }}
          >
            <div style={{ padding: "4px 8px", fontSize: 11, fontWeight: 700, color: "var(--text-muted, #6b7280)", textTransform: "uppercase" }}>
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
                    background: isSelected ? "rgba(236, 72, 153, 0.08)" : "transparent",
                    border: "none",
                    borderRadius: 8,
                    cursor: "pointer",
                    textAlign: "left",
                  }}
                >
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary, #111827)" }}>
                      {engine.icon} {engine.label}
                    </div>
                    <div style={{ fontSize: 10, color: "var(--text-muted, #6b7280)" }}>{engine.desc}</div>
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
            background: "var(--bg-surface-raised, #ffffff)",
            border: `1px solid ${activeDropdown === "voice" ? "var(--accent, #10b981)" : "var(--border-default, #e5e7eb)"}`,
            borderRadius: "var(--radius-pill, 9999px)",
            padding: "4px 10px",
            color: "var(--text-primary, #111827)",
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
            boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
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
              background: "var(--bg-surface-raised, #ffffff)",
              border: "1px solid var(--border-default, #e5e7eb)",
              borderRadius: 12,
              boxShadow: "0 10px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1)",
              padding: 6,
              zIndex: 200,
            }}
          >
            <div style={{ padding: "4px 8px", fontSize: 11, fontWeight: 700, color: "var(--text-muted, #6b7280)", textTransform: "uppercase" }}>
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
                    background: isSelected ? "rgba(16, 185, 129, 0.08)" : "transparent",
                    border: "none",
                    borderRadius: 8,
                    cursor: "pointer",
                    textAlign: "left",
                  }}
                >
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary, #111827)" }}>
                      {voice.icon} {voice.label}
                    </div>
                    <div style={{ fontSize: 10, color: "var(--text-muted, #6b7280)" }}>{voice.desc}</div>
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
