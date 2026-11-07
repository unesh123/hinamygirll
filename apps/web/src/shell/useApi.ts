import { useCallback, useEffect, useState } from "react";

export type ApiStatus = "loading" | "ok" | "missing" | "error";

export interface ApiResource<T> {
  status: ApiStatus;
  data: T | null;
  error: string | null;
  reload: () => void;
}

/** GET a JSON endpoint. 404/405 map to "missing" so UIs can say "not available on this backend". */
export function useApiJson<T>(path: string | null): ApiResource<T> {
  const [state, setState] = useState<Pick<ApiResource<T>, "status" | "data" | "error">>({ status: "loading", data: null, error: null });
  const [tick, setTick] = useState(0);
  const reload = useCallback(() => setTick((n) => n + 1), []);

  useEffect(() => {
    if (!path) return;
    const ctrl = new AbortController();
    setState((s) => ({ ...s, status: "loading", error: null }));
    fetch(path, { signal: ctrl.signal, headers: { Accept: "application/json" } })
      .then(async (res) => {
        if (res.status === 404 || res.status === 405) {
          setState({ status: "missing", data: null, error: null });
        } else if (!res.ok) {
          setState({ status: "error", data: null, error: `Request failed (${res.status})` });
        } else {
          setState({ status: "ok", data: (await res.json()) as T, error: null });
        }
      })
      .catch((err: unknown) => {
        if (ctrl.signal.aborted) return;
        setState({ status: "error", data: null, error: err instanceof Error ? err.message : "Network error" });
      });
    return () => ctrl.abort();
  }, [path, tick]);

  return { ...state, reload };
}

/** Pull a list out of `[...]` or `{ key: [...] }` payloads. */
export function asList<T = Record<string, unknown>>(data: unknown, keys: string[]): T[] {
  if (Array.isArray(data)) return data as T[];
  if (data && typeof data === "object") {
    for (const key of keys) {
      const value = (data as Record<string, unknown>)[key];
      if (Array.isArray(value)) return value as T[];
    }
  }
  return [];
}

export function str(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}
