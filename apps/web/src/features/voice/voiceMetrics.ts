/**
 * voiceMetrics.ts — HINAA Voice Pipeline Latency Instrumentation
 *
 * Captures measurable voice performance data at each stage of the pipeline.
 * All timestamps use performance.now() for sub-millisecond precision.
 */

export interface VoiceTurnMetrics {
  /** Unique turn identifier */
  turnId: string;
  /** Timestamp when user stopped speaking (VAD close) */
  speechEndMs: number;
  /** Timestamp when first LLM token was received */
  firstTokenMs?: number;
  /** Timestamp when TTS audio first started playing */
  firstAudioMs?: number;
  /** Timestamp when interruption was detected */
  interruptionMs?: number;
  /** Timestamp when playback fully stopped after interruption */
  playbackStopMs?: number;
  /** Timestamp when response completed (final audio chunk) */
  responseCompleteMs?: number;
  /** Provider used for STT */
  sttProvider?: string;
  /** Provider used for LLM */
  llmProvider?: string;
  /** Provider used for TTS */
  ttsProvider?: string;
  /** Whether this turn was interrupted */
  interrupted: boolean;
  /** Dropped audio chunks during playback */
  droppedChunks: number;
  /** Reordered audio chunks during playback */
  reorderedChunks: number;
  /** WebSocket reconnects during this turn */
  reconnects: number;
  /** Lip-sync drift in ms (measured) */
  lipSyncDriftMs?: number;
}

export interface VoiceSessionMetrics {
  sessionId: string;
  startedAt: number;
  turns: VoiceTurnMetrics[];
  totalReconnects: number;
  totalDroppedChunks: number;
}

/** Singleton metrics store for the current session */
let currentSession: VoiceSessionMetrics | null = null;
let currentTurn: Partial<VoiceTurnMetrics> | null = null;

export function startSession(): VoiceSessionMetrics {
  currentSession = {
    sessionId: `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    startedAt: performance.now(),
    turns: [],
    totalReconnects: 0,
    totalDroppedChunks: 0,
  };
  return currentSession;
}

export function startTurn(turnId?: string): void {
  currentTurn = {
    turnId: turnId || `turn-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    speechEndMs: performance.now(),
    interrupted: false,
    droppedChunks: 0,
    reorderedChunks: 0,
    reconnects: 0,
  };
}

export function markFirstToken(): void {
  if (currentTurn) {
    currentTurn.firstTokenMs = performance.now();
  }
}

export function markFirstAudio(): void {
  if (currentTurn) {
    currentTurn.firstAudioMs = performance.now();
  }
}

export function markInterruption(): void {
  if (currentTurn) {
    currentTurn.interruptionMs = performance.now();
    currentTurn.interrupted = true;
  }
}

export function markPlaybackStop(): void {
  if (currentTurn) {
    currentTurn.playbackStopMs = performance.now();
  }
}

export function markResponseComplete(): void {
  if (currentTurn) {
    currentTurn.responseCompleteMs = performance.now();
  }
}

export function setProviders(stt?: string, llm?: string, tts?: string): void {
  if (currentTurn) {
    if (stt) currentTurn.sttProvider = stt;
    if (llm) currentTurn.llmProvider = llm;
    if (tts) currentTurn.ttsProvider = tts;
  }
}

export function recordDroppedChunk(): void {
  if (currentTurn) currentTurn.droppedChunks++;
  if (currentSession) currentSession.totalDroppedChunks++;
}

export function recordReorderedChunk(): void {
  if (currentTurn) currentTurn.reorderedChunks++;
}

export function recordReconnect(): void {
  if (currentTurn) currentTurn.reconnects++;
  if (currentSession) currentSession.totalReconnects++;
}

export function setLipSyncDrift(driftMs: number): void {
  if (currentTurn) currentTurn.lipSyncDriftMs = driftMs;
}

export function endTurn(): VoiceTurnMetrics | null {
  if (!currentTurn || !currentSession) return null;
  const metrics = currentTurn as VoiceTurnMetrics;
  currentSession.turns.push(metrics);
  currentTurn = null;
  return metrics;
}

export function endSession(): VoiceSessionMetrics | null {
  if (currentTurn) endTurn();
  const session = currentSession;
  currentSession = null;
  return session;
}

export function getCurrentSession(): VoiceSessionMetrics | null {
  return currentSession;
}

/**
 * Compute derived latency measurements from a completed turn.
 */
export function computeLatencies(turn: VoiceTurnMetrics) {
  const speechEnd = turn.speechEndMs;
  return {
    /** Speech-end → first LLM token (ms) */
    ttft: turn.firstTokenMs ? turn.firstTokenMs - speechEnd : null,
    /** Speech-end → first audio playing (ms) */
    tta: turn.firstAudioMs ? turn.firstAudioMs - speechEnd : null,
    /** Speech-end → playback stop after interruption (ms) */
    interruptionLatency: turn.interruptionMs && turn.playbackStopMs
      ? turn.playbackStopMs - turn.interruptionMs
      : null,
    /** Total response time (ms) */
    totalResponseTime: turn.responseCompleteMs
      ? turn.responseCompleteMs - speechEnd
      : null,
    /** Lip-sync drift (ms) */
    lipSyncDrift: turn.lipSyncDriftMs ?? null,
  };
}

/**
 * Generate a human-readable summary of session metrics.
 */
export function summarizeSession(session: VoiceSessionMetrics): string {
  if (session.turns.length === 0) return "No turns completed.";

  const latencies = session.turns.map(computeLatencies);
  const ttfts = latencies.map((l) => l.ttft).filter((v): v is number => v !== null);
  const ttas = latencies.map((l) => l.tta).filter((v): v is number => v !== null);
  const drifts = latencies
    .map((l) => l.lipSyncDrift)
    .filter((v): v is number => v !== null);

  const avg = (arr: number[]) => (arr.length ? Math.round(arr.reduce((a, b) => a + b, 0) / arr.length) : null);
  const p95 = (arr: number[]) => {
    if (!arr.length) return null;
    const sorted = [...arr].sort((a, b) => a - b);
    return Math.round(sorted[Math.floor(sorted.length * 0.95)]);
  };

  return [
    `Voice Session: ${session.turns.length} turns`,
    `Avg TTFT: ${avg(ttfts)}ms (p95: ${p95(ttfts)}ms)`,
    `Avg TTA: ${avg(ttas)}ms (p95: ${p95(ttas)}ms)`,
    `Avg Lip-sync drift: ${avg(drifts)}ms`,
    `Dropped chunks: ${session.totalDroppedChunks}`,
    `Reconnects: ${session.totalReconnects}`,
    `Interruptions: ${session.turns.filter((t) => t.interrupted).length}`,
  ].join("\n");
}
