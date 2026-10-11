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
  /** True only when replay material exists AND the last utterance never
   *  produced sound (autoplay-blocked). A reply the user already heard must
   *  never qualify — otherwise every unlock re-speaks the previous message. */
  hasUnplayedReplay: () => boolean;
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
    onEnded?: () => void,
    onStarted?: () => void,
  ) => Promise<boolean>;
  beginSpeechStream: () => void;
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
  // Timestamp of the last speechSynthesis.cancel(). Chrome restarts a
  // just-cancelled utterance when the next speak() lands within a few hundred
  // milliseconds of cancel() — that replayed her previous reply over his new
  // message. Browser speech paths below let the engine settle first.
  const lastBrowserCancelAtRef = useRef(0);
  const frameRef = useRef<number | undefined>(undefined);
  const mutedRef = useRef(false);
  const playingRef = useRef(false);
  const browserSpeechActiveRef = useRef(false);
  const streamChunkQueueRef = useRef<SpeechSynthesisUtterance[]>([]);
  const streamActiveRef = useRef(false);
  const browserWatchdogRef = useRef<number | undefined>(undefined);
  const streamReplayRef = useRef<Array<{blob?: Blob; text: string; language?: string; companionId?: string; providerVisemes?: VisemeEvent[]}>>([]);
  const captureStreamReplayRef = useRef(false);
  const replayAbortRef = useRef<AbortController | null>(null);
  const beginSpeechStream = useCallback(() => {
    streamReplayRef.current = [];
    captureStreamReplayRef.current = true;
    lastStartedRef.current = false;
    // A new streamed turn supersedes the previous turn's single-shot replay
    // material — otherwise a blocked first chunk would replay the LAST turn.
    lastBrowserSpeechRef.current = null;
    lastBlobRef.current = null;
    setHasReplay(false);
  }, []);
  const lastBrowserSpeechRef = useRef<{ text: string; language: string; companionId?: string } | null>(null);
  const activeHtmlAudioRef = useRef<HTMLAudioElement | null>(null);
  // Did the most recent utterance actually reach the speakers? Stays false
  // when autoplay blocks playback before start — the only case where an
  // unlock may legitimately replay.
  const lastStartedRef = useRef(false);

  const ensureGraph = useCallback(() => {
    if (contextRef.current && contextRef.current.state !== "closed") return contextRef.current;
    let context: AudioContext;
    if (typeof window !== "undefined" && (window as any).__hinaaAudioCtx && (window as any).__hinaaAudioCtx.state !== "closed") {
      context = (window as any).__hinaaAudioCtx;
    } else {
      const AudioContextClass = typeof window !== "undefined" ? (window.AudioContext || (window as any).webkitAudioContext) : undefined;
      if (!AudioContextClass) {
        throw new Error("Audio output is unavailable on this device.");
      }
      context = new AudioContextClass({ latencyHint: "interactive" });
      if (typeof window !== "undefined") {
        (window as any).__hinaaAudioCtx = context;
      }
    }
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
    return context;
  }, []);

  const syncPlaying = useCallback(() => {
    const next = sourcesRef.current.size > 0 || browserSpeechActiveRef.current || Boolean(activeHtmlAudioRef.current && !activeHtmlAudioRef.current.paused);
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
    replayAbortRef.current?.abort();
    replayAbortRef.current = null;
    captureStreamReplayRef.current = false;
    // An interrupted reply must never come back: drop every piece of replay
    // material here. Without this, interrupting her mid-reply left the old
    // reply marked "unplayed" (the cancelled chunk had reset the heard
    // marker), so a later audio-unlock tap re-spoke the previous message
    // over his new one. The legitimate blocked-then-unblock flow never
    // passes through stop(), so genuine autoplay replays still work.
    streamReplayRef.current = [];
    lastBlobRef.current = null;
    lastBrowserSpeechRef.current = null;
    setHasReplay(false);
    sessionRef.current += 1;
    browserSpeechActiveRef.current = false;
    streamActiveRef.current = false;
    streamChunkQueueRef.current = [];
    if (activeHtmlAudioRef.current) {
      try {
        activeHtmlAudioRef.current.pause();
        activeHtmlAudioRef.current.currentTime = 0;
      } catch {}
      activeHtmlAudioRef.current = null;
    }
    if (browserWatchdogRef.current !== undefined) {
      window.clearTimeout(browserWatchdogRef.current);
      browserWatchdogRef.current = undefined;
    }
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      try {
        window.speechSynthesis.cancel();
        lastBrowserCancelAtRef.current = performance.now();
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
      lastStartedRef.current = false;
      const playHtml5AudioFallback = async (originalErr?: Error) => {
        if (typeof window === "undefined" || typeof Audio === "undefined") {
          onEnded?.();
          throw new Error("Audio is blocked. Tap the audio control to enable playback.");
        }
        let url = "";
        try {
          url = URL.createObjectURL(blob);
        } catch {
          onEnded?.();
          throw new Error("The voice audio could not be decoded. Please retry.");
        }
        const audio = new Audio(url);
        try {
          audio.playbackRate = 1.0;
          audio.volume = mutedRef.current ? 0 : 1;
        } catch {}
        activeHtmlAudioRef.current = audio;

        lastBlobRef.current = blob;
        lastTextRef.current = spokenText ?? "";
        lastProviderVisemesRef.current = providerVisemes;
        lastBrowserSpeechRef.current = null;
        setHasReplay(true);

        return new Promise<void>((resolve, reject) => {
          let endedDispatched = false;
          const finish = (err?: Error) => {
            if (endedDispatched) return;
            endedDispatched = true;
            try { URL.revokeObjectURL(url); } catch {}
            if (activeHtmlAudioRef.current === audio) {
              activeHtmlAudioRef.current = null;
            }
            syncPlaying();
            onEnded?.();
            if (err) {
              reject(err);
            } else {
              resolve();
            }
          };

          audio.onended = () => finish();
          audio.onerror = () => {
            finish(originalErr || new Error("Audio is blocked. Tap the audio control to enable playback."));
          };
          audio.onplay = () => {
            if (session !== sessionRef.current) return;
            lastStartedRef.current = true;
            onStarted?.();
            syncPlaying();
          };

          try {
            const playPromise = audio.play();
            if (playPromise !== undefined && typeof playPromise.then === "function") {
              playPromise
                .then(() => {
                  syncPlaying();
                })
                .catch((err) => {
                  console.warn("[HINAA] HTML5 Audio autoplay blocked:", err);
                  finish(originalErr || new Error("Audio is blocked. Tap the audio control to enable playback."));
                });
            } else {
              finish(originalErr || new Error("Audio is blocked. Tap the audio control to enable playback."));
            }
          } catch {
            finish(originalErr || new Error("Audio is blocked. Tap the audio control to enable playback."));
          }
        });
      };

      let context: AudioContext | null = null;
      try {
        context = ensureGraph();
      } catch (e) {
        console.warn("[HINAA] AudioContext creation failed:", e);
      }

      if (context && context.state !== "running") {
        try {
          await context.resume();
        } catch {
          // ignore resume error and fallback
        }
      }

      if (!context || context.state !== "running") {
        return await playHtml5AudioFallback();
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
        try {
          buffer = await context.decodeAudioData(bytes.slice(0));
        } catch (decodeErr) {
          // Only declared raw PCM can bypass the decoder; damaged MP3 is not PCM.
          if (["audio/pcm", "audio/raw"].includes(blob.type) && bytes.byteLength % 2 === 0) {
            const pcm16 = new Int16Array(bytes);
            if (pcm16.length === 0) throw decodeErr;
            const sampleRate = (blob as any).sampleRate || 24_000;
            buffer = context.createBuffer(1, pcm16.length, sampleRate);
            const channel = buffer.getChannelData(0);
            for (let i = 0; i < pcm16.length; i++) {
              channel[i] = pcm16[i] / 32768.0;
            }
          } else {
            throw decodeErr;
          }
        }
      } catch (e) {
        console.warn("[HINAA] Audio decode failed, falling back to HTML5 audio:", e);
        return await playHtml5AudioFallback(new Error("The voice audio could not be decoded. Please retry."));
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
      // Natural voice: 1.0x — the server-side pace calibration owns tempo.
      // BufferSource playbackRate resamples (no pitch preservation), so 1.08
      // was pitching her voice up ~8% and thinning it out.
      const playbackRate = 1.0;
      source.playbackRate.value = playbackRate;
      const effectiveDuration = buffer.duration / playbackRate;

      // Gapless, click-free seam: schedule exactly where the previous chunk
      // ends (no negative overlap — that double-plays 25ms at every chunk
      // seam). If the queue has drained, start promptly instead.
      const previousEndedAt = endedAtRef.current;
      const isContinuation = previousEndedAt > context.currentTime;
      const startAt = Math.max(context.currentTime + 0.02, previousEndedAt);
      endedAtRef.current = startAt + effectiveDuration;
      sourcesRef.current.add(source);
      syncPlaying();

      // Build viseme timeline from spoken text + audio duration.
      // For streamed chunks the queue is still hot (isContinuation), so this
      // chunk's syllables must APPEND to the existing timeline at the right
      // offset — replacing it would jerk the mouth back to the start of the
      // sentence on every packet.
      if ((spokenText || providerVisemes?.length) && effectiveDuration > 0) {
        const durationMs = effectiveDuration * 1000;
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
        ? Math.max(effectiveDuration, endedAtRef.current - audioStartTimeRef.current)
        : effectiveDuration;
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
        lastStartedRef.current = true;
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

      if (captureStreamReplayRef.current) streamReplayRef.current.push({ blob, text: spokenText ?? "", providerVisemes });
      else streamReplayRef.current = [];
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
      lastStartedRef.current = false;

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
          /microsoft jenny/i, /microsoft aria/i, /ayumi/i, /haruka/i, /sayaka/i,
          /huihui/i, /yaoyao/i, /catherine/i, /linda/i, /eva/i, /fiona/i, /moira/i,
          /veena/i, /priya/i, /ananya/i, /kalpana/i, /shruti/i, /sunita/i, /sangeeta/i
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
        // Priority 5: Any voice matching female patterns
        if (!selectedVoice) {
          selectedVoice = allVoices.find((v) => isFemaleVoice(v.name));
        }
        // If strictly only male voices exist on this OS, refuse male voice for Hina
        if (!selectedVoice && allVoices.length > 0) {
          console.warn("[HINAA] No female voice available in OS speech engine; refusing male voice for Hina");
          return false;
        }
        utterance.pitch = 1.08; // Gentle feminine lift — 1.18 read squeaky/thin
        utterance.rate = 0.98;
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
      streamReplayRef.current = [];
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
      // A reply that reached onend was heard, even when the engine skipped
      // onstart (Chrome often does). Otherwise it stays "unplayed" and a later
      // live toggle or unlock tap re-speaks it.
      utterance.onend = () => {
        if (session === sessionRef.current) lastStartedRef.current = true;
        finish();
      };
      utterance.onerror = finish;
      utterance.onstart = () => {
        if (session !== sessionRef.current || finished) return;
        startedAt = performance.now();
        lastStartedRef.current = true;
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
        // Settle after a fresh cancel(): a speak() that lands too soon makes
        // Chrome replay the interrupted utterance — her previous reply talking
        // over his new message.
        const sinceCancel = performance.now() - lastBrowserCancelAtRef.current;
        if (sinceCancel < 250) {
          await new Promise((resolve) => window.setTimeout(resolve, 250 - sinceCancel));
        }
        if (session !== sessionRef.current) return false; // interrupted while settling
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
      onEnded?: () => void,
      onStarted?: () => void,
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
        const capture = captureStreamReplayRef.current;
        stop();
        captureStreamReplayRef.current = capture;
        streamChunkQueueRef.current = [];
        streamActiveRef.current = true;
      } else if (!streamActiveRef.current) {
        streamActiveRef.current = true;
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
          /microsoft jenny/i, /microsoft aria/i, /ayumi/i, /haruka/i, /sayaka/i,
          /huihui/i, /yaoyao/i, /catherine/i, /linda/i, /eva/i, /fiona/i, /moira/i,
          /veena/i, /priya/i, /ananya/i, /kalpana/i, /shruti/i, /sunita/i, /sangeeta/i
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
        if (!selectedVoice) {
          selectedVoice = allVoices.find((v) => isFemaleVoice(v.name));
        }
        if (!selectedVoice && allVoices.length > 0) {
          console.warn("[HINAA] No female voice available in browser; refusing male voice for stream chunk");
          return false;
        }
        utterance.pitch = 1.08;
        // Natural conversational pace — 1.18 was racing and thinning her voice
        utterance.rate = 0.98;
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
      let startedAt: number | null = null;
      let finished = false;
      const browserTiming = new BrowserSpeechTimingSource({ durationMs: chunkDurationMs, visemes: chunkVisemes });

      const finish = () => {
        if (session !== sessionRef.current || finished) return;
        finished = true;
        if (browserWatchdogRef.current !== undefined) { window.clearTimeout(browserWatchdogRef.current); browserWatchdogRef.current = undefined; }
        browserTiming.onUtteranceEnd();
        onEnded?.();
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

      utterance.onboundary = (event) => {
        if (session !== sessionRef.current || startedAt === null || finished || event.charIndex < 0) return;
        const elapsed = performance.now() - startedAt;
        const remaining = clean.slice(event.charIndex);
        const duration = Math.max(300, remaining.trim().split(/\s+/).length * 270);
        visemeEvents.current = textToVisemeEvents(remaining, duration, elapsed);
        speech.current.events = visemeEvents.current;
        speech.current.timingSource = "browser-boundary";
        browserTiming.retarget({ startMs: elapsed, visemes: visemeEvents.current, durationMs: elapsed + duration });
      };
      utterance.onpause = () => { if (session !== sessionRef.current || finished) return; browserTiming.onUtterancePause(); speech.current.state = "paused"; jawEnergy.current = 0; };
      utterance.onresume = () => { if (session !== sessionRef.current || finished) return; browserTiming.onUtteranceResume(); speech.current.state = "playing"; };
      utterance.onend = () => {
        if (session === sessionRef.current) lastStartedRef.current = true;
        finish();
      };
      utterance.onerror = finish;
      utterance.onstart = () => {
        if (session !== sessionRef.current || finished) return;
        startedAt = performance.now();
        lastStartedRef.current = true;
        browserSpeechActiveRef.current = true;
        visemeEvents.current = chunkVisemes;
        browserTiming.onUtteranceStart();
        speech.current = { utteranceId: session, state: "playing", source: "browser", timingSource: "text", calibrationMs: 0, events: chunkVisemes, elapsedMs: () => performance.now() - (startedAt ?? performance.now()), timing: browserTiming };
        onStarted?.();
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
          const elapsedMs = browserTiming.getPlaybackTime();
          const currentViseme = browserTiming.isPlaying() ? browserTiming.getVisemeAt(elapsedMs) : null;
          const targetEnergy = currentViseme?.mouth !== "closed" ? currentViseme?.weight ?? 0 : 0;
          jawEnergy.current += (targetEnergy - jawEnergy.current) * (targetEnergy > jawEnergy.current ? 0.55 : 0.25);
          frameRef.current = window.requestAnimationFrame(tick);
        };
        frameRef.current = window.requestAnimationFrame(tick);
      };

      streamChunkQueueRef.current.push(utterance);
      // Only the first chunk of a new stream may reset the heard marker.
      // Resetting it for every queued chunk marked a half-heard, then
      // interrupted, reply as "unplayed" — the exact state that let a later
      // unlock re-speak an old message over his new one.
      if (isFirst) lastStartedRef.current = false;
      browserWatchdogRef.current = window.setTimeout(finish, Math.max(8_000, chunkDurationMs * 2 + 5_000));
      try {
        // Same cancel-then-speak race as speakBrowser: settle before speaking
        // or Chrome replays the interrupted utterance over his new message.
        const sinceCancel = performance.now() - lastBrowserCancelAtRef.current;
        if (sinceCancel < 250) {
          await new Promise((resolve) => window.setTimeout(resolve, 250 - sinceCancel));
        }
        if (session !== sessionRef.current) {
          // Interrupted while the engine settled: drop the chunk quietly.
          const staleIdx = streamChunkQueueRef.current.indexOf(utterance);
          if (staleIdx !== -1) streamChunkQueueRef.current.splice(staleIdx, 1);
          return false;
        }
        engine.speak(utterance);
        if (captureStreamReplayRef.current) streamReplayRef.current.push({ text: clean, language: normalizedLanguage, companionId });
        lastBrowserSpeechRef.current = { text: clean, language: normalizedLanguage, companionId };
        lastBlobRef.current = null;
        setHasReplay(true);
        return true;
      } catch {
        finish();
        return false;
      }
    },
    [stop, syncPlaying],
  );

  const replay = useCallback(async () => {
    const phrases = [...streamReplayRef.current];
    if (phrases.length) {
      stop();
      const abort = new AbortController();
      replayAbortRef.current = abort;
      for (const phrase of phrases) {
        if (abort.signal.aborted) return;
        await new Promise<void>((resolve, reject) => {
          const finish = () => { abort.signal.removeEventListener("abort", finish); resolve(); };
          abort.signal.addEventListener("abort", finish, { once: true });
          if (phrase.blob) void play(phrase.blob, phrase.text, undefined, finish, phrase.providerVisemes).catch(reject);
          else void speakStreamChunk(phrase.text, false, phrase.language, phrase.companionId, finish).then(ok => { if (!ok) finish(); }).catch(reject);
        });
      }
      if (!abort.signal.aborted) streamReplayRef.current = phrases;
      if (replayAbortRef.current === abort) replayAbortRef.current = null;
      return;
    }
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
  }, [play, speakBrowser, speakStreamChunk, stop]);

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

  const isAudioBlocked = useCallback(() => {
    return Boolean(contextRef.current && contextRef.current.state !== "running");
  }, []);

  const hasUnplayedReplay = useCallback(() => {
    if (lastStartedRef.current) return false;
    return Boolean(
      lastBlobRef.current ||
      lastBrowserSpeechRef.current ||
      streamReplayRef.current.length > 0,
    );
  }, []);

  const unlockAudio = useCallback(async () => {
    try {
      const ctx = ensureGraph();
      if (ctx.state === "suspended") {
        void ctx.resume();
      }
      // Prime audio context synchronously with a silent 1-sample buffer to satisfy autoplay policies
      const buffer = ctx.createBuffer(1, 1, 22050);
      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(ctx.destination);
      source.start(0);
    } catch (e) {
      console.warn("[HINAA] Audio unlock failed:", e);
    }
    // Also prime HTML5 Audio subsystem for Brave/Safari without interfering with active speech
    try {
      if (typeof window !== "undefined" && typeof Audio !== "undefined" && !(window as any).__hinaaHtmlPrimed) {
        (window as any).__hinaaHtmlPrimed = true;
        const primer = new Audio("data:audio/wav;base64,UklGRigAAABXQVZFRm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA");
        primer.volume = 0.01;
        const p = primer.play();
        if (p && typeof p.then === "function") {
          p.then(() => {
            try { primer.pause(); } catch {}
          }).catch(() => {});
        }
      }
    } catch {}
  }, [ensureGraph]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      (window as any).__hinaaUnlockAudio = unlockAudio;
    }
  }, [unlockAudio]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    let unlocked = false;
    const autoUnlock = () => {
      if (unlocked) return;
      unlocked = true;
      void unlockAudio();
      window.removeEventListener("pointerdown", autoUnlock);
      window.removeEventListener("click", autoUnlock);
      window.removeEventListener("touchstart", autoUnlock);
      window.removeEventListener("keydown", autoUnlock);
    };
    window.addEventListener("pointerdown", autoUnlock, { passive: true });
    window.addEventListener("click", autoUnlock, { passive: true });
    window.addEventListener("touchstart", autoUnlock, { passive: true });
    window.addEventListener("keydown", autoUnlock, { passive: true });
    return () => {
      window.removeEventListener("pointerdown", autoUnlock);
      window.removeEventListener("click", autoUnlock);
      window.removeEventListener("touchstart", autoUnlock);
      window.removeEventListener("keydown", autoUnlock);
    };
  }, [unlockAudio]);

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
      if (typeof window !== "undefined") {
        delete (window as any).__hinaaAudioCtx;
      }
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
    hasUnplayedReplay,
    unlockAudio,
    play,
    speakBrowser,
    speakStreamChunk,
    replay,
    beginSpeechStream,
    stop,
    toggleMute,
  };
}
