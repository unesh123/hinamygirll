import { useCallback, useEffect, useRef, useState } from "react";
import { textToVisemeEvents, getActiveViseme, type VisemeEvent } from "./textToViseme";

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
  play: (blob: Blob, spokenText?: string, onStarted?: () => void) => Promise<void>;
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
    const next = sourcesRef.current.size > 0;
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
    async (blob: Blob, spokenText?: string, onStarted?: () => void) => {
      const session = sessionRef.current;
      let context: AudioContext;
      try {
        context = ensureGraph();
      } catch {
        return;
      }
      if (context.state === "suspended") {
        try {
          await context.resume();
        } catch {
          return;
        }
      }
      if (session !== sessionRef.current) return;

      let bytes: ArrayBuffer;
      let buffer: AudioBuffer;
      try {
        bytes = await blob.arrayBuffer();
        if (session !== sessionRef.current) return;
        buffer = await context.decodeAudioData(bytes);
      } catch {
        return;
      }
      if (session !== sessionRef.current || !masterRef.current) return;

      lastBlobRef.current = blob;
      if (spokenText) lastTextRef.current = spokenText;
      setHasReplay(true);

      const source = context.createBufferSource();
      source.buffer = buffer;
      source.connect(masterRef.current);

      const startAt = Math.max(
        context.currentTime + 0.02,
        endedAtRef.current - 0.025,
      );
      endedAtRef.current = startAt + buffer.duration;
      sourcesRef.current.add(source);
      syncPlaying();

      // Build viseme timeline from spoken text + audio duration
      if (spokenText && buffer.duration > 0) {
        const durationMs = buffer.duration * 1000;
        visemeEvents.current = textToVisemeEvents(spokenText, durationMs);
        audioStartTimeRef.current = startAt;
      }

      source.onended = () => {
        sourcesRef.current.delete(source);
        syncPlaying();
      };
      // Watchdog for stuck sources
      window.setTimeout(() => {
        if (sourcesRef.current.has(source)) {
          sourcesRef.current.delete(source);
          syncPlaying();
        }
      }, Math.ceil((buffer.duration + 2) * 1000));

      try {
        source.start(startAt);
      } catch {
        sourcesRef.current.delete(source);
        syncPlaying();
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
          // Smooth jaw energy — used as amplitude scale for viseme weights
          jawEnergy.current = jawEnergy.current * 0.60 + Math.min(1, rms * 5.5) * 0.40;
          frameRef.current = window.requestAnimationFrame(tick);
        };
        frameRef.current = window.requestAnimationFrame(tick);
      }

      onStarted?.();
    },
    [ensureGraph, syncPlaying],
  );

  const replay = useCallback(async () => {
    if (lastBlobRef.current) await play(lastBlobRef.current, lastTextRef.current);
  }, [play]);

  const toggleMute = useCallback(() => {
    mutedRef.current = !mutedRef.current;
    setMuted(mutedRef.current);
    if (masterRef.current)
      masterRef.current.gain.value = mutedRef.current ? 0 : 1;
  }, []);

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
    replay,
    stop,
    toggleMute,
  };
}
