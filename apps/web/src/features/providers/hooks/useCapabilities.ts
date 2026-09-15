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
    agentCluster: boolean;
    memory: boolean;
    speech: boolean;
  };
}

const DEFAULT_CAPABILITIES: RuntimeCapabilities = {
  runtime: {
    version: "1.0.0",
    environment: "production",
    backendConnected: false,
    activeMode: "claude",
    persistenceEnabled: true,
    authMode: "dev",
  },
  modes: {
    auto: true,
    fast: true,
    deep: true,
    max: true,
    goal: true,
  },
  providers: [
    {
      id: "claude",
      name: "Anthropic Claude",
      configured: true,
      defaultModel: "claude-3-7-sonnet-20250219",
      allowedModels: ["claude-3-7-sonnet-20250219", "claude-3-5-haiku-20241022"],
      protocol: "anthropic-messages",
    },
    {
      id: "gemini",
      name: "Google Gemini",
      configured: true,
      defaultModel: "gemini-2.5-pro",
      allowedModels: ["gemini-2.5-pro", "gemini-2.5-flash"],
      protocol: "native-sdk",
    },
    {
      id: "deepseek",
      name: "DeepSeek AI",
      configured: false,
      defaultModel: "deepseek-chat",
      allowedModels: ["deepseek-chat"],
      protocol: "openai-compatible",
    },
  ],
  models: [
    {
      id: "claude-3-7-sonnet-20250219",
      name: "Claude 3.7 Sonnet",
      provider: "claude",
      tier: "frontier",
      configured: true,
      description: "Anthropic flagship hybrid reasoning and code synthesis",
    },
    {
      id: "claude-3-5-haiku-20241022",
      name: "Claude 3.5 Haiku",
      provider: "claude",
      tier: "fast",
      configured: true,
      description: "High-velocity conversational reasoning and execution",
    },
    {
      id: "gemini-2.5-pro",
      name: "Gemini 2.5 Pro",
      provider: "gemini",
      tier: "frontier",
      configured: true,
      description: "Google frontier multimodal reasoning and large context",
    },
    {
      id: "gemini-2.5-flash",
      name: "Gemini 2.5 Flash",
      provider: "gemini",
      tier: "fast",
      configured: true,
      description: "Low-latency multimodal execution and instant tool calling",
    },
  ],
  features: {
    webSearch: true,
    artifacts: true,
    goals: true,
    agentCluster: true,
    memory: true,
    speech: true,
  },
};

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
      setCapabilities(data);
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
