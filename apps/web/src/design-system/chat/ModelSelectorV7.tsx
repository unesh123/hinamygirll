import React, { useState, useRef, useEffect } from "react";
import {
  ChevronDown,
  Cpu,
  Sparkles,
  Zap,
  CheckCircle2,
  Brain,
  Layers,
  CircleDot,
} from "lucide-react";
import type { DiscoveredModel, DiscoveredProvider } from "../../features/providers/hooks/useCapabilities";

export interface ModelSelectorV7Props {
  models?: DiscoveredModel[];
  providers?: DiscoveredProvider[];
  selectedModelId?: string | null;
  selectedProviderId?: string | null;
  isAutoRouter?: boolean;
  onSelectAuto: () => void;
  onSelectModel: (model: DiscoveredModel) => void;
  backendConnected?: boolean;
  placement?: "top" | "bottom";
}

export const ModelSelectorV7: React.FC<ModelSelectorV7Props> = ({
  models = [],
  providers = [],
  selectedModelId,
  selectedProviderId,
  isAutoRouter = true,
  onSelectAuto,
  onSelectModel,
  backendConnected = true,
  placement = "bottom",
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        menuRef.current &&
        !menuRef.current.contains(event.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  // Close on Escape
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  // Find active model details
  const activeModel = models.find((m) => m.id === selectedModelId);
  const activeLabel = isAutoRouter
    ? "Auto (Router)"
    : activeModel?.name || selectedModelId || "Model";

  // Group models by provider
  const providerGroups: { [key: string]: DiscoveredModel[] } = {};
  for (const m of models) {
    if (!providerGroups[m.provider]) {
      providerGroups[m.provider] = [];
    }
    providerGroups[m.provider].push(m);
  }

  const getProviderName = (providerId: string) => {
    const p = providers.find((pr) => pr.id === providerId);
    if (p) return p.name;
    if (providerId === "claude") return "Anthropic Claude";
    if (providerId === "gemini") return "Google Gemini";
    if (providerId === "deepseek") return "DeepSeek AI";
    if (providerId === "openai") return "OpenAI / Codex";
    return providerId.toUpperCase();
  };

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <button
        ref={buttonRef}
        type="button"
        data-testid="composer-model-selector-btn"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 5,
          padding: "4px 9px",
          borderRadius: 9999,
          background: isAutoRouter
            ? "var(--surface-subtle, #f6f3f7)"
            : "rgba(220, 95, 139, 0.1)",
          border: isAutoRouter
            ? "1px solid var(--border-subtle, rgba(0,0,0,0.08))"
            : "1px solid rgba(220, 95, 139, 0.35)",
          fontSize: 11,
          fontWeight: 600,
          color: isAutoRouter
            ? "var(--text-secondary, #5e545d)"
            : "var(--accent-primary, #dc5f8b)",
          cursor: "pointer",
          transition: "all 0.15s ease",
        }}
        title="Select intelligence routing or pin a specific model"
      >
        {isAutoRouter ? (
          <Cpu size={11} style={{ opacity: 0.8 }} />
        ) : (
          <Brain size={11} style={{ color: "var(--accent-primary, #dc5f8b)" }} />
        )}
        <span className="model-selector-v7__label">{activeLabel}</span>
        <ChevronDown size={10} style={{ opacity: 0.6 }} />
      </button>

      {isOpen && (
        <div
          ref={menuRef}
          data-testid="composer-model-dropdown"
          style={{
            position: "absolute",
            top: placement === "bottom" ? "calc(100% + 8px)" : undefined,
            bottom: placement === "top" ? "calc(100% + 8px)" : undefined,
            right: placement === "bottom" ? 0 : undefined,
            left: placement === "top" ? 0 : undefined,
            width: 280,
            maxHeight: 420,
            overflowY: "auto",
            padding: 6,
            background: "var(--surface-overlay, #ffffff)",
            borderRadius: 12,
            boxShadow: "0 12px 32px -4px rgba(0,0,0,0.14), 0 4px 12px -2px rgba(0,0,0,0.06)",
            border: "1px solid var(--border-default, rgba(0,0,0,0.1))",
            zIndex: 90,
            fontFamily: "inherit",
          }}
        >
          {/* Header */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "6px 8px 4px 8px",
              borderBottom: "1px solid var(--border-subtle, rgba(0,0,0,0.06))",
              marginBottom: 4,
            }}
          >
            <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.05em", color: "var(--text-tertiary, #847a83)" }}>
              INTELLIGENCE & ROUTING
            </span>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                fontSize: 10,
                color: backendConnected ? "#10b981" : "#f59e0b",
                fontWeight: 500,
              }}
            >
              <CircleDot size={8} />
              {backendConnected ? "Live Backend" : "Standby"}
            </span>
          </div>

          {/* Option 1: Auto (Router) */}
          <button
            type="button"
            data-testid="model-option-auto"
            onClick={() => {
              onSelectAuto();
              setIsOpen(false);
            }}
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "7px 8px",
              borderRadius: 8,
              border: "none",
              background: isAutoRouter ? "var(--surface-subtle, #f6f3f7)" : "transparent",
              cursor: "pointer",
              textAlign: "left",
              marginBottom: 4,
              transition: "background 0.12s ease",
            }}
          >
            <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
              <Sparkles
                size={14}
                style={{
                  marginTop: 2,
                  color: isAutoRouter ? "var(--accent-primary, #dc5f8b)" : "var(--text-secondary, #5e545d)",
                }}
              />
              <div>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: isAutoRouter ? "var(--accent-primary, #dc5f8b)" : "var(--text-primary, #1e191d)",
                  }}
                >
                  Auto (Adaptive Router)
                </div>
                <div style={{ fontSize: 10, color: "var(--text-tertiary, #847a83)", marginTop: 1 }}>
                  Infers task depth & routes to optimal model
                </div>
              </div>
            </div>
            {isAutoRouter && <CheckCircle2 size={13} style={{ color: "var(--accent-primary, #dc5f8b)" }} />}
          </button>

          <div style={{ height: 1, background: "var(--border-subtle, rgba(0,0,0,0.06))", margin: "4px 0" }} />

          {/* Empty / loading state — never silently show only "Auto" */}
          {Object.keys(providerGroups).length === 0 && (
            <div
              data-testid="model-selector-empty"
              style={{
                padding: "10px 8px 12px 8px",
                fontSize: 11,
                lineHeight: 1.45,
                color: "var(--text-tertiary, #847a83)",
              }}
            >
              {backendConnected
                ? "No live models are currently configured on the backend. Auto routing will use the default brain."
                : "Loading available models… If this persists, Hina's backend is unreachable."}
            </div>
          )}

          {/* Discovered Real Models Grouped by Provider */}
          {Object.entries(providerGroups).map(([providerKey, groupModels]) => {
            const providerName = getProviderName(providerKey);
            const providerConfig = providers.find((p) => p.id === providerKey);
            const isConfigured = providerConfig ? providerConfig.configured : groupModels.some((m) => m.configured);

            return (
              <div key={providerKey} style={{ marginTop: 6, marginBottom: 4 }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "3px 8px",
                    fontSize: 10,
                    fontWeight: 700,
                    letterSpacing: "0.04em",
                    color: "var(--text-tertiary, #847a83)",
                    textTransform: "uppercase",
                  }}
                >
                  <span>{providerName}</span>
                  <span
                    style={{
                      fontSize: 9,
                      padding: "1px 5px",
                      borderRadius: 4,
                      background: isConfigured ? "rgba(16, 185, 129, 0.1)" : "rgba(100, 116, 139, 0.1)",
                      color: isConfigured ? "#059669" : "#64748b",
                      fontWeight: 600,
                    }}
                  >
                    {isConfigured ? "Configured" : "Unconfigured"}
                  </span>
                </div>

                {groupModels.map((model) => {
                  const isSelected = !isAutoRouter && selectedModelId === model.id;

                  return (
                    <button
                      key={model.id}
                      type="button"
                      data-testid={`model-option-${model.id}`}
                      onClick={() => {
                        onSelectModel(model);
                        setIsOpen(false);
                      }}
                      style={{
                        width: "100%",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "6px 8px",
                        borderRadius: 6,
                        border: "none",
                        background: isSelected ? "var(--surface-subtle, #f6f3f7)" : "transparent",
                        cursor: "pointer",
                        textAlign: "left",
                        marginTop: 1,
                        transition: "background 0.12s ease",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                        <CircleDot
                          size={11}
                          style={{
                            marginTop: 3,
                            color: model.configured ? "#10b981" : "#94a3b8",
                          }}
                        />
                        <div>
                          <div
                            style={{
                              fontSize: 12,
                              fontWeight: isSelected ? 600 : 500,
                              color: isSelected ? "var(--accent-primary, #dc5f8b)" : "var(--text-primary, #1e191d)",
                              display: "flex",
                              alignItems: "center",
                              gap: 6,
                            }}
                          >
                            <span>{model.name}</span>
                            {model.tier === "frontier" && (
                              <span
                                style={{
                                  fontSize: 9,
                                  padding: "0 4px",
                                  borderRadius: 3,
                                  background: "rgba(220, 95, 139, 0.1)",
                                  color: "var(--accent-primary, #dc5f8b)",
                                  fontWeight: 600,
                                }}
                              >
                                Frontier
                              </span>
                            )}
                          </div>
                          <div
                            style={{
                              fontSize: 10,
                              color: "var(--text-tertiary, #847a83)",
                              marginTop: 1,
                              lineHeight: 1.25,
                            }}
                          >
                            {model.description}
                          </div>
                        </div>
                      </div>
                      {isSelected && (
                        <CheckCircle2 size={13} style={{ color: "var(--accent-primary, #dc5f8b)", flexShrink: 0 }} />
                      )}
                    </button>
                  );
                })}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
