/**
 * Human-readable labels and descriptions for each provider mode.
 * Internal keys (e.g. "real") are never shown directly in the UI.
 */

import type { ProviderMode, ProviderOption, ProviderStatus } from "../types/provider";

const PROVIDER_LABELS: Record<ProviderMode, { label: string; description: string }> = {
  mock:   { label: "Demo",           description: "Deterministic responses. No API calls." },
  local:  { label: "Local",          description: "Zero-credit on-device model. Text only." },
  custom: { label: "Custom Gateway", description: "Your private backend gateway (hcnsec.cn)." },
  openai: { label: "OpenAI",         description: "GPT models via Microsoft Azure." },
  real:   { label: "Gemini",         description: "Google Gemini cloud cascade." },
  groq:   { label: "Groq",           description: "Fast Groq inference." },
  claude: { label: "Claude", description: "Anthropic Messages API through HINAA's local backend configuration." },
  "agent-router": { label: "Agent Router", description: "Unified router with server-side security policies." },
  "cx-gateway":   { label: "CX Gateway",   description: "cx/gpt-5.6-sol — your private premium gateway." },
  "gemini-live":   { label: "Gemini Live",  description: "Native Speech-to-Speech (<300ms multimodal voice)." },
};

export function getProviderLabel(mode: ProviderMode): string {
  return PROVIDER_LABELS[mode]?.label ?? mode;
}

export function getProviderDescription(mode: ProviderMode): string {
  return PROVIDER_LABELS[mode]?.description ?? "";
}

/**
 * Extract model options from raw capability strings.
 * Capability format: "model:<id>" and "default-model:<id>"
 */
export function extractModelOptions(capabilities: string[]): {
  models: Array<{ id: string; isDefault: boolean }>;
  defaultId: string | null;
} {
  const models = capabilities
    .filter((c) => c.startsWith("model:"))
    .map((c) => ({ id: c.slice("model:".length), isDefault: false }));

  const defaultId =
    capabilities
      .find((c) => c.startsWith("default-model:"))
      ?.slice("default-model:".length) ?? null;

  if (defaultId) {
    const idx = models.findIndex((m) => m.id === defaultId);
    if (idx >= 0) models[idx].isDefault = true;
    else models.unshift({ id: defaultId, isDefault: true });
  }

  return { models, defaultId };
}

/**
 * Build the ProviderOption list from raw backend statuses.
 * Always includes mock and local. Cloud providers only appear when healthy.
 * Groq is hidden (no key configured by default).
 */
export function buildProviderOptions(statuses: ProviderStatus[]): ProviderOption[] {
  const byId = new Map(statuses.map((s) => [s.id, s]));

  const alwaysPresent: ProviderMode[] = ["mock", "local"];
  const cloudProviders: ProviderMode[] = ["custom", "openai", "real", "cx-gateway", "claude", "gemini-live"];

  const options: ProviderOption[] = [];

  for (const mode of alwaysPresent) {
    options.push({
      mode,
      ...PROVIDER_LABELS[mode],
      health: "healthy",
      available: true,
    });
  }

  for (const mode of cloudProviders) {
    const backendId = mode === "real" ? "gemini" : mode;
    const status = byId.get(backendId);
    if (!status) continue; // not returned by backend — skip

    const health = status.state;
    const available = health === "healthy";
    options.push({
      mode,
      ...PROVIDER_LABELS[mode],
      health,
      healthReason: !available ? (status.userMessage ?? undefined) : undefined,
      available,
    });
  }

  return options;
}
