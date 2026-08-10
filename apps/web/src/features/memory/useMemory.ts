/**
 * HINAA Memory System
 * Persistent conversation memory with localStorage + categories.
 * Auto-saves facts, preferences, context. User-editable.
 */

import { useCallback, useEffect, useState } from "react";

export interface MemoryEntry {
  id: string;
  content: string;
  category: "fact" | "preference" | "workflow" | "task" | "conversation";
  createdAt: string;
  lastConfirmedAt: string;
  source: string;
  sensitivity: "low" | "medium" | "high";
  expiresAt?: string;
}

export interface MemoryStore {
  entries: MemoryEntry[];
  version: number;
}

const STORAGE_KEY = "hinaa_memory_v2";

function loadMemory(): MemoryStore {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { entries: [], version: 1 };
    return JSON.parse(raw) as MemoryStore;
  } catch {
    return { entries: [], version: 1 };
  }
}

function saveMemory(store: MemoryStore): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  } catch {
    // Storage full — silently fail
  }
}

function createEntry(
  content: string,
  category: MemoryEntry["category"],
  source: string,
  sensitivity: MemoryEntry["sensitivity"] = "low",
): MemoryEntry {
  const now = new Date().toISOString();
  return {
    id: `mem-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    content,
    category,
    createdAt: now,
    lastConfirmedAt: now,
    source,
    sensitivity,
  };
}

export function useMemory() {
  const [store, setStore] = useState<MemoryStore>(loadMemory);

  useEffect(() => {
    saveMemory(store);
  }, [store]);

  const addMemory = useCallback(
    (content: string, category: MemoryEntry["category"], source = "user", sensitivity: MemoryEntry["sensitivity"] = "low") => {
      setStore((prev) => {
        // Don't duplicate
        const exists = prev.entries.some((e) => e.content === content && e.category === category);
        if (exists) return prev;
        const entry = createEntry(content, category, source, sensitivity);
        return { ...prev, entries: [...prev.entries, entry] };
      });
    },
    [],
  );

  const removeMemory = useCallback((id: string) => {
    setStore((prev) => ({
      ...prev,
      entries: prev.entries.filter((e) => e.id !== id),
    }));
  }, []);

  const updateMemory = useCallback((id: string, content: string) => {
    setStore((prev) => ({
      ...prev,
      entries: prev.entries.map((e) =>
        e.id === id ? { ...e, content, lastConfirmedAt: new Date().toISOString() } : e,
      ),
    }));
  }, []);

  const confirmMemory = useCallback((id: string) => {
    setStore((prev) => ({
      ...prev,
      entries: prev.entries.map((e) =>
        e.id === id ? { ...e, lastConfirmedAt: new Date().toISOString() } : e,
      ),
    }));
  }, []);

  const getByCategory = useCallback(
    (category: MemoryEntry["category"]) => store.entries.filter((e) => e.category === category),
    [store.entries],
  );

  const searchMemory = useCallback(
    (query: string) => {
      const q = query.toLowerCase();
      return store.entries.filter((e) => e.content.toLowerCase().includes(q));
    },
    [store.entries],
  );

  const clearAll = useCallback(() => {
    setStore({ entries: [], version: 1 });
  }, []);

  // Auto-extract from assistant responses
  const extractFromResponse = useCallback(
    (text: string) => {
      // Extract potential facts/preferences using heuristic patterns
      const patterns = [
        { regex: /(?:remember|noted|saved):\s*(.+)/gi, category: "fact" as const },
        { regex: /(?:you prefer|you like|you want)\s+(.+)/gi, category: "preference" as const },
        { regex: /(?:your\s+)(?:goal|task|project)(?:\s+is)?\s*(.+)/gi, category: "task" as const },
      ];

      for (const { regex, category } of patterns) {
        let match;
        while ((match = regex.exec(text)) !== null) {
          addMemory(match[1].trim(), category, "auto-extract", "medium");
        }
      }
    },
    [addMemory],
  );

  return {
    entries: store.entries,
    addMemory,
    removeMemory,
    updateMemory,
    confirmMemory,
    getByCategory,
    searchMemory,
    clearAll,
    extractFromResponse,
  };
}

export default useMemory;
