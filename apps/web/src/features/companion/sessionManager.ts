/**
 * sessionManager.ts — Session Anti-Amnesia Engine
 * Persists active view, conversation id, camera mode, avatar model, and conversation messages
 * across page refreshes and browser re-launches.
 */

import type { TranscriptMessage } from "./types";
import { deserializeAssistantTurn, getAssistantDisplayText } from "./assistantTurnCodec";

export interface ActiveSessionState {
  conversationId: string;
  sakuraView: "talk" | "work" | "projects" | "images" | "library";
  avatarModel: string;
  avatarMode: "portrait" | "upperbody" | "closeup" | "full" | "companion" | "hidden";
  dockSide?: "right" | "left" | "floating";
  updatedAt?: string;
}

const SESSION_STORAGE_KEY = "hinaa.session.active.v1";

export function saveActiveSession(patch: Partial<ActiveSessionState>): void {
  if (typeof window === "undefined") return;
  try {
    const existing = loadActiveSession();
    const updated = { ...existing, ...patch, updatedAt: new Date().toISOString() };
    window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(updated));
  } catch (err) {
    console.warn("Failed to persist active session:", err);
  }
}

export function loadActiveSession(): Partial<ActiveSessionState> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(SESSION_STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

export function getOrCreateActiveConversationId(): string {
  const existing = loadActiveSession();
  if (existing.conversationId && existing.conversationId.trim()) {
    return existing.conversationId.trim();
  }
  const nextId =
    typeof globalThis.crypto?.randomUUID === "function"
      ? globalThis.crypto.randomUUID()
      : `convo-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  saveActiveSession({ conversationId: nextId });
  return nextId;
}

export function createNextConversationId(): string {
  const nextId =
    typeof globalThis.crypto?.randomUUID === "function"
      ? globalThis.crypto.randomUUID()
      : `convo-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  saveActiveSession({ conversationId: nextId });
  return nextId;
}

export function getConversationStorageKey(conversationId: string): string {
  return `hinaa-messages-${conversationId}`;
}

export function saveConversationMessages(conversationId: string, messages: TranscriptMessage[]): void {
  if (typeof window === "undefined" || !conversationId) return;
  try {
    window.localStorage.setItem(getConversationStorageKey(conversationId), JSON.stringify(messages));
  } catch (err) {
    console.warn("Failed to persist conversation messages:", err);
  }
}

export function loadConversationMessages(conversationId: string): TranscriptMessage[] | null {
  if (typeof window === "undefined" || !conversationId) return null;
  try {
    const raw = window.localStorage.getItem(getConversationStorageKey(conversationId));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return null;
    return parsed.map((message: any) => {
      if (message.role !== "assistant" || !message.content) return message;
      const plan = deserializeAssistantTurn(message.content);
      return plan
        ? { ...message, text: getAssistantDisplayText(message.content), plan }
        : message;
    });
  } catch {
    return null;
  }
}
