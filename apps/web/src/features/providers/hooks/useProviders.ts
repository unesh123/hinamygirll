/**
 * useProviders — fetches and normalizes provider health from /v1/providers.
 *
 * Polling policy:
 * - Fetch immediately on mount.
 * - Abort pending request when a new one starts.
 * - Pause while document is hidden; refresh immediately on visibility.
 * - Exponential backoff after failures: 2s → 4s → 8s → 16s → 30s (cap).
 * - Reset failure count on success.
 * - When healthy, re-poll every 45 seconds (not every retry interval).
 * - Manual refresh via providers.refresh() resets failure count.
 * - Aborts cleanly on unmount.
 * - Uses jitter (±20%) to prevent synchronized clients.
 *
 * This hook DOES NOT auto-select providers. Provider routing is a separate concern.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { fetchProviderStatuses, type ProviderStatus as ApiStatus } from "../../audio/api";
import { buildProviderOptions, extractModelOptions } from "../utils/providerLabels";
import type {
  ModelOption,
  ProviderHealth,
  ProviderMode,
  ProviderStatus,
  ProvidersState,
} from "../types/provider";

// ── Polling constants ──────────────────────────────────────────────────────────
const HEALTHY_POLL_INTERVAL_MS = 45_000;
const BACKOFF_SEQUENCE_MS = [2_000, 4_000, 8_000, 16_000, 30_000];
const JITTER_FACTOR = 0.2; // ±20%

function withJitter(ms: number): number {
  const jitter = ms * JITTER_FACTOR;
  return Math.round(ms + (Math.random() * 2 - 1) * jitter);
}

function getBackoffMs(failureCount: number): number {
  const idx = Math.min(failureCount - 1, BACKOFF_SEQUENCE_MS.length - 1);
  return withJitter(BACKOFF_SEQUENCE_MS[idx]);
}

// ── Type adapter — bridges api.ts ProviderStatus to our normalized type ────────
function adaptStatus(api: ApiStatus): ProviderStatus {
  const state: ProviderHealth =
    api.state === "healthy"     ? "healthy"     :
    api.state === "degraded"    ? "degraded"    :
    api.state === "disabled"    ? "unavailable" :
    api.state === "unavailable" ? "unavailable" :
    "unknown";

  return {
    id: api.id,
    state,
    capabilities: api.capabilities,
    userMessage: api.userMessage ?? undefined,
  };
}

// ── Hook ──────────────────────────────────────────────────────────────────────

export function useProviders(): ProvidersState {
  const [statuses, setStatuses] = useState<ProviderStatus[]>([]);
  const [loaded, setLoaded]     = useState(false);
  const [error, setError]       = useState<string | null>(null);

  const abortRef         = useRef<AbortController | undefined>(undefined);
  const timerRef         = useRef<number | undefined>(undefined);
  const failureCount     = useRef(0);
  const mountedRef       = useRef(true);

  const clearTimer = useCallback(() => {
    if (timerRef.current !== undefined) {
      window.clearTimeout(timerRef.current);
      timerRef.current = undefined;
    }
  }, []);

  const scheduleNext = useCallback((delayMs: number, fn: () => void) => {
    clearTimer();
    timerRef.current = window.setTimeout(fn, delayMs);
  }, [clearTimer]);

  const load = useCallback(() => {
    if (document.visibilityState === "hidden") {
      // Don't poll while hidden; visibility handler will trigger on return
      return;
    }

    // Abort any inflight request
    abortRef.current?.abort();
    abortRef.current = new AbortController();
    const signal = abortRef.current.signal;

    void fetchProviderStatuses(signal)
      .then((raw) => {
        if (!mountedRef.current || signal.aborted) return;

        failureCount.current = 0;
        const normalized = raw.map(adaptStatus);
        setStatuses(normalized);
        setLoaded(true);
        setError(null);

        // Schedule next healthy poll
        scheduleNext(withJitter(HEALTHY_POLL_INTERVAL_MS), load);
      })
      .catch((err: unknown) => {
        if (!mountedRef.current) return;
        if (err instanceof DOMException && err.name === "AbortError") return;

        failureCount.current += 1;
        if (!loaded) setLoaded(true); // stop indefinite spinner

        const delay = getBackoffMs(failureCount.current);
        setError(`Backend unreachable — retrying in ${Math.round(delay / 1000)}s`);
        scheduleNext(delay, load);
      });
  }, [loaded, scheduleNext]); // eslint-disable-line react-hooks/exhaustive-deps

  const refresh = useCallback(() => {
    clearTimer();
    failureCount.current = 0;
    setError(null);
    load();
  }, [clearTimer, load]);

  // Visibility change: refresh immediately when tab becomes visible
  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        // Only refresh if we have an error or haven't loaded yet
        refresh();
      }
    };
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, [refresh]);

  // Mount/unmount lifecycle
  useEffect(() => {
    mountedRef.current = true;
    load();
    return () => {
      mountedRef.current = false;
      clearTimer();
      abortRef.current?.abort();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Derived helpers (memoised) ─────────────────────────────────────────────
  const providerOptions = useMemo(() => buildProviderOptions(statuses), [statuses]);

  const getModelOptions = useCallback(
    (mode: ProviderMode): ModelOption[] => {
      const backendId = mode === "real" ? "gemini" : mode;
      const status = statuses.find((s) => s.id === backendId);
      if (!status) return [];
      const { models, defaultId } = extractModelOptions(status.capabilities);
      return models.map((m) => ({
        id: m.id,
        label: m.id,
        isDefault: m.id === defaultId,
      }));
    },
    [statuses],
  );

  const getDefaultModel = useCallback(
    (mode: ProviderMode): string | null => {
      const backendId = mode === "real" ? "gemini" : mode;
      const status = statuses.find((s) => s.id === backendId);
      if (!status) return null;
      return extractModelOptions(status.capabilities).defaultId;
    },
    [statuses],
  );

  const getHealth = useCallback(
    (mode: ProviderMode): ProviderHealth => {
      if (!loaded) return "checking";
      if (mode === "mock" || mode === "local") return "healthy";
      const backendId = mode === "real" ? "gemini" : mode;
      const status = statuses.find((s) => s.id === backendId);
      return status?.state ?? "unknown";
    },
    [loaded, statuses],
  );

  return {
    statuses,
    loaded,
    error,
    providerOptions,
    getModelOptions,
    getDefaultModel,
    getHealth,
    refresh,
  };
}
