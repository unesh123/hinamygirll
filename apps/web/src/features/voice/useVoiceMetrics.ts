/**
 * useVoiceMetrics.ts — Instruments the existing HINAA voice pipeline
 * with latency measurements. Non-invasive: wraps existing hooks,
 * does not modify useAudioPlayback or useLiveConversation.
 */
import { useCallback, useRef } from "react";
import {
  startSession,
  startTurn,
  markFirstToken,
  markFirstAudio,
  markInterruption,
  markPlaybackStop,
  markResponseComplete,
  endTurn,
  endSession,
  setLipSyncDrift,
  type VoiceTurnMetrics,
  type VoiceSessionMetrics,
  computeLatencies,
  summarizeSession,
} from "./voiceMetrics";

export interface VoiceMetricsController {
  /** Call when user speech ends (VAD close) */
  onSpeechEnd: (turnId?: string) => void;
  /** Call when first LLM streaming token arrives */
  onFirstToken: () => void;
  /** Call when TTS audio first starts playing */
  onFirstAudio: () => void;
  /** Call when user interrupts */
  onInterruption: () => void;
  /** Call when playback fully stops after interruption */
  onPlaybackStop: () => void;
  /** Call when the full response is complete */
  onResponseComplete: () => void;
  /** Call to measure lip-sync drift (ms) */
  setLipSyncDrift: (driftMs: number) => void;
  /** Get the metrics for the current turn */
  getCurrentMetrics: () => Partial<VoiceTurnMetrics> | null;
  /** End the current session and get summary */
  getSessionSummary: () => string | null;
  /** Get raw session data */
  getSession: () => VoiceSessionMetrics | null;
}

export function useVoiceMetrics(): VoiceMetricsController {
  const sessionStarted = useRef(false);

  const ensureSession = useCallback(() => {
    if (!sessionStarted.current) {
      startSession();
      sessionStarted.current = true;
    }
  }, []);

  const onSpeechEnd = useCallback(
    (turnId?: string) => {
      ensureSession();
      startTurn(turnId);
    },
    [ensureSession],
  );

  const onFirstToken = useCallback(() => {
    markFirstToken();
  }, []);

  const onFirstAudio = useCallback(() => {
    markFirstAudio();
  }, []);

  const onInterruption = useCallback(() => {
    markInterruption();
  }, []);

  const onPlaybackStop = useCallback(() => {
    markPlaybackStop();
  }, []);

  const onResponseComplete = useCallback(() => {
    markResponseComplete();
    endTurn();
  }, []);

  const setLipSyncDriftValue = useCallback((driftMs: number) => {
    setLipSyncDrift(driftMs);
  }, []);

  const getCurrentMetrics = useCallback(() => {
    const session = getCurrentSessionRef();
    if (!session || session.turns.length === 0) return null;
    return session.turns[session.turns.length - 1] as Partial<VoiceTurnMetrics>;
  }, []);

  const getSessionSummary = useCallback(() => {
    const session = endSession();
    sessionStarted.current = false;
    if (!session) return null;
    return summarizeSession(session);
  }, []);

  const getSession = useCallback(() => {
    return getCurrentSessionRef();
  }, []);

  return {
    onSpeechEnd,
    onFirstToken,
    onFirstAudio,
    onInterruption,
    onPlaybackStop,
    onResponseComplete,
    setLipSyncDrift: setLipSyncDriftValue,
    getCurrentMetrics,
    getSessionSummary,
    getSession,
  };
}

/** Internal helper — read current session without importing at call time */
function getCurrentSessionRef() {
  // Lazy import to avoid circular deps
  const { getCurrentSession } = require("./voiceMetrics");
  return getCurrentSession();
}
