import { useCallback, useEffect, useRef, useState } from "react";
import { createLipSyncTimeline, textToVisemeEvents, getActiveViseme, type VisemeEvent } from "./textToViseme";

export interface PlaybackController {
  playing: boolean;
  muted: boolean;
  hasReplay: boolean;
  jawEnergy: React.MutableRefObject<number>;
  /** Live ref reflecting whether audio is actually producing sound right now.
   *  This is the single timing authority for avatar lip-sync. */
  playingRef: React.MutableRefObject<boolean>;
  /** Current viseme events for the active utterance — drives avatar mouth */
  visemeEvents: React.MutableRefObject<VisemeEvent[]>;
  /** AudioContext time when current audio started (for playback clock sync) */
  audioStartTimeRef: React.MutableRefObject<number>;
  play: (
    blob: Blob,
    spokenText?: string,
    onStarted?: () => void,
    onEnded?: () => void,
    providerVisemes?: VisemeEvent[],
  ) => Promise<void>;
  /** Speak through the browser's local speech engine when no intelligible TTS provider is available. */
  speakBrowser: (spokenText: string, language?: string) => Promise<boolean>;
  replay: () => Promise<void>;
  stop: () => void;
  toggleMute: () => void;
}

/**
 * Gapless, stall-proof speech playback with viseme-based lip-sync.
 */
export function useAudioPlayback(): PlaybackController {
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const [hasReplay, setHasReplay] = useState(false);
  
  // Use refs instead of state for 60fps high-frequency updates
  const jawEnergy = useRef(0);
  const visemeEvents = useRef<VisemeEvent[]>([]);
  const audioStartTimeRef = useRef(0);

  const contextRef = useRef<AudioContext | null>(null);
  const masterRef = useRef<GainNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourcesRef = useRef<Set<AudioBufferSourceNode>>(new Set());
  const endedAtRef = useRef(0);
  const lastBlobRef = useRef<Blob | null>(null);
  const lastTextRef = useRef<string>("");
  const sessionRef = useRef(0);
  const frameRef = useRef<number | undefined>(undefined);
  const mutedRef = useRef(false);
  const playingRef = useRef(false);
  const browserSpeechActiveRef = useRef(false);
  const browserWatchdogRef = useRef<number | undefined>(undefined);
  const lastBrowserSpeechRef = useRef<{ text: string; language: string } | null>(null);

  const ensureGraph = useCallback(() => {
    if (contextRef.current) return contextRef.current;
    const context = new AudioContext({ latencyHint: "interactive" });
    const master = context.createGain();
    master.gain.value = mutedRef.current ? 0 : 1;
    const analyser = context.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.55;
    master.connect(analyser);
    analyser.connect(context.destination);
    contextRef.current = context;
    masterRef.current = master;
    analyserRef.current = analyser;
    // Expose globally so AvatarPresence Model can read the playback clock
    // across the React Three Fiber Canvas boundary (refs can't cross Canvas)
    (window as any).__hinaaAudioCtx = context;
    return context;
  }, []);

  const syncPlaying = useCallback(() => {
    const next = sourcesRef.current.size > 0 || browserSpeechActiveRef.current;
    if (next === playingRef.current) return;
    playingRef.current = next;
    if (!next) {
      // Playback stopped/ended: immediately close the mouth.
      if (frameRef.current !== undefined) {
        window.cancelAnimationFrame(frameRef.current);
        frameRef.current = undefined;
      }
      jawEnergy.current = 0;
      visemeEvents.current = [];
    }
    setPlaying(next);
  }, []);

  const stop = useCallback(() => {
    sessionRef.current += 1;
    browserSpeechActiveRef.current = false;
    if (browserWatchdogRef.current !== undefined) {
      window.clearTimeout(browserWatchdogRef.current);
      browserWatchdogRef.current = undefined;
    }
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      try {
        window.speechSynthesis.cancel();
      } catch {
        // Browser speech is optional; stopping decoded audio must still work.
      }
    }
    for (const source of sourcesRef.current) {
      try {
        source.onended = null;
        source.stop();
      } catch {
        // Already stopped — nothing to do.
      }
    }
    sourcesRef.current.clear();
    endedAtRef.current = 0;
    if (frameRef.current !== undefined) {
      window.cancelAnimationFrame(frameRef.current);
      frameRef.current = undefined;
    }
    jawEnergy.current = 0;
    visemeEvents.current = [];
    syncPlaying();
  }, [syncPlaying]);

  const play = useCallback(
    async (
      blob: Blob,
      spokenText?: string,
      onStarted?: () => void,
      onEnded?: () => void,
      providerVisemes?: VisemeEvent[],
    ) => {
      const session = sessionRef.current;
      let context: AudioContext;
      try {
        context = ensureGraph();
      } catch (e) {
        console.warn("[HINAA] AudioContext creation failed:", e);
        onEnded?.();
        return;
      }
      if (context.state === "suspended") {
        try {
          await context.resume();
        } catch {
          onEnded?.();
          return;
        }
      }
      if (session !== sessionRef.current) {
        onEnded?.();
        return;
      }

      let bytes: ArrayBuffer;
      let buffer: AudioBuffer;
      try {
        bytes = await blob.arrayBuffer();
        if (session !== sessionRef.current) {
          onEnded?.();
          return;
        }
        buffer = await context.decodeAudioData(bytes);
      } catch (e) {
        console.warn("[HINAA] Audio decode failed:", e);
        onEnded?.();
        return;
      }
      if (session !== sessionRef.current || !masterRef.current) {
        onEnded?.();
        return;
      }

      lastBlobRef.current = blob;
      if (spokenText) lastTextRef.current = spokenText;
      setHasReplay(true);

      const source = context.createBufferSource();
      source.buffer = buffer;
      source.connect(masterRef.current);

      // Gapless, click-free seam: schedule exactly where the previous chunk
      // ends (no negative overlap — that double-plays 25ms at every chunk
      // seam). If the queue has drained, start promptly instead.
      const previousEndedAt = endedAtRef.current;
      const isContinuation = previousEndedAt > context.currentTime;
      const startAt = Math.max(context.currentTime + 0.02, previousEndedAt);
      endedAtRef.current = startAt + buffer.duration;
      sourcesRef.current.add(source);
      syncPlaying();

      // Build viseme timeline from spoken text + audio duration.
      // For streamed chunks the queue is still hot (isContinuation), so this
      // chunk's syllables must APPEND to the existing timeline at the right
      // offset — replacing it would jerk the mouth back to the start of the
      // sentence on every packet.
      if ((spokenText || providerVisemes?.length) && buffer.duration > 0) {
        const durationMs = buffer.duration * 1000;
        if (isContinuation && visemeEvents.current.length > 0) {
          const offsetMs = Math.max(
            0,
            (startAt - audioStartTimeRef.current) * 1000,
          );
          visemeEvents.current = visemeEvents.current.concat(
            createLipSyncTimeline({
              text: spokenText,
              durationMs,
              startMs: offsetMs,
              providerEvents: providerVisemes,
            }),
          );
        } else {
          visemeEvents.current = createLipSyncTimeline({
            text: spokenText,
            durationMs,
            providerEvents: providerVisemes,
          });
          audioStartTimeRef.current = startAt;
        }
      }

      let endedDispatched = false;
      const dispatchEnded = () => {
        if (!endedDispatched) {
          endedDispatched = true;
          onEnded?.();
        }
      };

      source.onended = () => {
        sourcesRef.current.delete(source);
        syncPlaying();
        dispatchEnded();
      };
      // Watchdog for stuck sources
      window.setTimeout(() => {
        if (sourcesRef.current.has(source)) {
          sourcesRef.current.delete(source);
          syncPlaying();
          dispatchEnded();
        }
      }, Math.ceil((buffer.duration + 2) * 1000));

      try {
        source.start(startAt);
      } catch (e) {
        console.warn("[HINAA] AudioBufferSource start failed:", e);
        sourcesRef.current.delete(source);
        syncPlaying();
        dispatchEnded();
        return;
      }

      // Jaw-energy analyser loop — drives amplitude scaling of viseme weights
      if (frameRef.current === undefined && analyserRef.current) {
        const analyser = analyserRef.current;
        const samples = new Uint8Array(analyser.fftSize);
        const tick = () => {
          analyser.getByteTimeDomainData(samples);
          let sum = 0;
          for (const value of samples) sum += ((value - 128) / 128) ** 2;
          const rms = Math.sqrt(sum / samples.length);
          // Fast attack captures syllable openings; slower release keeps the
          // mouth from snapping shut between quiet consonants or streamed audio
          // packets. This path also drives live audio when no text timing exists.
          const target = Math.min(1, rms * 7.5);
          const attack = target > jawEnergy.current ? 0.66 : 0.16;
          jawEnergy.current += (target - jawEnergy.current) * attack;
          frameRef.current = window.requestAnimationFrame(tick);
        };
        frameRef.current = window.requestAnimationFrame(tick);
      }

      onStarted?.();
    },
    [ensureGraph, syncPlaying],
  );

  const speakBrowser = useCallback(
    async (spokenText: string, language = "en-US"): Promise<boolean> => {
      const text = spokenText.trim();
      if (
        !text ||
        mutedRef.current ||
        typeof window === "undefined" ||
        !("speechSynthesis" in window) ||
        typeof SpeechSynthesisUtterance === "undefined"
      ) {
        return false;
      }

      const engine = window.speechSynthesis;
      if (!engine) return false;
      stop();

      const utterance = new SpeechSynthesisUtterance(text);
      const normalizedLanguage = language === "mixed" ? "hi-IN" : language;
      utterance.lang = normalizedLanguage;
      utterance.rate = 0.93;
      utterance.pitch = 1.04;
      utterance.volume = 1;

      const matchingVoice = engine
        .getVoices()
        .find((voice) => voice.lang.toLowerCase().startsWith(normalizedLanguage.slice(0, 2).toLowerCase()));
      if (matchingVoice) utterance.voice = matchingVoice;

      let context: AudioContext | null = null;
      try {
        context = ensureGraph();
        if (context.state === "suspended") await context.resume();
      } catch {
        // Browser speech remains usable without an AudioContext; the avatar uses
        // the text-derived viseme timeline below.
      }

      const estimatedDurationMs = Math.min(
        22_000,
        Math.max(700, text.trim().split(/\s+/).length * 310),
      );
      lastBrowserSpeechRef.current = { text, language: normalizedLanguage };
      browserSpeechActiveRef.current = true;
      visemeEvents.current = textToVisemeEvents(text, estimatedDurationMs);
      audioStartTimeRef.current = context?.currentTime ?? 0;
      syncPlaying();

      const finish = () => {
        if (!browserSpeechActiveRef.current) return; // idempotent — onend/onerror/watchdog race
        browserSpeechActiveRef.current = false;
        if (browserWatchdogRef.current !== undefined) {
          window.clearTimeout(browserWatchdogRef.current);
          browserWatchdogRef.current = undefined;
        }
        if (frameRef.current !== undefined) {
          window.cancelAnimationFrame(frameRef.current);
          frameRef.current = undefined;
        }
        jawEnergy.current = 0;
        syncPlaying();
      };
      utterance.onend = finish;
      utterance.onerror = finish;

      try {
        engine.speak(utterance);
        // Real-time syllable modulation & viseme sync for browser speech
        if (frameRef.current !== undefined) {
          window.cancelAnimationFrame(frameRef.current);
          frameRef.current = undefined;
        }
        const speechStartTime = performance.now();
        const tick = () => {
          if (!browserSpeechActiveRef.current) {
            jawEnergy.current = 0;
            return;
          }
          const elapsedMs = performance.now() - speechStartTime;
          const currentViseme = getActiveViseme(elapsedMs, visemeEvents.current);
          if (currentViseme && currentViseme.mouth !== "closed") {
            // Modulate active phoneme weight with natural acoustic vibration
            const pulse = 0.72 + 0.28 * Math.sin(elapsedMs * 0.024);
            const targetEnergy = Math.min(1.0, Math.max(0.18, (currentViseme.weight || 0.8) * pulse));
            jawEnergy.current += (targetEnergy - jawEnergy.current) * 0.45;
          } else {
            // Natural syllable cadence (~5 Hz) between words and during phrase transitions
            const tSec = elapsedMs / 1000;
            const syllableOsc = 0.42 + 0.34 * Math.sin(tSec * 2 * Math.PI * 4.9) + 0.14 * Math.sin(tSec * 2 * Math.PI * 8.4);
            const targetEnergy = Math.min(0.88, Math.max(0.08, syllableOsc));
            jawEnergy.current += (targetEnergy - jawEnergy.current) * 0.35;
          }
          frameRef.current = window.requestAnimationFrame(tick);
        };
        frameRef.current = window.requestAnimationFrame(tick);

        // Chrome has a long-standing bug where speechSynthesis silently stops
        // producing audio (or never fires onend after a pause) — the avatar
        // would then pose "playing" forever and the conversation would hang.
        // A generous watchdog guarantees the UI always recovers.
        browserWatchdogRef.current = window.setTimeout(() => {
          browserWatchdogRef.current = undefined;
          if (!browserSpeechActiveRef.current) return;
          try {
            engine.cancel();
          } catch {
            // best-effort
          }
          finish();
        }, estimatedDurationMs + 5_000);
        return true;
      } catch {
        finish();
        return false;
      }
    },
    [ensureGraph, stop, syncPlaying],
  );

  const replay = useCallback(async () => {
    if (lastBlobRef.current) {
      await play(lastBlobRef.current, lastTextRef.current);
      return;
    }
    if (lastBrowserSpeechRef.current) {
      await speakBrowser(
        lastBrowserSpeechRef.current.text,
        lastBrowserSpeechRef.current.language,
      );
    }
  }, [play, speakBrowser]);

  const toggleMute = useCallback(() => {
    mutedRef.current = !mutedRef.current;
    setMuted(mutedRef.current);
    if (masterRef.current)
      masterRef.current.gain.value = mutedRef.current ? 0 : 1;
    // The browser speech engine bypasses the AudioContext gain graph
    // entirely, so muting must hard-stop any in-flight utterance.
    if (mutedRef.current && browserSpeechActiveRef.current) {
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        try {
          window.speechSynthesis.cancel();
        } catch {
          // best-effort
        }
      }
      browserSpeechActiveRef.current = false;
      if (browserWatchdogRef.current !== undefined) {
        window.clearTimeout(browserWatchdogRef.current);
        browserWatchdogRef.current = undefined;
      }
      syncPlaying();
    }
  }, [syncPlaying]);

  useEffect(
    () => () => {
      sessionRef.current += 1;
      for (const source of sourcesRef.current) {
        try {
          source.onended = null;
          source.stop();
        } catch {}
      }
      sourcesRef.current.clear();
      if (frameRef.current !== undefined)
        window.cancelAnimationFrame(frameRef.current);
      if (contextRef.current?.state !== "closed")
        void contextRef.current?.close();
      browserSpeechActiveRef.current = false;
      if (browserWatchdogRef.current !== undefined) {
        window.clearTimeout(browserWatchdogRef.current);
        browserWatchdogRef.current = undefined;
      }
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        try {
          window.speechSynthesis.cancel();
        } catch {
          // Browser speech is optional during teardown.
        }
      }
      contextRef.current = null;
      masterRef.current = null;
      analyserRef.current = null;
    },
    [],
  );

  return {
    playing,
    muted,
    hasReplay,
    jawEnergy,
    playingRef,
    visemeEvents,
    audioStartTimeRef,
    play,
    speakBrowser,
    replay,
    stop,
    toggleMute,
  };
}
