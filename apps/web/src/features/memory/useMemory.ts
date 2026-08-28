/**
 * HINAA Memory System
 * Persistent conversation memory using durable backend store.
 */

import { useCallback, useEffect, useState } from "react";

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
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-HINAA-Dev-User": "local-web-user",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw new Error("Memory API failed");
  }
  return response.json();
}

export function useMemory() {
  const [entries, setEntries] = useState<MemoryEntry[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchMemories = useCallback(async () => {
    try {
      setLoading(true);
      const data = await memoryFetch("/v1/privacy/memories");
      setEntries(data.memories || []);
    } catch (err) {
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
      } catch (err) {
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
    addMemory,
    removeMemory,
    updateMemory,
    clearAll,
    searchMemory,
    fetchMemories,
  };
}

export default useMemory;
