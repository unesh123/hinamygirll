/**
 * Provider types — shared across features.
 *
 * These mirror the backend /v1/providers response shape.
 * Keep in sync with apps/api/hinaa_api/main.py ProviderStatus model.
 */

/** Health state reported by the backend for each provider. */
export type ProviderHealth = "healthy" | "degraded" | "unavailable" | "disabled" | "checking" | "unknown";

/** Normalized provider status (adapted from audio/api ProviderStatus). */
export interface ProviderStatus {
  id: string;
  state: ProviderHealth;
  /** Capability strings e.g. "model:gpt-4o", "default-model:gpt-4o", "stt", "tts" */
  capabilities: string[];
  /** Optional human-readable notice from backend. */
  userMessage?: string;
}

/**
 * Provider modes understood by the backend /v1/chat endpoint.
 * Internal keys — never shown directly in UI (use providerLabels.ts).
 */
export type ProviderMode = "mock" | "local" | "custom" | "openai" | "real" | "groq" | "claude" | "agent-router" | "cx-gateway" | "gemini-live";

/** A model option derived from provider capabilities. */
export interface ModelOption {
  id: string;
  label: string;
  isDefault: boolean;
}

/** A selectable provider option derived from backend statuses. */
export interface ProviderOption {
  /** Internal key sent to backend. */
  mode: ProviderMode;
  /** User-facing label. */
  label: string;
  /** Short description shown in settings. */
  description: string;
  health: ProviderHealth;
  /** Human-readable reason for degraded/unavailable state. */
  healthReason?: string;
  /** Whether this option can be selected. */
  available: boolean;
}

/** Result shape returned by useProviders hook. */
export interface ProvidersState {
  statuses: ProviderStatus[];
  loaded: boolean;
  error: string | null;
  providerOptions: ProviderOption[];
  getModelOptions: (mode: ProviderMode) => ModelOption[];
  getDefaultModel: (mode: ProviderMode) => string | null;
  getHealth: (mode: ProviderMode) => ProviderHealth;
  refresh: () => void;
}
