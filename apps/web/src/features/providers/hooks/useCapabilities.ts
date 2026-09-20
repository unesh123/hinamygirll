import { useState, useEffect, useCallback } from "react";

export interface DiscoveredModel {
  id: string;
  name: string;
  provider: string;
  tier: "frontier" | "fast" | "deep" | "max" | string;
  configured: boolean;
  description: string;
}

export interface DiscoveredProvider {
  id: string;
  name: string;
  configured: boolean;
  defaultModel: string;
  allowedModels: string[];
  protocol: string;
}

export interface RuntimeCapabilities {
  runtime: {
    version: string;
    environment: string;
    backendConnected: boolean;
    activeMode: string;
    persistenceEnabled: boolean;
    authMode: string;
  };
  modes: {
    auto: boolean;
    fast: boolean;
    deep: boolean;
    max: boolean;
    goal: boolean;
  };
  providers: DiscoveredProvider[];
  models: DiscoveredModel[];
  features: {
    webSearch: boolean;
    artifacts: boolean;
    goals: boolean;
    agentRuntime: boolean;
    memory: boolean;
    speech: boolean;
  };
  integrations: {
    github: {
      configured: boolean;
      defaultRepo: string | null;
      served: boolean;
    };
  };
}

const DEFAULT_CAPABILITIES: RuntimeCapabilities = {
  runtime: {
    version: "1.0.0",
    environment: "unknown",
    // Optimistic defaults are dishonest: until /v1/capabilities answers we do
    // not know the backend is reachable, so the UI must say so instead of
    // implying live brains are available.
    backendConnected: false,
    activeMode: "unknown",
    persistenceEnabled: false,
    authMode: "unknown",
  },
  modes: {
    auto: true,
    fast: false,
    deep: false,
    max: false,
    goal: false,
  },
  providers: [],
  models: [],
  features: {
    webSearch: false,
    artifacts: false,
    goals: false,
    agentRuntime: false,
    memory: false,
    speech: false,
  },
  integrations: {
    github: { configured: false, defaultRepo: null, served: false },
  },
};

function normalizeCapabilities(raw: unknown): RuntimeCapabilities {
  if (!raw || typeof raw !== "object") return DEFAULT_CAPABILITIES;
  const payload = raw as Partial<RuntimeCapabilities>;
  return {
    runtime: {
      ...DEFAULT_CAPABILITIES.runtime,
      ...(typeof payload.runtime === "object" && payload.runtime !== null ? payload.runtime : {}),
    },
    modes: {
      ...DEFAULT_CAPABILITIES.modes,
      ...(typeof payload.modes === "object" && payload.modes !== null ? payload.modes : {}),
    },
    providers: Array.isArray(payload.providers) ? payload.providers : [],
    models: Array.isArray(payload.models) ? payload.models : [],
    features: {
      ...DEFAULT_CAPABILITIES.features,
      ...(typeof payload.features === "object" && payload.features !== null ? payload.features : {}),
    },
    integrations: {
      github: {
        ...DEFAULT_CAPABILITIES.integrations.github,
        ...(payload.integrations?.github ?? {}),
      },
    },
  };
}

export function useCapabilities() {
  const [capabilities, setCapabilities] = useState<RuntimeCapabilities>(DEFAULT_CAPABILITIES);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCapabilities = useCallback(async () => {
    try {
      setLoading(true);
      const apiBase = import.meta.env.VITE_HINAA_API_BASE_URL
        ? String(import.meta.env.VITE_HINAA_API_BASE_URL).replace(/\/+$/, "")
        : "";
      const res = await fetch(`${apiBase}/api/v1/capabilities`, {
        headers: {
          "bypass-tunnel-reminder": "true",
        },
      });
      if (!res.ok) {
        throw new Error(`Failed to load capabilities (${res.status})`);
      }
      const data = await res.json();
      // Defensive merge: a partial or malformed capabilities payload (proxy
      // error page, older backend, mock) must never poison the shape the UI
      // relies on. Missing keys fall back to the safe defaults.
      setCapabilities(normalizeCapabilities(data));
      setError(null);
    } catch (err: any) {
      console.warn("Capability discovery fallback to cached defaults:", err?.message || err);
      setError(err?.message || "Failed to discover capabilities");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCapabilities();
  }, [fetchCapabilities]);

  return {
    capabilities,
    models: capabilities.models,
    providers: capabilities.providers,
    runtime: capabilities.runtime,
    loading,
    error,
    refetch: fetchCapabilities,
  };
}
