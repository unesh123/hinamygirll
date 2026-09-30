import { useCallback, useEffect, useRef, useState } from "react";
import { createLipSyncTimeline, textToVisemeEvents, getActiveViseme, type VisemeEvent } from "./textToViseme";
import { idleSpeechPlayback, type SpeechPlaybackBridge } from "./speechPlaybackBridge";
import { WebAudioSpeechTimingSource, BrowserSpeechTimingSource } from "./speechTimingSource";

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
  speech: SpeechPlaybackBridge;
  isAudioBlocked: () => boolean;
  unlockAudio: () => Promise<void>;
  play: (
    blob: Blob,
    spokenText?: string,
    onStarted?: () => void,
    onEnded?: () => void,
    providerVisemes?: VisemeEvent[],
  ) => Promise<void>;
  /** Speak through the browser's local speech engine when no intelligible TTS provider is available. */
  speakBrowser: (spokenText: string, language?: string, companionId?: string) => Promise<boolean>;
  speakStreamChunk: (
    chunkText: string,
    isFirst: boolean,
    language?: string,
    companionId?: string,
  ) => Promise<boolean>;
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
  const speech = useRef(idleSpeechPlayback());

  const contextRef = useRef<AudioContext | null>(null);
  const masterRef = useRef<GainNode | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourcesRef = useRef<Set<AudioBufferSourceNode>>(new Set());
  const endedAtRef = useRef(0);
  const lastBlobRef = useRef<Blob | null>(null);
  const lastTextRef = useRef<string>("");
  const lastProviderVisemesRef = useRef<VisemeEvent[] | undefined>(undefined);
  const sessionRef = useRef(0);
  const frameRef = useRef<number | undefined>(undefined);
  const mutedRef = useRef(false);
  const playingRef = useRef(false);
  const browserSpeechActiveRef = useRef(false);
  const streamChunkQueueRef = useRef<SpeechSynthesisUtterance[]>([]);
  const streamActiveRef = useRef(false);
  const browserWatchdogRef = useRef<number | undefined>(undefined);
  const lastBrowserSpeechRef = useRef<{ text: string; language: string; companionId?: string } | null>(null);

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
    if (typeof window !== "undefined") {
      (window as any).__hinaaAudioCtx = context;
    }
    return context;
  }, []);

  const syncPlaying = useCallback(() => {
    const next = sourcesRef.current.size > 0 || browserSpeechActiveRef.current;
    playingRef.current = next;
    if (!next) {
      // Playback stopped/ended: immediately close the mouth.
      if (frameRef.current !== undefined) {
        window.cancelAnimationFrame(frameRef.current);
        frameRef.current = undefined;
      }
      jawEnergy.current = 0;
      visemeEvents.current = [];
      speech.current = idleSpeechPlayback(speech.current.utteranceId);
    }
    setPlaying(next);
  }, []);

  const stop = useCallback(() => {
    sessionRef.current += 1;
    browserSpeechActiveRef.current = false;
    streamActiveRef.current = false;
    streamChunkQueueRef.current = [];
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
    if (typeof window !== "undefined") {
      (window as any).__hinaaAudioStartTime = 0;
    }
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
      lastTextRef.current = spokenText ?? "";
      lastProviderVisemesRef.current = providerVisemes;
      lastBrowserSpeechRef.current = null;
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
      if (!isContinuation) audioStartTimeRef.current = startAt;
      if (typeof window !== "undefined") {
        (window as any).__hinaaAudioStartTime = audioStartTimeRef.current;
      }
      const calibrationMs = speech.current.calibrationMs;
      const totalDurationSec = isContinuation
        ? Math.max(buffer.duration, endedAtRef.current - audioStartTimeRef.current)
        : buffer.duration;
      const webAudioTiming = new WebAudioSpeechTimingSource({
        context,
        startTime: audioStartTimeRef.current,
        durationSeconds: totalDurationSec,
        visemes: visemeEvents.current,
        isPlaying: () => playingRef.current,
      });
      speech.current = {
        utteranceId: isContinuation ? speech.current.utteranceId : speech.current.utteranceId + 1,
        state: "playing", source: "audio", timingSource: providerVisemes?.length ? "provider" : "text",
        calibrationMs, events: visemeEvents.current,
        elapsedMs: () => context.state === "running" ? (context.currentTime - audioStartTimeRef.current) * 1000 : -1,
        timing: webAudioTiming,
      };

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
      }, Math.ceil((endedAtRef.current - context.currentTime + 2) * 1000));

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
    async (spokenText: string, language = "en-US", companionId = "hinaa"): Promise<boolean> => {
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
      const session = sessionRef.current;

      const utterance = new SpeechSynthesisUtterance(text);
      const normalizedLanguage = language === "mixed" ? "hi-IN" : language;
      utterance.lang = normalizedLanguage;

      const isHinaa = companionId !== "hiro";
      const allVoices = engine.getVoices();
      const langPrefix = normalizedLanguage.slice(0, 2).toLowerCase();
      const langVoices = allVoices.filter((v) =>
        v.lang.toLowerCase().startsWith(langPrefix),
      );
      const candidateVoices = langVoices.length > 0 ? langVoices : allVoices;

      const isMaleVoice = (name: string): boolean => {
        const lower = name.toLowerCase();
        // If it explicitly has female/girl/woman, it is NOT male!
        if (lower.includes("female") || lower.includes("girl") || lower.includes("woman")) {
          return false;
        }
        const malePatterns = [
          /\bdavid\b/i, /\bmark\b/i, /\bgeorge\b/i, /\bguy\b/i, /\bravi\b/i,
          /\bmadhur\b/i, /\bsagar\b/i, /\brichard\b/i, /\bjames\b/i, /\bsean\b/i,
          /\bboy\b/i, /\bmale\b/i, /microsoft david/i, /microsoft mark/i, /microsoft guy/i
        ];
        return malePatterns.some((pattern) => pattern.test(lower));
      };

      const isFemaleVoice = (name: string): boolean => {
        const lower = name.toLowerCase();
        const femalePatterns = [
          /\bzira\b/i, /\bjenny\b/i, /\baria\b/i, /\bswara\b/i, /\bhemkala\b/i,
          /\bsamantha\b/i, /\bvictoria\b/i, /\bkaren\b/i, /\bsonia\b/i, /\bheera\b/i,
          /\bneerja\b/i, /\bhazel\b/i, /\bsusan\b/i, /\bgirl\b/i, /\bfemale\b/i,
          /\bwoman\b/i, /natural.*female/i, /google us english/i, /microsoft zira/i,
          /microsoft jenny/i, /microsoft aria/i
        ];
        return femalePatterns.some((pattern) => pattern.test(lower));
      };

      const isIndianFemaleVoice = (voice: SpeechSynthesisVoice): boolean => {
        const lower = voice.name.toLowerCase();
        const vLang = voice.lang.toLowerCase();
        const indianPatterns = [
          /\bswara\b/i, /\bheera\b/i, /\bneerja\b/i, /\bhemkala\b/i,
          /\bkalpana\b/i, /\bshruti\b/i, /\bsunita\b/i, /google हिन्दी/i,
          /hi-in/i, /hindi/i,
        ];
        return (
          vLang.startsWith("hi") ||
          (vLang.includes("in") && !isMaleVoice(voice.name)) ||
          indianPatterns.some((pattern) => pattern.test(lower))
        );
      };

      let selectedVoice: SpeechSynthesisVoice | undefined;

      if (isHinaa) {
        const isHindiContext = normalizedLanguage.startsWith("hi") || /[\u0900-\u097F]/.test(text);
        if (isHindiContext) {
          selectedVoice =
            allVoices.find((v) => isIndianFemaleVoice(v)) ||
            candidateVoices.find((v) => isFemaleVoice(v.name));
        } else {
          selectedVoice =
            candidateVoices.find((v) => isFemaleVoice(v.name)) ||
            allVoices.find((v) => isIndianFemaleVoice(v)) ||
            allVoices.find((v) => isFemaleVoice(v.name));
        }
        // Priority 3: Any voice in candidates that is NOT male
        if (!selectedVoice) {
          selectedVoice = candidateVoices.find((v) => !isMaleVoice(v.name));
        }
        // Priority 4: Any voice across all voices that is NOT male
        if (!selectedVoice) {
          selectedVoice = allVoices.find((v) => !isMaleVoice(v.name));
        }
        // If strictly only male voices exist on this OS, pitch shift up high so it never sounds like a man
        if (!selectedVoice) {
          selectedVoice = candidateVoices[0] || allVoices[0];
          utterance.pitch = 1.35; // Feminine pitch shift
        } else {
          utterance.pitch = 1.18; // Sweet, lively anime companion pitch
        }
        utterance.rate = 1.05;
        utterance.volume = 1;
      } else {
        // Hiro companion: calm male voice
        selectedVoice = candidateVoices.find((v) => isMaleVoice(v.name)) || allVoices.find((v) => isMaleVoice(v.name));
        utterance.pitch = 0.96;
        utterance.rate = 1.0;
        utterance.volume = 1;
      }

      if (selectedVoice) utterance.voice = selectedVoice;

      const estimatedDurationMs = Math.min(
        180_000,
        Math.max(700, text.trim().split(/\s+/).length * 310),
      );
      lastBrowserSpeechRef.current = { text, language: normalizedLanguage, companionId };
      lastBlobRef.current = null;
      setHasReplay(true);
      visemeEvents.current = textToVisemeEvents(text, estimatedDurationMs);
      let startedAt: number | null = null;
      let pausedAt = 0;
      let boundaryOffset = 0;
      let finished = false;
      const browserTiming = new BrowserSpeechTimingSource({
        durationMs: estimatedDurationMs,
        visemes: visemeEvents.current,
      });
      speech.current = {
        utteranceId: session, state: "queued", source: "browser", timingSource: "text",
        calibrationMs: 0, events: visemeEvents.current,
        elapsedMs: () => startedAt !== null ? (pausedAt || performance.now()) - startedAt + boundaryOffset : -1,
        timing: browserTiming,
      };

      const finish = () => {
        if (session !== sessionRef.current || finished) return;
        finished = true;
        browserTiming.onUtteranceEnd();
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
      utterance.onstart = () => {
        if (session !== sessionRef.current || finished) return;
        startedAt = performance.now();
        browserTiming.onUtteranceStart();
        browserSpeechActiveRef.current = true;
        speech.current.state = "playing";
        syncPlaying();
        if (frameRef.current !== undefined) {
          window.cancelAnimationFrame(frameRef.current);
          frameRef.current = undefined;
        }
        const tick = () => {
          if (session !== sessionRef.current || !browserSpeechActiveRef.current || finished) {
            jawEnergy.current = 0;
            return;
          }
          const elapsedMs = speech.current.elapsedMs();
          const currentViseme = getActiveViseme(elapsedMs, visemeEvents.current);
          const targetEnergy = !pausedAt && currentViseme?.mouth !== "closed" ? currentViseme?.weight ?? 0 : 0;
          jawEnergy.current += (targetEnergy - jawEnergy.current) * (targetEnergy > jawEnergy.current ? 0.55 : 0.25);
          frameRef.current = window.requestAnimationFrame(tick);
        };
        frameRef.current = window.requestAnimationFrame(tick);
      };
      utterance.onboundary = (event) => {
        if (session !== sessionRef.current || finished || !browserSpeechActiveRef.current) return;
        if (event.name && event.name !== "word") return;
        // Re-anchor the remaining timeline at the actual spoken word. Browser
        // boundaries have no phoneme data, so only this word timing is measured.
        const index = Math.max(0, Math.min(text.length, event.charIndex));
        const remaining = text.slice(index);
        const elapsed = speech.current.elapsedMs();
        const duration = Math.max(200, remaining.trim().split(/\s+/).length * 310);
        visemeEvents.current = textToVisemeEvents(remaining, duration, elapsed);
        speech.current.events = visemeEvents.current;
        speech.current.timingSource = "browser-boundary";
        browserTiming.retarget({ startMs: elapsed, visemes: visemeEvents.current, durationMs: elapsed + duration });
      };
      utterance.onpause = () => {
        if (session !== sessionRef.current || finished) return;
        pausedAt = performance.now();
        browserTiming.onUtterancePause();
        speech.current.state = "paused";
        jawEnergy.current = 0;
      };
      utterance.onresume = () => {
        if (session !== sessionRef.current || finished) return;
        if (pausedAt) boundaryOffset -= performance.now() - pausedAt;
        pausedAt = 0;
        browserTiming.onUtteranceResume();
        speech.current.state = "playing";
      };

      try {
        engine.speak(utterance);
        // producing audio (or never fires onend after a pause) — the avatar
        // would then pose "playing" forever and the conversation would hang.
        // A generous watchdog guarantees the UI always recovers.
        browserWatchdogRef.current = window.setTimeout(() => {
          browserWatchdogRef.current = undefined;
          if (session !== sessionRef.current || finished) return;
          try {
            engine.cancel();
          } catch {
            // best-effort
          }
          finish();
        }, estimatedDurationMs * 2 + 10_000);
        return true;
      } catch {
        finish();
        return false;
      }
    },
    [stop, syncPlaying],
  );

  const speakStreamChunk = useCallback(
    async (
      chunkText: string,
      isFirst: boolean,
      language: string = "en-US",
      companionId?: string,
    ): Promise<boolean> => {
      if (typeof window === "undefined" || !("speechSynthesis" in window)) return false;
      const engine = window.speechSynthesis;
      if (!engine) return false;

      // Clean chunk text: strip markdown code, asterisks, URLs, brackets
      const clean = chunkText
        .replace(/```[\s\S]*?```/g, "")
        .replace(/`([^`]+)`/g, "$1")
        .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
        .replace(/https?:\/\/\S+/g, "")
        .replace(/[*_~#|]/g, "")
        .trim();

      if (clean.length < 2) return false;

      if (isFirst) {
        stop();
        streamChunkQueueRef.current = [];
        streamActiveRef.current = true;
      } else if (!streamActiveRef.current) {
        return false;
      }

      const session = sessionRef.current;
      const utterance = new SpeechSynthesisUtterance(clean);
      const normalizedLanguage = language === "mixed" ? "hi-IN" : language;
      utterance.lang = normalizedLanguage;

      const isHinaa = companionId !== "hiro";
      const allVoices = engine.getVoices();
      const langPrefix = normalizedLanguage.slice(0, 2).toLowerCase();
      const langVoices = allVoices.filter((v) =>
        v.lang.toLowerCase().startsWith(langPrefix),
      );
      const candidateVoices = langVoices.length > 0 ? langVoices : allVoices;

      const isMaleVoice = (name: string): boolean => {
        const lower = name.toLowerCase();
        if (lower.includes("female") || lower.includes("girl") || lower.includes("woman")) {
          return false;
        }
        const malePatterns = [
          /\bdavid\b/i, /\bmark\b/i, /\bgeorge\b/i, /\bguy\b/i, /\bravi\b/i,
          /\bmadhur\b/i, /\bsagar\b/i, /\brichard\b/i, /\bjames\b/i, /\bsean\b/i,
          /\bboy\b/i, /\bmale\b/i, /microsoft david/i, /microsoft mark/i, /microsoft guy/i,
        ];
        return malePatterns.some((pattern) => pattern.test(lower));
      };

      const isFemaleVoice = (name: string): boolean => {
        const lower = name.toLowerCase();
        const femalePatterns = [
          /\bzira\b/i, /\bjenny\b/i, /\baria\b/i, /\bswara\b/i, /\bhemkala\b/i,
          /\bsamantha\b/i, /\bvictoria\b/i, /\bkaren\b/i, /\bsonia\b/i, /\bheera\b/i,
          /\bneerja\b/i, /\bhazel\b/i, /\bsusan\b/i, /\bgirl\b/i, /\bfemale\b/i,
          /\bwoman\b/i, /natural.*female/i, /google us english/i, /microsoft zira/i,
          /microsoft jenny/i, /microsoft aria/i,
        ];
        return femalePatterns.some((pattern) => pattern.test(lower));
      };

      const isIndianFemaleVoice = (voice: SpeechSynthesisVoice): boolean => {
        const lower = voice.name.toLowerCase();
        const vLang = voice.lang.toLowerCase();
        const indianPatterns = [
          /\bswara\b/i, /\bheera\b/i, /\bneerja\b/i, /\bhemkala\b/i,
          /\bkalpana\b/i, /\bshruti\b/i, /\bsunita\b/i, /google हिन्दी/i,
          /hi-in/i, /hindi/i,
        ];
        return (
          vLang.startsWith("hi") ||
          (vLang.includes("in") && !isMaleVoice(voice.name)) ||
          indianPatterns.some((pattern) => pattern.test(lower))
        );
      };

      let selectedVoice: SpeechSynthesisVoice | undefined;
      if (isHinaa) {
        const isHindiContext = normalizedLanguage.startsWith("hi") || /[\u0900-\u097F]/.test(clean);
        if (isHindiContext) {
          selectedVoice =
            allVoices.find((v) => isIndianFemaleVoice(v)) ||
            candidateVoices.find((v) => isFemaleVoice(v.name));
        } else {
          selectedVoice =
            candidateVoices.find((v) => isFemaleVoice(v.name)) ||
            allVoices.find((v) => isIndianFemaleVoice(v)) ||
            allVoices.find((v) => isFemaleVoice(v.name));
        }
        if (!selectedVoice) {
          selectedVoice =
            candidateVoices.find((v) => !isMaleVoice(v.name)) ||
            allVoices.find((v) => !isMaleVoice(v.name));
        }
        utterance.pitch = selectedVoice ? 1.15 : 1.35;
        // High speed speech generation as requested by user
        utterance.rate = 1.18;
        utterance.volume = 1;
      } else {
        selectedVoice =
          candidateVoices.find((v) => isMaleVoice(v.name)) ||
          allVoices.find((v) => isMaleVoice(v.name));
        utterance.pitch = 0.96;
        utterance.rate = 1.05;
        utterance.volume = 1;
      }
      if (selectedVoice) utterance.voice = selectedVoice;

      const chunkDurationMs = Math.min(
        60_000,
        Math.max(500, clean.trim().split(/\s+/).length * 270),
      );

      const chunkVisemes = textToVisemeEvents(clean, chunkDurationMs);
      if (isFirst) {
        visemeEvents.current = chunkVisemes;
      } else {
        visemeEvents.current = [...visemeEvents.current, ...chunkVisemes];
      }

      let startedAt: number | null = null;
      let finished = false;

      const finish = () => {
        if (session !== sessionRef.current || finished) return;
        finished = true;
        const idx = streamChunkQueueRef.current.indexOf(utterance);
        if (idx !== -1) streamChunkQueueRef.current.splice(idx, 1);
        if (streamChunkQueueRef.current.length === 0) {
          streamActiveRef.current = false;
          browserSpeechActiveRef.current = false;
          jawEnergy.current = 0;
          if (frameRef.current !== undefined) {
            window.cancelAnimationFrame(frameRef.current);
            frameRef.current = undefined;
          }
          syncPlaying();
        }
      };

      utterance.onend = finish;
      utterance.onerror = finish;
      utterance.onstart = () => {
        if (session !== sessionRef.current || finished) return;
        startedAt = performance.now();
        browserSpeechActiveRef.current = true;
        speech.current.state = "playing";
        syncPlaying();
        if (frameRef.current !== undefined) {
          window.cancelAnimationFrame(frameRef.current);
          frameRef.current = undefined;
        }
        const tick = () => {
          if (session !== sessionRef.current || !browserSpeechActiveRef.current || finished) {
            jawEnergy.current = 0;
            return;
          }
          const elapsedMs = performance.now() - (startedAt || performance.now());
          const currentViseme = getActiveViseme(elapsedMs, chunkVisemes);
          const targetEnergy = currentViseme?.mouth !== "closed" ? currentViseme?.weight ?? 0 : 0;
          jawEnergy.current += (targetEnergy - jawEnergy.current) * (targetEnergy > jawEnergy.current ? 0.55 : 0.25);
          frameRef.current = window.requestAnimationFrame(tick);
        };
        frameRef.current = window.requestAnimationFrame(tick);
      };

      streamChunkQueueRef.current.push(utterance);
      try {
        engine.speak(utterance);
        return true;
      } catch {
        finish();
        return false;
      }
    },
    [stop, syncPlaying],
  );

  const replay = useCallback(async () => {
    if (lastBlobRef.current) {
      stop();
      await play(lastBlobRef.current, lastTextRef.current, undefined, undefined, lastProviderVisemesRef.current);
      return;
    }
    if (lastBrowserSpeechRef.current) {
      await speakBrowser(
        lastBrowserSpeechRef.current.text,
        lastBrowserSpeechRef.current.language,
        (lastBrowserSpeechRef.current as any).companionId,
      );
    }
  }, [play, speakBrowser, stop]);

  const toggleMute = useCallback(() => {
    mutedRef.current = !mutedRef.current;
    setMuted(mutedRef.current);
    if (masterRef.current)
      masterRef.current.gain.value = mutedRef.current ? 0 : 1;
    // The browser speech engine bypasses the AudioContext gain graph
    // entirely, so muting must hard-stop any in-flight utterance.
    if (mutedRef.current && speech.current.source === "browser") {
      sessionRef.current += 1;
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

  const isAudioBlocked = useCallback(() => contextRef.current?.state === "suspended", []);
  const unlockAudio = useCallback(async () => {
    if (contextRef.current?.state === "suspended") await contextRef.current.resume();
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
      speech.current = idleSpeechPlayback(sessionRef.current);
      playingRef.current = false;
      jawEnergy.current = 0;
      visemeEvents.current = [];
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

  useEffect(() => {
    const synth = typeof window !== "undefined" ? window.speechSynthesis : undefined;
    if (!synth) return;

    if (typeof synth.getVoices === "function") {
      synth.getVoices();
    }
    const onVoicesChanged = () => {
      if (typeof synth.getVoices === "function") {
        synth.getVoices();
      }
    };
    if (typeof synth.addEventListener === "function") {
      synth.addEventListener("voiceschanged", onVoicesChanged);
      return () => {
        synth.removeEventListener?.("voiceschanged", onVoicesChanged);
      };
    } else {
      const prevHandler = synth.onvoiceschanged;
      synth.onvoiceschanged = onVoicesChanged;
      return () => {
        if (synth && synth.onvoiceschanged === onVoicesChanged) {
          synth.onvoiceschanged = prevHandler;
        }
      };
    }
  }, []);

  return {
    playing,
    muted,
    hasReplay,
    jawEnergy,
    playingRef,
    visemeEvents,
    audioStartTimeRef,
    speech,
    isAudioBlocked,
    unlockAudio,
    play,
    speakBrowser,
    speakStreamChunk,
    replay,
    stop,
    toggleMute,
  };
}
