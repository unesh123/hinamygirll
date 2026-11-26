import { useCallback, useEffect, useRef, useState } from "react";
import {
  createInitialAgentTurnState,
  reduceAgentTurnEvent,
  type AgentTurnState,
} from "../contracts/agentEvents";

export interface UseAgentTurnOptions {
  apiBase?: string;
}

export function useAgentTurn(options: UseAgentTurnOptions = {}) {
  const apiBase = options.apiBase ?? "";
  const [state, setState] = useState<AgentTurnState>(() => createInitialAgentTurnState());
  const abortRef = useRef<AbortController | null>(null);

  const abort = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  useEffect(() => abort, [abort]);

  const reset = useCallback(() => {
    abort();
    setState(createInitialAgentTurnState());
  }, [abort]);

  const applyEvent = useCallback((raw: Record<string, unknown>) => {
    setState((prev) => reduceAgentTurnEvent(prev, raw));
  }, []);

  const subscribeRun = useCallback(
    async (runId: string) => {
      abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      setState({
        ...createInitialAgentTurnState(),
        phase: "thinking",
        runId,
        startedAt: Date.now(),
      });

      try {
        const res = await fetch(
          `${apiBase}/api/v1/agent/agentic-runs/${encodeURIComponent(runId)}/stream`,
          { signal: ctrl.signal },
        );
        if (!res.ok || !res.body) {
          throw new Error(`Stream unavailable (${res.status})`);
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (!ctrl.signal.aborted) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";
          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) continue;
            const jsonText = trimmed.startsWith("data:") ? trimmed.slice(5).trim() : trimmed;
            if (!jsonText || jsonText === "[DONE]") continue;
            try {
              const parsed = JSON.parse(jsonText) as Record<string, unknown>;
              setState((prev) => reduceAgentTurnEvent(prev, parsed));
            } catch {
              // ignore malformed stream frame
            }
          }
        }
      } catch (err) {
        if ((err as Error)?.name === "AbortError") {
          setState((prev) => ({ ...prev, phase: "cancelled", finishedAt: Date.now() }));
          return;
        }
        setState((prev) => ({
          ...prev,
          phase: "error",
          error: err instanceof Error ? err.message : "Run stream failed",
          finishedAt: Date.now(),
        }));
      }
    },
    [abort, apiBase],
  );

  return {
    state,
    applyEvent,
    subscribeRun,
    abort,
    reset,
  };
}
