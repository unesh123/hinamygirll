/**
 * HINAA Memory System
 * Persistent conversation memory using durable backend store.
 */

import { useCallback, useEffect, useState } from "react";
import { HINAA_DEV_USER } from "../../lib/hinaaIdentity";
import { describeResponseFailure, describeThrownFailure } from "../../lib/turnFailure";

export interface MemoryEntry {
  id: string;
  content: string;
  category: "fact" | "preference" | "workflow" | "task" | "conversation" | string;
  status: string;
  consentState: string;
  sourceTurnRef?: string;
  createdAt: string;
  updatedAt: string;
  expiresAt?: string | null;
}

async function memoryFetch(path: string, init?: RequestInit) {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        "X-HINAA-Dev-User": HINAA_DEV_USER,
        ...(init?.headers ?? {}),
      },
    });
  } catch (err) {
    throw new Error(describeThrownFailure(err, "HINAA's memory store never answered"));
  }
  const contentType = response.headers.get("content-type");
  // A 200 carrying HTML is the network edge answering, not the store. Parsing it
  // as JSON would throw a SyntaxError that quotes the page.
  if (!response.ok || (contentType ?? "").toLowerCase().includes("text/html")) {
    const body = await response.text().catch(() => "");
    throw new Error(
      describeResponseFailure({ status: response.status, body, contentType }),
    );
  }
  return response.json();
}

export function useMemory() {
  const [entries, setEntries] = useState<MemoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchMemories = useCallback(async () => {
    try {
      setLoading(true);
      const data = await memoryFetch("/v1/privacy/memories");
      setEntries(data.memories || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Memory store unavailable.");
      console.error("Failed to load memories", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMemories();
  }, [fetchMemories]);

  const addMemory = useCallback(
    async (content: string, category: string = "other", sourceTurnRef?: string) => {
      try {
        const result = await memoryFetch("/v1/privacy/memories", {
          method: "POST",
          body: JSON.stringify({ content, category, sourceTurnRef }),
        });
        setEntries((prev) => [result as MemoryEntry, ...prev]);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Memory store unavailable.");
        console.error("Failed to add memory", err);
      }
    },
    []
  );

  const removeMemory = useCallback(async (id: string) => {
    try {
      await memoryFetch(`/v1/privacy/memories/${id}`, { method: "DELETE" });
      setEntries((prev) => prev.filter((e) => e.id !== id));
    } catch (err) {
      console.error("Failed to remove memory", err);
    }
  }, []);

  const updateMemory = useCallback(async (id: string, content: string, expiresAt?: string | null) => {
    try {
      const result = await memoryFetch(`/v1/privacy/memories/${id}`, {
        method: "PUT",
        body: JSON.stringify({ content, expiresAt }),
      });
      setEntries((prev) => prev.map((e) => (e.id === id ? (result as MemoryEntry) : e)));
    } catch (err) {
      console.error("Failed to update memory", err);
    }
  }, []);

  const clearAll = useCallback(async () => {
    try {
      await memoryFetch(`/v1/privacy/memories`, { method: "DELETE" });
      setEntries([]);
    } catch (err) {
      console.error("Failed to clear memories", err);
    }
  }, []);

  const searchMemory = useCallback(
    (query: string) => {
      const q = query.toLowerCase();
      return entries.filter((e) => e.content.toLowerCase().includes(q));
    },
    [entries]
  );

  return {
    entries,
    loading,
    error,
    addMemory,
    removeMemory,
    updateMemory,
    clearAll,
    searchMemory,
    fetchMemories,
  };
}

export default useMemory;
