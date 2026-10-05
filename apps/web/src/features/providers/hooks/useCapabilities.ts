import { useState, useEffect, useCallback, useRef } from "react";

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
  /** "fallback" for gateways that take a turn only after every brain fails. */
  role?: "fallback";
  /** Models the gateway reported on its live /v1/models answer, if it was probed. */
  servingModels?: number;
  /**
   * What the last live call proved, derived from the brain ledger. `configured`
   * only answers "does a credential exist?"; this answers "will it answer me?".
   */
  health?: "healthy" | "degraded" | "unavailable" | "untested";
  healthMessage?: string;
}

export interface RuntimeCapabilities {
  runtime: {
    version: string;
    environment: string;
    backendConnected: boolean;
    activeMode: string;
    persistenceEnabled: boolean;
    authMode: string;
    ownerName: string;
    privateDataOpen: boolean;
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
    backendConnected: false,
    activeMode: "unknown",
    persistenceEnabled: false,
    authMode: "unknown",
    ownerName: "",
    privateDataOpen: false,
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
      backendConnected: true,
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
  const isFetchingRef = useRef(false);

  const fetchCapabilities = useCallback(async () => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;
    try {
      const apiBase = import.meta.env.VITE_HINAA_API_BASE_URL
        ? String(import.meta.env.VITE_HINAA_API_BASE_URL).replace(/\/+$/, "")
        : "";

      const candidateUrls = [
        `${apiBase}/api/v1/capabilities`,
        `${apiBase}/v1/capabilities`,
      ];

      // If running on local or desktop, add localhost fallback
      if (typeof window !== "undefined" && (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")) {
        candidateUrls.push("http://127.0.0.1:8000/api/v1/capabilities");
        candidateUrls.push("http://127.0.0.1:8000/v1/capabilities");
      }

      let data: any = null;
      let lastErr: Error | null = null;

      for (const targetUrl of candidateUrls) {
        try {
          const res = await fetch(targetUrl, {
            signal: AbortSignal.timeout(8000),
            headers: {
              "bypass-tunnel-reminder": "true",
            },
          });
          if (res.ok) {
            data = await res.json();
            break;
          } else {
            lastErr = new Error(`Failed to load capabilities (${res.status})`);
          }
        } catch (fetchErr: any) {
          lastErr = fetchErr;
        }
      }

      if (data) {
        setCapabilities(normalizeCapabilities(data));
        setError(null);
      } else {
        throw lastErr || new Error("Failed to load capabilities from all candidates");
      }
    } catch (err: any) {
      console.warn("Capability discovery fallback to cached defaults:", err?.message || err);
      setCapabilities((previous) => ({
        ...previous,
        runtime: { ...previous.runtime, backendConnected: false },
      }));
      setError(err?.message || "Failed to discover capabilities");
    } finally {
      setLoading(false);
      isFetchingRef.current = false;
    }
  }, []);

  // Initial fetch and self-healing polling loop
  useEffect(() => {
    fetchCapabilities();

    // Auto-retry quickly (3.5s) if backend is disconnected, or poll periodically (45s) when healthy
    const intervalMs = capabilities.runtime.backendConnected ? 45000 : 3500;
    const timer = setInterval(() => {
      fetchCapabilities();
    }, intervalMs);

    const handleFocusOrOnline = () => {
      fetchCapabilities();
    };

    window.addEventListener("focus", handleFocusOrOnline);
    window.addEventListener("online", handleFocusOrOnline);

    return () => {
      clearInterval(timer);
      window.removeEventListener("focus", handleFocusOrOnline);
      window.removeEventListener("online", handleFocusOrOnline);
    };
  }, [fetchCapabilities, capabilities.runtime.backendConnected]);

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
