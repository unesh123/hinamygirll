import { createContext, type MutableRefObject } from "react";
import { getActiveViseme, type VisemeEvent } from "./textToViseme";
import type { SpeechTimingSource } from "./speechTimingSource";

/** Shared by DOM and R3F surfaces; only the playback controller owns this clock. */
export interface SpeechPlayback {
  utteranceId: number;
  state: "idle" | "queued" | "playing" | "paused";
  source: "none" | "audio" | "browser";
  timingSource: "none" | "provider" | "text" | "browser-boundary";
  events: VisemeEvent[];
  calibrationMs: number;
  elapsedMs: () => number;
  timing?: SpeechTimingSource | null;
}

export function idleSpeechPlayback(utteranceId = 0): SpeechPlayback {
  return { utteranceId, state: "idle", source: "none", timingSource: "none", events: [], calibrationMs: 0, elapsedMs: () => 0, timing: null };
}

export type SpeechPlaybackBridge = MutableRefObject<SpeechPlayback>;
export const SpeechPlaybackContext = createContext<SpeechPlaybackBridge | null>(null);

export function sampleSpeechPlayback(bridge: SpeechPlaybackBridge) {
  const speech = bridge.current;
  const rawTime = speech.timing ? speech.timing.getPlaybackTime() : speech.elapsedMs();
  const elapsedMs = rawTime - speech.calibrationMs;
  const isTimingPlaying = speech.timing ? speech.timing.isPlaying() : true;
  const speaking = speech.state === "playing" && isTimingPlaying && elapsedMs >= 0;
  const activeViseme = speaking
    ? (speech.timing ? speech.timing.getVisemeAt(elapsedMs) : getActiveViseme(elapsedMs, speech.events))
    : null;
  return { ...speech, speaking, timeMs: Math.max(0, elapsedMs), viseme: activeViseme };
}

