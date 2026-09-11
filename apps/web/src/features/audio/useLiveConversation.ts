import { useCallback, useEffect, useRef, useState } from "react";
import { parseAssistantTurnPlan } from "../../contracts/assistantTurnPlan";
import { getSafeAssistantStreamingText } from "../companion/assistantTurnCodec";
import type { CompanionController } from "../companion/useCompanionController";
import type { PlaybackController } from "./useAudioPlayback";
import { LatencyClock } from "./latencyClock";
import { PhraseDetector } from "./phraseDetector";
import { TurnTakingController } from "./turnTakingController";
import type { ActiveLanguagePolicy } from "../settings/types/settings";
import { recognitionLocale, browserSpeechLocale } from "./languagePolicy";

function parseTurnId(turnId: string): { turn: number; generation: number } {
  // Format: turn-{turnNumber}-{generation}
  const parts = turnId.split("-");
  if (parts.length >= 3) {
    const turn = parseInt(parts[1], 10);
    const gen = parseInt(parts[2], 10);
    return {
      turn: isNaN(turn) ? 0 : turn,
      generation: isNaN(gen) ? 0 : gen,
    };
  }
  return { turn: 0, generation: 0 };
}

type LiveStatus =
  "idle" | "connecting" | "listening" | "paused" | "reconnecting" | "error";

/**
 * Real-time pipeline diagnostics for the voice drawer.
 * Tracks every stage from microphone to playback.
 */
export interface VoicePipelineDiagnostics {
  micPermission: "unknown" | "granted" | "denied";
  trackState: "unknown" | "live" | "ended" | "muted";
  audioContextState: "unknown" | "running" | "suspended" | "closed" | "interrupted";
  inputSampleRate: number;
  rmsLevel: number;
  chunksSentPerSecond: number;
  sttSocketState: "unknown" | "connecting" | "open" | "closed";
  lastPartialTranscript: string;
  lastCommittedTranscript: string;
  sttLatencyMs: number;
  brainProvider: string;
  firstTokenReceived: boolean;
  brainLatencyMs: number;
  ttsProvider: string;
  ttsSocketState: "unknown" | "connecting" | "open" | "closed";
  audioChunksReceived: number;
  playbackState: "idle" | "playing" | "error";
  /** Playback queue diagnostics */
  queueEncodedChunks: number;
  queueDecoding: number;
  queueDecodedBuffers: number;
  queueScheduledSources: number;
  queueDrained: boolean;
  finalSequenceReceived: boolean;
  currentStage: string;
  lastError: string;
  turnCount: number;
  activeTurnId: string;
  /** Exact voice route — which providers are in use for STT/Brain/TTS */
  voiceRoute: {
    sttProvider: string;
    sttTransport: string;
    brainProvider: string;
    brainModel: string;
    ttsProvider: string;
    ttsTransport: string;
    ttsVoiceId: string;
    ttsFallbackReason?: string;
  };
}

export interface LiveMetrics {
  partialFromSpeechMs?: number;
  finalAfterSpeechMs?: number;
  firstTextAfterFinalMs?: number;
  firstAudibleAfterSpeechMs?: number;
  playbackCompleteAfterSpeechMs?: number;
  sttMs?: number;
  llmMs?: number;
  llmFirstDeltaMs?: number;
  ttsMs?: number;
  totalMs?: number;
  bargeInStopMs?: number;
  turnState?: string;
}

interface LiveEvent {
  type: string;
  generation?: number;
  turnId?: string;
  text?: string;
  delta?: string;
  plan?: unknown;
  audioBase64?: string;
  mediaType?: string;
  provider?: string;
  code?: string;
  message?: string;
  requestedVoice?: string;
  actualVoice?: string;
  calibration?: string;
  sttMs?: number;
  llmMs?: number;
  llmFirstDeltaMs?: number;
  ttsMs?: number;
  totalMs?: number;
  segment?: number;
  segments?: number;
  /** turn.complete metadata */
  outputMode?: "text" | "audio" | "text_and_audio";
  ttsRequested?: boolean;
  ttsStatus?: "not_requested" | "completed" | "partial" | "failed" | "streaming" | "cancelled";
  ttsChunksTotal?: number;
  ttsChunksSucceeded?: number;
}

interface LiveOptions {
  conversationId?: string;
  controller: CompanionController;
  playback: PlaybackController;
  calibration: "natural" | "soft" | "lively";
  outputMode: "headphones" | "speaker";
  activeLanguagePolicy: ActiveLanguagePolicy;
  /** Called when the pipeline is stuck in listening and needs recovery */
  onPipelineStuck?: (stage: string) => void;
}

function websocketUrl(): string {
  // Always connect same-origin through /api. In dev the Vite proxy forwards
  // the WebSocket upgrade to the backend (verified end-to-end). Connecting
  // directly to :8000 broke two real cases: phones on the LAN (uvicorn only
  // listens on 127.0.0.1) and HTTPS dev (wss:// to a plain-HTTP backend).
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/api/v1/realtime`;
}

const liveLocaleForPolicy = recognitionLocale;

function decodeAudio(value: string, mediaType = "audio/wav"): Blob {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1)
    bytes[index] = binary.charCodeAt(index);
  return new Blob([bytes], { type: mediaType });
}

/**
 * Opt-in voice pipeline trace. Set sessionStorage["hinaa-voice-trace"] = "1"
 * before starting a live session, then read DevTools console for
 * "[voice-trace]" entries covering every mic frame decision, turn boundary,
 * and server event — including events silently discarded by turn/generation
 * guards, which is how stuck-listening bugs hide.
 */
function voiceTraceEnabled(): boolean {
  try {
    return typeof sessionStorage !== "undefined" &&
      sessionStorage.getItem("hinaa-voice-trace") === "1";
  } catch {
    return false;
  }
}

function voiceTrace(...parts: unknown[]): void {
  if (voiceTraceEnabled()) console.debug("[voice-trace]", ...parts);
}

export function useLiveConversation({
  controller,
  playback,
  calibration,
  outputMode,
  activeLanguagePolicy,
  conversationId,
}: LiveOptions) {
  const localSessionId = useRef(globalThis.crypto.randomUUID());
  const languagePolicyRef = useRef(activeLanguagePolicy);
  languagePolicyRef.current = activeLanguagePolicy;
  const [status, setStatus] = useState<LiveStatus>("idle");
  const [microphoneLevel, setMicrophoneLevel] = useState(0);
  const [detail, setDetail] = useState("Live microphone is off");
  const [metrics, setMetrics] = useState<LiveMetrics>({});
  const [voiceMetadata, setVoiceMetadata] = useState("");
  const [paused, setPaused] = useState(false);
  /** True from the moment a turn is committed until the first sign of an
   *  assistant response. This is the ONLY reliable arming signal for the
   *  brain-timeout watchdog — entering "waiting_for_provider" never changes
   *  `status`, so an effect keyed on [status] would never re-run and the
   *  watchdog would never arm. */
  const [brainPending, setBrainPending] = useState(false);
  const [diagnostics, setDiagnostics] = useState<VoicePipelineDiagnostics>({
    micPermission: "unknown",
    trackState: "unknown",
    audioContextState: "unknown",
    inputSampleRate: 0,
    rmsLevel: 0,
    chunksSentPerSecond: 0,
    sttSocketState: "unknown",
    lastPartialTranscript: "",
    lastCommittedTranscript: "",
    sttLatencyMs: 0,
    brainProvider: "",
    firstTokenReceived: false,
    brainLatencyMs: 0,
    ttsProvider: "",
    ttsSocketState: "unknown",
    audioChunksReceived: 0,
    playbackState: "idle",
    currentStage: "idle",
    lastError: "",
    turnCount: 0,
    activeTurnId: "",
    queueEncodedChunks: 0,
    queueDecoding: 0,
    queueDecodedBuffers: 0,
    queueScheduledSources: 0,
    queueDrained: true,
    finalSequenceReceived: false,
    voiceRoute: {
      sttProvider: "—",
      sttTransport: "—",
      brainProvider: "—",
      brainModel: "—",
      ttsProvider: "—",
      ttsTransport: "—",
      ttsVoiceId: "—",
    },
  });
  const chunksSentRef = useRef(0);
  const chunksPerSecRef = useRef(0);
  const socket = useRef<WebSocket | undefined>(undefined);
  const stream = useRef<MediaStream | undefined>(undefined);
  const audioContext = useRef<AudioContext | undefined>(undefined);
  const source = useRef<MediaStreamAudioSourceNode | undefined>(undefined);
  const worklet = useRef<AudioWorkletNode | undefined>(undefined);
  const silentNode = useRef<GainNode | undefined>(undefined);
  const handleWorkletFrameRef = useRef<((frame: ArrayBuffer, level: number) => void) | undefined>(undefined);
  const active = useRef(false);
  const pausedRef = useRef(false);
  const manualStop = useRef(false);
  const ready = useRef(false);
  const generation = useRef(1);
  const sequence = useRef(0);
  const capturing = useRef(false);
  const pushToTalkHeld = useRef(false);
  const preRoll = useRef<ArrayBuffer[]>([]);
  const reconnectAttempt = useRef(0);
  const reconnectTimer = useRef<number | undefined>(undefined);
  const heartbeat = useRef<number | undefined>(undefined);
  const stuckTimerRef = useRef<number | undefined>(undefined);
  const brainTimerRef = useRef<number | undefined>(undefined);
  const drainTimerRef = useRef<number | undefined>(undefined);
  const playbackQueue = useRef(Promise.resolve());
  const playbackState = useRef(false);
  const wasPlayingRef = useRef(false);
  const manualAudioStop = useRef(false);
  const speechStartedAt = useRef<number | undefined>(undefined);
  const speechEndedAt = useRef<number | undefined>(undefined);
  const finalAt = useRef<number | undefined>(undefined);
  const partialGeneration = useRef<number | undefined>(undefined);
  const textGeneration = useRef<number | undefined>(undefined);
  const audibleGeneration = useRef<number | undefined>(undefined);
  const lastPartial = useRef("");
  const frameTraceCount = useRef(0);
  const startupCalibrationCount = useRef(0);
  const turnTaking = useRef(new TurnTakingController());
  const phraseDetector = useRef(new PhraseDetector());
  const latency = useRef(new LatencyClock());
  const rawAssistantTextRef = useRef("");
  const visibleAssistantTextRef = useRef("");
  const lastSpokenTextRef = useRef("");
  const diagnosticsRef = useRef({ audioChunksReceived: 0 });
  const activeTurnIdRef = useRef("");
  const turnCompleteReceivedRef = useRef(false);
  const playbackQueueRef = useRef({
    encodedChunks: 0,
    decoding: 0,
    decodedBuffers: 0,
    scheduledSources: 0,
    finalSequenceReceived: false,
  });
  const callbacks = useRef({ controller, playback });
  callbacks.current = { controller, playback };
  playbackState.current = playback.playing;
  // When the requested live brain is unconfigured, automatically retry the
  // session once with the mock brain so the user can keep testing voice
  // without an opaque "voice service is not configured" error.
  const forcedMockFallback = useRef(false);

  const updateQueueDiagnostics = useCallback(() => {
    const pq = playbackQueueRef.current;
    setDiagnostics((prev) => ({
      ...prev,
      queueEncodedChunks: pq.encodedChunks,
      queueDecoding: pq.decoding,
      queueDecodedBuffers: pq.decodedBuffers,
      queueScheduledSources: pq.scheduledSources,
      queueDrained: pq.encodedChunks === 0 && pq.decoding === 0 && pq.decodedBuffers === 0 && pq.scheduledSources === 0,
      finalSequenceReceived: pq.finalSequenceReceived,
    }));
  }, []);

  // Track playback state in diagnostics
  useEffect(() => {
    setDiagnostics((prev) => ({
      ...prev,
      playbackState: playback.playing ? "playing" : "idle",
    }));
  }, [playback.playing]);

  // Gapless playback resolves play() at schedule time, so end-of-speech
  // When playback transitions from playing -> not playing, this is the
  // authoritative signal that HINAA has finished speaking.
  // Only then do we transition Speaking -> Listening.
  useEffect(() => {
    const was = wasPlayingRef.current;
    wasPlayingRef.current = playback.playing;
    if (was && !playback.playing) {
      if (manualAudioStop.current) {
        manualAudioStop.current = false;
        return;
      }
      if (speechEndedAt.current !== undefined) {
        latency.current.mark("final_audio");
        setMetrics((value) => ({
          ...value,
          playbackCompleteAfterSpeechMs: Math.round(
            performance.now() - speechEndedAt.current!,
          ),
        }));
      }
      // If turn.complete was already received and we're in Speaking state,
      // now is the time to transition to Listening.
      if (
        turnCompleteReceivedRef.current &&
        (turnTaking.current?.currentState === "speaking" ||
         turnTaking.current?.currentState === "interrupted") &&
        active.current &&
        !pausedRef.current
      ) {
        turnTaking.current.setSessionState("listening");
        callbacks.current.controller.setLiveState("listening");
        setDetail("Turn complete · automatically listening again");
        setDiagnostics((prev) => ({ ...prev, currentStage: "playback-drained" }));
        window.clearTimeout(drainTimerRef.current);
      } else if (
        turnCompleteReceivedRef.current &&
        turnTaking.current?.currentState === "speaking" &&
        pausedRef.current
      ) {
        turnTaking.current.setSessionState("listening");
        callbacks.current.controller.setLiveState("listening");
        setDetail("Turn complete · listening paused");
        window.clearTimeout(drainTimerRef.current);
      }
    }
  }, [playback.playing]);

  const sendJson = useCallback((value: object) => {
    if (socket.current?.readyState === WebSocket.OPEN)
      socket.current.send(JSON.stringify(value));
  }, []);

  // Release all microphone/websocket resources without changing UI state.
  // Declared before event/connect callbacks so their cleanup dependency is
  // explicit and cannot capture a stale render.
  const teardownSession = useCallback(() => {
    active.current = false;
    ready.current = false;
    capturing.current = false;
    sendJson({ type: "session.close" });
    socket.current?.close();
    socket.current = undefined;
    if (heartbeat.current) window.clearInterval(heartbeat.current);
    if (reconnectTimer.current) window.clearTimeout(reconnectTimer.current);
    worklet.current?.disconnect();
    source.current?.disconnect();
    silentNode.current?.disconnect();
    for (const track of stream.current?.getTracks() ?? []) track.stop();
    if (audioContext.current?.state !== "closed") void audioContext.current?.close();
    stream.current = undefined;
    worklet.current = undefined;
    source.current = undefined;
    silentNode.current = undefined;
    audioContext.current = undefined;
    preRoll.current = [];
    turnTaking.current.resetSpeech();
    turnTaking.current.setSessionState("inactive");
    phraseDetector.current.reset();
    setMicrophoneLevel(0);
    playbackQueueRef.current = { encodedChunks: 0, decoding: 0, decodedBuffers: 0, scheduledSources: 0, finalSequenceReceived: false };
    turnCompleteReceivedRef.current = false;
    if (playbackState.current) manualAudioStop.current = true;
    callbacks.current.playback.stop();
    window.clearTimeout(drainTimerRef.current);
    window.clearTimeout(stuckTimerRef.current);
    window.clearTimeout(brainTimerRef.current);
    setBrainPending(false);
  }, [sendJson]);

  const sendFrame = useCallback(
    (frame: ArrayBuffer) => {
      if (!ready.current || !capturing.current || pausedRef.current) return;
      sendJson({
        type: "audio.frame",
        sequence: sequence.current,
        generation: generation.current,
        capturedAtMs: performance.now(),
        byteLength: frame.byteLength,
      });
      socket.current?.send(frame);
      sequence.current += 1;
    },
    [sendJson],
  );

  const beginSpeech = useCallback(() => {
    if (playbackState.current) {
      manualAudioStop.current = true;
      callbacks.current.playback.stop();
      playbackState.current = false;
      generation.current += 1;
      latency.current.mark("interruption_detected");
      latency.current.mark("playback_stopped");
      sendJson({ type: "interrupt", generation: generation.current });
    }
    // A new user turn is starting: clear the previous turn's correlation ID so
    // the server's NEW turnId (turn-{n}-{gen} increments per turn) is adopted
    // instead of discarded as a "late event from a previous turn". Without
    // this reset every turn after the first was silently dropped.
    activeTurnIdRef.current = "";
    sequence.current = 0;
    capturing.current = true;
    speechStartedAt.current = performance.now();
    speechEndedAt.current = undefined;
    finalAt.current = undefined;
    rawAssistantTextRef.current = "";
    visibleAssistantTextRef.current = "";
    lastSpokenTextRef.current = "";
    partialGeneration.current = undefined;
    textGeneration.current = undefined;
    audibleGeneration.current = undefined;
    lastPartial.current = "";
    setBrainPending(false);
    phraseDetector.current.reset();
    diagnosticsRef.current.audioChunksReceived = 0;
    latency.current.mark("speech_started");
    sendJson({ type: "audio.start", generation: generation.current });
    for (const frame of preRoll.current) sendFrame(frame);
    preRoll.current = [];
    callbacks.current.controller.setLiveState("listening");
    setDetail("Listening · hands-free · speak naturally");
  }, [sendFrame, sendJson]);

  const handleWorkletFrame = useCallback(
    (frame: ArrayBuffer, level: number) => {
      setMicrophoneLevel((current) => current * 0.7 + level * 0.3);
      chunksSentRef.current += 1;
      // Update RMS in diagnostics (throttled to avoid excessive re-renders)
      setDiagnostics((prev) => ({
        ...prev,
        rmsLevel: level,
        noiseFloor: turnTaking.current.currentNoiseFloor,
        vadThreshold: turnTaking.current.currentThreshold,
      }));
      if (pushToTalkHeld.current && capturing.current && active.current && ready.current && !pausedRef.current) {
        sendFrame(frame);
        return;
      }
      // On the first 8 frames when mic starts up (once per session), calibrate ambient noise floor.
      // Ignore levels >= 0.025 so user speech is never mistaken for background noise.
      if (startupCalibrationCount.current < 8 && !pushToTalkHeld.current && !capturing.current) {
        startupCalibrationCount.current += 1;
        if (level < 0.025) {
          turnTaking.current.calibrateFloor(level);
        }
      }
      const isWaiting =
        brainPending ||
        turnTaking.current.currentState === "waiting_for_provider";
      const decision = turnTaking.current.process({
        level,
        assistantPlaying: playbackState.current,
        partialText: lastPartial.current,
        sessionActive: active.current && ready.current,
        paused: pausedRef.current,
        waitingForProvider: isWaiting,
      });
      setMetrics((current) => ({ ...current, turnState: decision.state }));

      // Periodic frame-level trace so quiet-mic / threshold issues are visible
      frameTraceCount.current = (frameTraceCount.current + 1) % 25;
      if (frameTraceCount.current === 0)
        voiceTrace(
          "mic-frame",
          "rms:", level.toFixed(4),
          "state:", decision.state,
          "capturing:", capturing.current,
          "assistantPlaying:", playbackState.current,
        );

      // Trust the controller's barge-in decision: it already enforces the
      // sustained-intent threshold (0.22 floor + bargeInFrames). The old extra
      // `level >= 0.22` check only ran on the single frame where hotFrames
      // equaled bargeInFrames — if that one frame was slightly under 0.22 the
      // barge-in was rejected and could never re-fire, creating a dead zone
      // where the user shouted but HINAA never stopped.
      if (decision.bargeIn) {
        const started = performance.now();
        manualAudioStop.current = true;
        setBrainPending(false);
        callbacks.current.playback.stop();
        playbackState.current = false;
        generation.current += 1;
        // Clear ALL old-turn state
        playbackQueueRef.current = { encodedChunks: 0, decoding: 0, decodedBuffers: 0, scheduledSources: 0, finalSequenceReceived: false };
        turnCompleteReceivedRef.current = false;
        rawAssistantTextRef.current = "";
        visibleAssistantTextRef.current = "";
        lastSpokenTextRef.current = "";
        phraseDetector.current.reset();
        latency.current.mark("interruption_detected");
        latency.current.mark("playback_stopped");
        sendJson({ type: "interrupt", generation: generation.current });
        turnTaking.current.setSessionState("interrupted");
        window.clearTimeout(drainTimerRef.current);
        setMetrics((current) => ({
          ...current,
          bargeInStopMs: Math.round(performance.now() - started),
        }));
        setDiagnostics((prev) => ({ ...prev, currentStage: "interrupted", audioChunksReceived: 0 }));
        setDetail("Interrupted · listening again");
      }

      if (!capturing.current) {
        preRoll.current.push(frame);
        if (preRoll.current.length > 10) preRoll.current.shift();
      }
      if (decision.speechStart) {
        voiceTrace("speech-start", "rms:", level.toFixed(4), "state:", decision.state);
        beginSpeech();
        sendFrame(frame);
      } else if (capturing.current) sendFrame(frame);
      if (decision.speechCommit && capturing.current) {
        voiceTrace("speech-commit", "frames-captured:", sequence.current);
        speechEndedAt.current = performance.now();
        latency.current.mark("speech_ended");
        latency.current.mark("turn_committed");
        sendJson({
          type: "audio.commit",
          generation: generation.current,
          endedAtMs: performance.now(),
        });
        capturing.current = false;
        turnTaking.current.setSessionState("waiting_for_provider");
        setBrainPending(true);
        setDetail("Turn committed · waiting for HINAA…");
      }
    },
    [beginSpeech, sendFrame, sendJson],
  );
  handleWorkletFrameRef.current = handleWorkletFrame;

  const handleServerEvent = useCallback((event: LiveEvent) => {
    voiceTrace(
      "server-event",
      event.type,
      "turnId:", event.turnId ?? "—",
      "active:", activeTurnIdRef.current || "—",
      "gen:", event.generation ?? "—",
    );
    // Reject events from a stale generation
    if (
      typeof event.generation === "number" &&
      event.generation < generation.current
    ) {
      voiceTrace("discard:stale-generation", event.type, event.generation, "current:", generation.current);
      return;
    }
    // Session-level events bypass turn correlation
    if (event.type === "session.ready" || event.type === "pong" || event.type === "error") {
      // fall through to handler below
    } else if (event.turnId) {
      if (!activeTurnIdRef.current) {
        // Adopt initial turn ID
        activeTurnIdRef.current = event.turnId;
        turnCompleteReceivedRef.current = false;
        diagnosticsRef.current.audioChunksReceived = 0;
        playbackQueueRef.current = { encodedChunks: 0, decoding: 0, decodedBuffers: 0, scheduledSources: 0, finalSequenceReceived: false };
      } else if (event.turnId !== activeTurnIdRef.current) {
        const incoming = parseTurnId(event.turnId);
        const active = parseTurnId(activeTurnIdRef.current);

        // If the incoming event is from a newer turn or generation, advance to it!
        if (incoming.turn > active.turn || (incoming.turn === active.turn && incoming.generation > active.generation)) {
          voiceTrace("turn-advance", "from:", activeTurnIdRef.current, "to:", event.turnId, "event:", event.type);
          activeTurnIdRef.current = event.turnId;
          turnCompleteReceivedRef.current = false;
          diagnosticsRef.current.audioChunksReceived = 0;
          playbackQueueRef.current = { encodedChunks: 0, decoding: 0, decodedBuffers: 0, scheduledSources: 0, finalSequenceReceived: false };
        } else {
          // Genuinely stale event from an older turn that was already completed or superseded
          voiceTrace(
            "discard:stale-turn",
            event.type,
            "event turnId:", event.turnId,
            "active turnId:", activeTurnIdRef.current,
          );
          return;
        }
      }
    }
    const current = callbacks.current;
    if (event.type === "session.ready") {
      ready.current = true;
      reconnectAttempt.current = 0;
      setStatus(pausedRef.current ? "paused" : "listening");
      setDiagnostics((prev) => ({ ...prev, sttSocketState: "open", currentStage: "listening" }));
      setDetail(
        pausedRef.current
          ? "Listening paused · tap Resume to continue hands-free"
          : "Microphone active · hands-free listening",
      );
      current.controller.setLiveState("listening");
      latency.current.mark("microphone_ready");
    } else if (event.type === "stt.partial" && event.text) {
      lastPartial.current = event.text;
      turnTaking.current.notePartial(event.text);
      setDiagnostics((prev) => ({ ...prev, lastPartialTranscript: event.text || "", currentStage: "stt-partial" }));
      if (
        partialGeneration.current !== generation.current &&
        speechStartedAt.current !== undefined
      ) {
        partialGeneration.current = generation.current;
        latency.current.mark("first_stt_partial");
        setMetrics((value) => ({
          ...value,
          partialFromSpeechMs: Math.round(
            performance.now() - speechStartedAt.current!,
          ),
        }));
      }
      current.controller.applyLivePartial(event.text);
    } else if (event.type === "stt.final" && event.text) {
      finalAt.current = performance.now();
      latency.current.mark("stt_final");
      latency.current.mark("llm_request_started");
      setDiagnostics((prev) => ({
        ...prev,
        lastCommittedTranscript: event.text || "",
        sttLatencyMs: event.sttMs ?? 0,
        brainProvider: prev.voiceRoute.brainProvider || "claude",
        currentStage: "stt-final",
        turnCount: prev.turnCount + 1,
        activeTurnId: `turn-${Date.now()}`,
      }));
      if (speechEndedAt.current !== undefined)
        setMetrics((value) => ({
          ...value,
          finalAfterSpeechMs: Math.round(
            finalAt.current! - speechEndedAt.current!,
          ),
        }));
      current.controller.applyLiveFinal(event.text);
    } else if (event.type === "voice.pipeline") {
      const stage = (event as any).stage || "unknown";
      const detail = (event as any).detail || "";
      setDiagnostics((prev) => ({ ...prev, currentStage: `pipeline-${stage}`, lastError: "" }));
      if (stage === "transcribing") {
        current.controller.setLiveState("thinking");
        setDetail("Transcribing your speech…");
      } else if (stage === "brain") {
        current.controller.setLiveState("thinking");
        setDetail("HINAA is thinking…");
      } else if (stage === "tts") {
        setDetail("Generating speech…");
      } else if (detail) {
        setDetail(detail);
      }
    } else if (event.type === "assistant.thinking") {
      current.controller.setLiveState("thinking");
    } else if (event.type === "assistant.text.delta" && event.delta) {
      setBrainPending(false);
      setDiagnostics((prev) => ({ ...prev, currentStage: "brain-streaming" }));
      if (
        textGeneration.current !== generation.current &&
        finalAt.current !== undefined
      ) {
        textGeneration.current = generation.current;
        latency.current.mark("first_text_delta");
        setMetrics((value) => ({
          ...value,
          firstTextAfterFinalMs: Math.round(
            performance.now() - finalAt.current!,
          ),
        }));
      }
      rawAssistantTextRef.current += event.delta;
      const safeText = getSafeAssistantStreamingText(rawAssistantTextRef.current);
      const previousVisible = visibleAssistantTextRef.current;
      const visibleDelta = safeText.startsWith(previousVisible)
        ? safeText.slice(previousVisible.length)
        : safeText;
      visibleAssistantTextRef.current = safeText;
      if (visibleDelta) {
        const phrases = phraseDetector.current.push(visibleDelta);
        if (phrases.length) latency.current.mark("first_stable_phrase");
        current.controller.applyLiveDelta(visibleDelta);
        lastSpokenTextRef.current = safeText;
      }
    } else if (event.type === "assistant.plan") {
      setBrainPending(false);
      phraseDetector.current.flush();
      latency.current.mark("final_text");
      setDiagnostics((prev) => ({
        ...prev,
        currentStage: "brain-complete",
        firstTokenReceived: true,
        brainProvider: prev.voiceRoute.brainProvider || "claude",
      }));
      try {
        const plan = parseAssistantTurnPlan(event.plan);
        lastSpokenTextRef.current = plan.spokenText;
        current.controller.applyLivePlan(plan);
      } catch {
        current.controller.applyLiveError(
          "The live response plan was invalid and was not animated.",
        );
      }
    } else if (event.type === "tts.audio" && event.audioBase64) {
      const encodedAudio = event.audioBase64;
      const eventGeneration = event.generation;
      latency.current.mark("tts_request_started");
      latency.current.mark("first_audio_chunk");
      diagnosticsRef.current.audioChunksReceived += 1;
      // Track playback queue state
      const pq = playbackQueueRef.current;
      pq.encodedChunks += 1;
      if (event.segment !== undefined && event.segments !== undefined && event.segment >= event.segments - 1) {
        pq.finalSequenceReceived = true;
      }
      setDiagnostics((prev) => ({
        ...prev,
        ttsProvider: event.provider ?? "",
        audioChunksReceived: prev.audioChunksReceived + 1,
        currentStage: "tts-audio",
        queueEncodedChunks: pq.encodedChunks,
        finalSequenceReceived: pq.finalSequenceReceived,
      }));
      const isPlaceholder = /(?:placeholder|mock)/i.test(
        `${event.provider ?? ""} ${event.actualVoice ?? ""}`,
      );
      const isLastPlaceholderSegment =
        !isPlaceholder || (event.segment ?? 0) === Math.max(0, (event.segments ?? 1) - 1);
      if (isPlaceholder && !isLastPlaceholderSegment) return;

      playbackQueue.current = playbackQueue.current.then(async () => {
        if (eventGeneration !== generation.current) return;
        current.controller.setLiveState("speaking");
        turnTaking.current.setSessionState("speaking");
        // Track queue state: decoding
        playbackQueueRef.current.encodedChunks -= 1;
        playbackQueueRef.current.decoding += 1;
        updateQueueDiagnostics();

        let decodingDrained = false;
        const ensureDecodingDrained = () => {
          if (!decodingDrained) {
            decodingDrained = true;
            playbackQueueRef.current.decoding -= 1;
            updateQueueDiagnostics();
          }
        };

        try {
        const spokenText = isPlaceholder
          ? lastSpokenTextRef.current.trim()
          : typeof event.text === "string" && event.text.trim()
            ? event.text.trim()
            : lastSpokenTextRef.current.trim();

        if (isPlaceholder && spokenText) {
          setVoiceMetadata("Device browser voice fallback · local speech output");
          const started = await current.playback.speakBrowser(
            spokenText,
            browserSpeechLocale(spokenText, languagePolicyRef.current),
          );
          if (started) {
            latency.current.mark("playback_started");
            if (
              audibleGeneration.current !== generation.current &&
              speechEndedAt.current !== undefined
            ) {
              audibleGeneration.current = generation.current;
              setMetrics((value) => ({
                ...value,
                firstAudibleAfterSpeechMs: Math.round(
                  performance.now() - speechEndedAt.current!,
                ),
              }));
            }
          }
          return;
        }

        setVoiceMetadata(
          `${event.requestedVoice ?? "voice unknown"} → ${event.actualVoice ?? "not confirmed"} · ${event.calibration ?? "natural"}`,
        );
        let blob: Blob;
        try {
          blob = decodeAudio(encodedAudio, event.mediaType);
        } catch (decodeErr) {
          console.error("[HINAA] TTS audio decode failed:", decodeErr);
          playbackQueueRef.current.decoding -= 1;
          updateQueueDiagnostics();
          setDiagnostics((prev) => ({ ...prev, lastError: "AUDIO_DECODE_FAILED", currentStage: "audio-decode-error" }));
          return;
        }
        playbackQueueRef.current.decoding -= 1;
        playbackQueueRef.current.decodedBuffers += 1;
        updateQueueDiagnostics();
        try {
          await current.playback.play(
            blob,
            spokenText || undefined,
            () => {
              latency.current.mark("playback_started");
              playbackQueueRef.current.decodedBuffers -= 1;
              playbackQueueRef.current.scheduledSources += 1;
              updateQueueDiagnostics();
              if (
                audibleGeneration.current !== generation.current &&
                speechEndedAt.current !== undefined
              ) {
                audibleGeneration.current = generation.current;
                setMetrics((value) => ({
                  ...value,
                  firstAudibleAfterSpeechMs: Math.round(
                    performance.now() - speechEndedAt.current!,
                  ),
                }));
              }
            },
            () => {
              playbackQueueRef.current.scheduledSources = Math.max(0, playbackQueueRef.current.scheduledSources - 1);
              updateQueueDiagnostics();
              const pq = playbackQueueRef.current;
              if (pq.encodedChunks === 0 && pq.decoding === 0 && pq.decodedBuffers === 0 && pq.scheduledSources === 0) {
                if (turnCompleteReceivedRef.current && !pausedRef.current) {
                  window.clearTimeout(drainTimerRef.current);
                  turnTaking.current.setSessionState("listening");
                  setStatus("listening");
                  setDetail("Microphone active · hands-free listening");
                  current.controller.setLiveState("listening");
                }
              }
            },
          );
        } catch (playErr) {
          console.error("[HINAA] TTS playback failed:", playErr);
          playbackQueueRef.current.decodedBuffers -= 1;
          ensureDecodingDrained();
          updateQueueDiagnostics();
          setDiagnostics((prev) => ({ ...prev, lastError: "PLAYBACK_FAILED", currentStage: "playback-error" }));
        }
        } finally {
          ensureDecodingDrained();
        }
      });
    } else if (event.type === "turn.complete") {
      setBrainPending(false);
      turnCompleteReceivedRef.current = true;
      latency.current.mark("turn_completed");
      setDiagnostics((prev) => ({ ...prev, currentStage: "turn-complete" }));
      setMetrics((value) => ({
        ...value,
        sttMs: event.sttMs,
        llmMs: event.llmMs,
        llmFirstDeltaMs: event.llmFirstDeltaMs,
        ttsMs: event.ttsMs,
        totalMs: event.totalMs,
      }));
      if (current.controller.routing.activeMode === "mock") {
        pausedRef.current = true;
        setPaused(true);
        capturing.current = false;
        preRoll.current = [];
        turnTaking.current.resetSpeech();
        turnTaking.current.setSessionState("listening");
        setStatus("paused");
        setDetail(
          "Mock diagnostic turn complete · paused so the fixed demo transcript will not repeat",
        );
        current.controller.setLiveState("idle");
        return;
      }
      // Use turn.complete metadata to determine if audio was expected
      const ttsRequested = event.ttsRequested ?? (diagnosticsRef.current.audioChunksReceived > 0);
      const ttsStatus = event.ttsStatus ?? "unknown";
      const pq = playbackQueueRef.current;
      const audioStillPending = pq.encodedChunks > 0 || pq.decoding > 0 || pq.decodedBuffers > 0 || pq.scheduledSources > 0;
      // Determine if playback is truly done
      const playbackDone = !current.playback.playing && !audioStillPending;
      if (playbackDone && !ttsRequested) {
        // Intentional text-only response — this is normal, not an error
        turnTaking.current.setSessionState(
          pausedRef.current ? "listening" : "listening",
        );
        setDetail(
          pausedRef.current
            ? "Response complete · you can read my reply below"
            : "Response complete · listening again",
        );
        current.controller.setLiveState(pausedRef.current ? "listening" : "listening");
      } else if (playbackDone && ttsStatus === "failed") {
        // TTS failed but text is available
        turnTaking.current.setSessionState(pausedRef.current ? "listening" : "listening");
        setStatus("listening");
        setDetail("I completed the reply, but voice playback wasn't available. You can read my reply below.");
        setDiagnostics((prev) => ({ ...prev, lastError: "TTS_FAILED" }));
        current.controller.setLiveState("listening");
      } else if (!playbackDone) {
        // Audio is still pending — do NOT transition to Listening
        turnTaking.current.setSessionState("speaking");
        setDetail("HINAA is speaking · waiting for playback to finish");
        setDiagnostics((prev) => ({ ...prev, currentStage: "playback-draining" }));
        // The playback.playing effect drives the final transition
      } else if (pausedRef.current) {
        turnTaking.current.setSessionState("listening");
        setDetail("Turn complete · listening paused");
        current.controller.setLiveState("listening");
      } else {
        turnTaking.current.setSessionState("listening");
        setDetail("Turn complete · automatically listening again");
        current.controller.setLiveState("listening");
      }
    } else if (event.type === "voice.error") {
      // Informational — backend reports a voice-pipeline issue.
      // The turn.cancelled event handles flow control; this captures
      // the diagnostic detail without tearing down the live session.
      const code = (event as any).code ?? "voice_error";
      const reason = (event as any).reason ?? "";
      setBrainPending(false);
      setDiagnostics((prev) => ({
        ...prev,
        lastError: `voice_error:${code}`,
        currentStage: `voice-error-${code}`,
      }));
      if (reason) {
        setDetail(reason);
      }
            } else if (event.type === "turn.cancelled") {
      setBrainPending(false);
      latency.current.mark("server_cancel_acknowledged");
      const reason = (event as any).reason || "unknown";
      current.controller.setLiveState("idle");
      turnTaking.current.resetSpeech();
      turnTaking.current.setSessionState("listening");
      if (reason === "no_speech_detected" || reason === "STT_EMPTY_TRANSCRIPT") {
        setDetail("Listening · hands-free · speak naturally");
        setDiagnostics((prev) => ({ ...prev, currentStage: "listening", lastError: "" }));
      } else {
        setDetail("Previous response interrupted · listening");
      }
    } else if (event.type === "error") {
      capturing.current = false;
      setBrainPending(false);
      const code = event.code ?? "error";
      setDiagnostics((prev) => ({ ...prev, lastError: code, currentStage: `error-${code}` }));
      // Clear playback queue on error
      playbackQueueRef.current = { encodedChunks: 0, decoding: 0, decodedBuffers: 0, scheduledSources: 0, finalSequenceReceived: false };
      window.clearTimeout(drainTimerRef.current);
      const liveProviderUnavailable =
        code.includes("PROVIDER") || code.includes("CONFIGURATION");
      // Auto-recover from a brain that is not configured locally: keep the mic
      // and websocket alive, retry once with the local mock brain so the user
      // can continue testing voice instead of seeing a hard error.
      if (
        code === "PROVIDER_CONFIGURATION_MISSING" &&
        !forcedMockFallback.current
      ) {
        forcedMockFallback.current = true;
        setDiagnostics((prev) => ({
          ...prev,
          currentStage: "mock-fallback",
          voiceRoute: {
            ...(prev.voiceRoute ?? {
              sttProvider: "elevenlabs",
              sttTransport: "websocket",
              brainProvider: "mock",
              brainModel: "default",
              ttsProvider: "elevenlabs",
              ttsTransport: "http",
              ttsVoiceId: "configured",
            }),
            brainProvider: "mock",
            ttsFallbackReason: "Selected brain is not configured locally — using local mock for this session.",
          },
        }));
        setDetail(
          "Selected brain is not configured in this backend — continuing with the local mock voice so you can keep testing.",
        );
        setStatus("reconnecting");
        turnTaking.current.setSessionState("reconnecting");
        reconnectAttempt.current = 0;
        try { socket.current?.close(); } catch { /* already closing */ }
        return;
      }
      turnTaking.current.setSessionState(
        liveProviderUnavailable ? "provider_unavailable" : "error",
      );
      setStatus("error");
      // User-friendly error messages (technical codes go to diagnostics only)
      const userMessages: Record<string, string> = {
        PROVIDER_KEY_INVALID: "The voice service needs to be configured. You can still type to me.",
        PROVIDER_TIMEOUT: "The response took too long. Your transcript is still available.",
        PROVIDER_CONFIGURATION_MISSING: "The voice service is not configured yet. You can still type to me.",
        AUDIO_NO_SIGNAL: "I didn't hear anything. Try speaking again or use text.",
        STT_COMMIT_TIMEOUT: "I didn't receive a clear transcript. Please try speaking again.",
        TTS_ZERO_AUDIO: "I completed the reply, but voice playback wasn't available. You can read my reply below.",
        AUDIO_DECODE_FAILED: "I received the voice response, but this browser couldn't decode it.",
        PLAYBACK_BLOCKED: "I couldn't play the voice response. Tap to retry audio.",
        REALTIME_TURN_FAILED: "Something went wrong. Let's try again.",
      };
      setDetail(
        userMessages[code] || event.message?.trim() ||
        (liveProviderUnavailable
          ? "The voice service is temporarily unavailable. You can still type to me."
          : "Something went wrong with the voice session. Let's try again."),
      );
      // Release mic/websocket so Start button works for retry.
      teardownSession();
    }
  }, [teardownSession, updateQueueDiagnostics]);

  const connect = useCallback(() => {
    const next = new WebSocket(websocketUrl());
    socket.current = next;
    next.binaryType = "arraybuffer";
    setDiagnostics((prev) => ({ ...prev, sttSocketState: "connecting", currentStage: "stt-connecting" }));
    next.onopen = () => {
      reconnectAttempt.current = 0;
      const requestedMode = callbacks.current.controller.routing.activeMode ?? "mock";
      const effectiveMode = forcedMockFallback.current ? "mock" : requestedMode;
      sendJson({
        type: "session.hello",
        protocolVersion: "1.0",
        sessionId: conversationId ?? localSessionId.current,
        companionId: callbacks.current.controller.companionId,
        providerMode: effectiveMode,
        brainModel:
          effectiveMode === "custom" ||
          effectiveMode === "openai" ||
          effectiveMode === "real" ||
          effectiveMode === "agent-router" ||
          effectiveMode === "claude" ||
          effectiveMode === "cx-gateway" ||
          effectiveMode === "qwen"
            ? callbacks.current.controller.routing.activeModel ?? undefined
            : undefined,
        generation: generation.current,
        language: liveLocaleForPolicy(activeLanguagePolicy),
        languageMode: recognitionLocale(activeLanguagePolicy) === "mixed" ? "auto" : "fixed",
        calibration,
      });
      // Populate the voice route diagnostics with the actual providers in use
      setDiagnostics((prev) => ({
        ...prev,
        sttSocketState: "open",
        currentStage: "session-ready",
        voiceRoute: {
          ...prev.voiceRoute,
          brainProvider: effectiveMode === "mock" ? "mock" : "claude",
          ttsProvider: effectiveMode === "mock" ? "mock" : "elevenlabs",
        },
      }));
      turnTaking.current.setSessionState("listening");
      setStatus("listening");
      setDetail("Microphone active · hands-free listening");
      callbacks.current.controller.setLiveState("idle");
      if (heartbeat.current) window.clearInterval(heartbeat.current);
      heartbeat.current = window.setInterval(() => {
        sendJson({ type: "ping", sentAtMs: performance.now() });
      }, 5000);
    };
    next.onmessage = (message: MessageEvent<string>) => {
      try {
        handleServerEvent(JSON.parse(message.data) as LiveEvent);
      } catch {
        setDetail("An invalid server event was ignored safely");
      }
    };
    next.onerror = () => setDetail("Realtime connection error");
    next.onclose = () => {
      ready.current = false;
      if (heartbeat.current) window.clearInterval(heartbeat.current);
      if (!active.current || manualStop.current) return;
      if (reconnectAttempt.current >= 10) {
        callbacks.current.controller.applyLiveError(
          "Realtime reconnection stopped after multiple bounded attempts.",
        );
        teardownSession();
        setStatus("error");
        callbacks.current.controller.setLiveState("error");
        return;
      }
      setStatus("reconnecting");
      turnTaking.current.setSessionState("reconnecting");
      const delay = Math.min(2000, 250 * 2 ** reconnectAttempt.current);
      reconnectAttempt.current += 1;
      reconnectTimer.current = window.setTimeout(connect, delay);
    };
  }, [activeLanguagePolicy, conversationId, calibration, handleServerEvent, sendJson, teardownSession]);

  const start = useCallback(async () => {
    if (active.current) {
      teardownSession();
    }
    manualStop.current = false;
    pausedRef.current = false;
    setPaused(false);
    setStatus("connecting");
    setDetail("Requesting microphone permission…");
    setMetrics({});
    latency.current.reset();
    latency.current.mark("live_session_started");
    startupCalibrationCount.current = 0;
    // Each fresh session resets the one-shot mock-fallback retry.
    forcedMockFallback.current = false;
    turnTaking.current = new TurnTakingController({
      startThreshold: 0.012,
      speakerThreshold: outputMode === "speaker" ? 0.095 : 0.045,
      startFrames: 4,
      minimumSpeechFrames: 8,
      hesitationFrames: 14,
      endOfTurnFrames: 28,
      maxSilenceFrames: 40,
      maxSpeechFrames: 1000,
    });
    turnTaking.current.setSessionState("initializing");
    try {
      const media = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
        video: false,
      });
      const context = new AudioContext({ latencyHint: "interactive", sampleRate: 48000 });
      // Chrome suspends AudioContext by default — must resume to start mic processing
      if (context.state === "suspended") {
        await context.resume();
      }
      await context.audioWorklet.addModule("/worklets/pcm-capture.js");
      const mediaSource = context.createMediaStreamSource(media);

      // High-pass filter at 140Hz to eliminate fan rumble, desk vibrations, and 50/60Hz AC hum.
      // Human voice fundamentals start at 120Hz+ for women/children and 85Hz+ for men.
      // Filtering sub-140Hz attenuates 95%+ of mechanical fan motor/air turbulence noise.
      const highpass = context.createBiquadFilter();
      highpass.type = "highpass";
      highpass.frequency.value = 140;
      highpass.Q.value = 0.8;

      const node = new AudioWorkletNode(context, "hinaa-pcm-capture");
      const silent = context.createGain();
      silent.gain.value = 0;
      silentNode.current = silent;
      mediaSource.connect(highpass);
      highpass.connect(node);
      node.connect(silent);
      silent.connect(context.destination);
      node.port.onmessage = (message: MessageEvent) => {
        const value = message.data as { frame: ArrayBuffer; level: number };
        handleWorkletFrameRef.current?.(value.frame, value.level);
      };
      stream.current = media;
      audioContext.current = context;
      source.current = mediaSource;
      worklet.current = node;
      active.current = true;
      setDiagnostics((prev) => ({
        ...prev,
        micPermission: "granted",
        trackState: media.getAudioTracks()[0]?.readyState === "live" ? "live" : "ended",
        audioContextState: context.state,
        inputSampleRate: context.sampleRate,
        currentStage: "mic-ready",
      }));
      const mode = callbacks.current.controller.routing.activeMode;
      const providersReady = callbacks.current.controller.routing.providersLoaded;
      if (!providersReady && !mode) {
        setDetail("Voice services are still loading. Releasing microphone — try again shortly.");
        setDiagnostics((prev) => ({ ...prev, currentStage: "providers-loading" }));
        teardownSession();
        setStatus("error");
        callbacks.current.controller.setLiveState("error");
        return;
      }
      const effectiveMode = mode ?? "mock";
      setDetail(
        effectiveMode === "mock"
          ? "Diagnostic mock live · fixed demo transcript · pauses after one turn"
          : effectiveMode === "local"
            ? "Zero-credit local live · text/placeholder voice only until local STT is installed"
            : effectiveMode === "groq"
              ? "Groq brain live · local STT required before microphone speech works"
              : effectiveMode === "qwen"
                ? "Qwen brain live · ElevenLabs handles speech recognition and voice"
                : effectiveMode === "claude"
                  ? "Claude brain live · ElevenLabs handles speech recognition and voice"
                  : effectiveMode === "cx-gateway"
                    ? "CX brain live · ElevenLabs handles speech recognition and voice"
                    : effectiveMode === "custom"
                      ? "Custom gateway brain live · ElevenLabs handles speech recognition and voice"
                      : "Connecting realtime providers…",

      );
      connect();
    } catch (error) {
      teardownSession();
      setStatus("error");
      turnTaking.current.setSessionState("microphone_denied");
      setDiagnostics((prev) => ({ ...prev, micPermission: "denied", currentStage: "mic-denied" }));
      setDetail(
        error instanceof DOMException && error.name === "NotAllowedError"
          ? "Microphone permission denied · text mode still works"
          : "Live microphone setup failed safely · use text fallback",
      );
      // Mirror the failure into the companion state so the header pill and the
      // avatar show the error too, not just the stage status bar.
      callbacks.current.controller.setLiveState("error");
    }
  }, [connect, handleWorkletFrame, outputMode, teardownSession]);

  const pause = useCallback(() => {
    pushToTalkHeld.current = false;
    if (!active.current) return;
    pausedRef.current = true;
    setPaused(true);
    capturing.current = false;
    turnTaking.current.resetSpeech();
    turnTaking.current.setSessionState("listening");
    setStatus("paused");
    setDetail("Listening paused · microphone tracks remain until Stop");
  }, []);

  const resume = useCallback(() => {
    if (!active.current) return;
    pausedRef.current = false;
    setPaused(false);
    setStatus("listening");
    setDetail("Microphone active · hands-free listening");
    turnTaking.current.setSessionState("listening");
  }, []);

  const stop = useCallback(() => {
    pushToTalkHeld.current = false;
    manualStop.current = true;
    pausedRef.current = false;
    setPaused(false);
    teardownSession();
    setStatus("idle");
    setDetail("Live microphone is off");
    callbacks.current.controller.setLiveState("idle");
  }, [teardownSession]);

  // ── Chunk rate counter (updates diagnostics every second) ──
  useEffect(() => {
    const interval = window.setInterval(() => {
      chunksPerSecRef.current = chunksSentRef.current;
      chunksSentRef.current = 0;
      setDiagnostics((prev) => ({ ...prev, chunksSentPerSecond: chunksPerSecRef.current }));
    }, 1000);
    return () => window.clearInterval(interval);
  }, []);

  // ── Idle listening guard: auto-recover if speech buffer gets stuck ──
  useEffect(() => {
    if (status === "listening" && !pausedRef.current) {
      stuckTimerRef.current = window.setTimeout(() => {
        if (turnTaking.current?.currentState === "waiting_for_provider") {
          return; // turn already committed and awaiting brain — not stuck
        }
        if (status === "listening" && active.current && ready.current) {
          turnTaking.current.resetSpeech();
          capturing.current = false;
          preRoll.current = [];
          setDetail("Microphone active · hands-free listening");
        }
      }, 30_000);
      return () => window.clearTimeout(stuckTimerRef.current);
    }
    window.clearTimeout(stuckTimerRef.current);
  }, [status, paused, diagnostics.lastPartialTranscript, diagnostics.lastCommittedTranscript]);

  // ── Brain timeout: if thinking for >25s with no text delta, surface error ──
  useEffect(() => {
    if (brainPending) {
      brainTimerRef.current = window.setTimeout(() => {
        if (turnTaking.current?.currentState === "waiting_for_provider" && active.current) {
          teardownSession();
          turnTaking.current.setSessionState("error");
          setStatus("error");
          setBrainPending(false);
          setDetail("Brain response timed out — the selected provider may be unavailable. Try a different brain.");
          setDiagnostics((prev) => ({ ...prev, lastError: "BRAIN_TIMEOUT_25S", currentStage: "brain-timeout" }));
          callbacks.current.controller.setLiveState("error");
        }
      }, 25_000);
      return () => window.clearTimeout(brainTimerRef.current);
    }
    window.clearTimeout(brainTimerRef.current);
  }, [brainPending, teardownSession]);

  // ── Playback drain watchdog: when turn.complete is received but audio is still draining ──
  // This replaces the generic 15s timeout with queue-aware logic.
  useEffect(() => {
    if (turnCompleteReceivedRef.current) {
      const pq = playbackQueueRef.current;
      const audioStillPending = pq.encodedChunks > 0 || pq.decoding > 0 || pq.decodedBuffers > 0 || pq.scheduledSources > 0;
      if (audioStillPending || playback.playing) {
        // Audio is still draining — wait for it to finish, with a 30s safety net
        drainTimerRef.current = window.setTimeout(() => {
          // 30s passed and audio still hasn't drained — recover
          turnTaking.current.setSessionState("listening");
          setStatus("listening");
          setDetail("Voice playback took longer than expected · you can read my reply below");
          setDiagnostics((prev) => ({ ...prev, currentStage: "drain-timeout" }));
          callbacks.current.controller.setLiveState("listening");
        }, 30_000);
        return () => window.clearTimeout(drainTimerRef.current);
      }
    }
    window.clearTimeout(drainTimerRef.current);
  }, [status, playback.playing, diagnostics.audioChunksReceived]);

  // ── Manual commit: force the backend to transcribe what we have ──
  const manualCommit = useCallback(() => {
    if (!active.current || !ready.current || capturing.current) return;
    // Reset the stuck timer
    window.clearTimeout(stuckTimerRef.current);
    // New turn correlation: same reasoning as beginSpeech — the server will
    // assign a fresh turnId and it must be adopted, not discarded.
    activeTurnIdRef.current = "";
    voiceTrace("manual-commit", "generation:", generation.current);
    // Send a manual commit with the current audio buffer
    speechEndedAt.current = performance.now();
    latency.current.mark("speech_ended");
    latency.current.mark("turn_committed");
    sendJson({
      type: "audio.commit",
      generation: generation.current,
      endedAtMs: performance.now(),
    });
    capturing.current = false;
    turnTaking.current.setSessionState("waiting_for_provider");
    setBrainPending(true);
    setDetail("Manual commit sent · waiting for HINAA…");
    setDiagnostics((prev) => ({ ...prev, currentStage: "committed-manual" }));
  }, [sendJson]);

  const startPushToTalk = useCallback(() => {
    if (!active.current || !ready.current || pausedRef.current || pushToTalkHeld.current) return;
    pushToTalkHeld.current = true;
    if (capturing.current) return;
    callbacks.current.playback.stop();
    playbackState.current = false;
    generation.current += 1;
    sendJson({ type: "interrupt", generation: generation.current });
    turnTaking.current.forceSpeechStart();
    beginSpeech();
  }, [beginSpeech, sendJson]);

  const stopPushToTalk = useCallback(() => {
    pushToTalkHeld.current = false;
    if (!active.current || !ready.current || !capturing.current) return;
    speechEndedAt.current = performance.now();
    latency.current.mark("speech_ended");
    latency.current.mark("turn_committed");
    sendJson({
      type: "audio.commit",
      generation: generation.current,
      endedAtMs: performance.now(),
    });
    capturing.current = false;
    turnTaking.current.setSessionState("waiting_for_provider");
    setBrainPending(true);
    setDetail("Turn committed · waiting for HINAA…");
    setDiagnostics((prev) => ({ ...prev, currentStage: "committed-push-to-talk" }));
  }, [sendJson]);

  return {
    active: status !== "idle" && status !== "error",
    status,
    detail,
    microphoneLevel,
    metrics,
    voiceMetadata,
    paused,
    diagnostics,
    manualCommit,
    startPushToTalk,
    stopPushToTalk,
    start,
    pause,
    resume,
    stop,
  };
}
