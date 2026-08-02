import { useCallback, useEffect, useRef, useState } from "react";
import { parseAssistantTurnPlan } from "../../contracts/assistantTurnPlan";
import type { CompanionController } from "../companion/useCompanionController";
import type { PlaybackController } from "./useAudioPlayback";
import { LatencyClock } from "./latencyClock";
import { PhraseDetector } from "./phraseDetector";
import { TurnTakingController } from "./turnTakingController";

type LiveStatus =
  "idle" | "connecting" | "listening" | "paused" | "reconnecting" | "error";

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
  text?: string;
  delta?: string;
  plan?: unknown;
  audioBase64?: string;
  mediaType?: string;
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
}

interface LiveOptions {
  controller: CompanionController;
  playback: PlaybackController;
  calibration: "natural" | "soft" | "lively";
  outputMode: "headphones" | "speaker";
  languageMode: "fixed-ne-NP" | "auto";
}

function websocketUrl(): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/api/v1/realtime`;
}

function decodeAudio(value: string, mediaType = "audio/wav"): Blob {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1)
    bytes[index] = binary.charCodeAt(index);
  return new Blob([bytes], { type: mediaType });
}

export function useLiveConversation({
  controller,
  playback,
  calibration,
  outputMode,
  languageMode,
}: LiveOptions) {
  const [status, setStatus] = useState<LiveStatus>("idle");
  const [microphoneLevel, setMicrophoneLevel] = useState(0);
  const [detail, setDetail] = useState("Live microphone is off");
  const [metrics, setMetrics] = useState<LiveMetrics>({});
  const [voiceMetadata, setVoiceMetadata] = useState("");
  const [paused, setPaused] = useState(false);
  const socket = useRef<WebSocket | undefined>(undefined);
  const stream = useRef<MediaStream | undefined>(undefined);
  const audioContext = useRef<AudioContext | undefined>(undefined);
  const source = useRef<MediaStreamAudioSourceNode | undefined>(undefined);
  const worklet = useRef<AudioWorkletNode | undefined>(undefined);
  const active = useRef(false);
  const pausedRef = useRef(false);
  const manualStop = useRef(false);
  const ready = useRef(false);
  const generation = useRef(1);
  const sequence = useRef(0);
  const capturing = useRef(false);
  const preRoll = useRef<ArrayBuffer[]>([]);
  const reconnectAttempt = useRef(0);
  const reconnectTimer = useRef<number | undefined>(undefined);
  const heartbeat = useRef<number | undefined>(undefined);
  const playbackQueue = useRef(Promise.resolve());
  const playbackState = useRef(false);
  const speechStartedAt = useRef<number | undefined>(undefined);
  const speechEndedAt = useRef<number | undefined>(undefined);
  const finalAt = useRef<number | undefined>(undefined);
  const partialGeneration = useRef<number | undefined>(undefined);
  const textGeneration = useRef<number | undefined>(undefined);
  const audibleGeneration = useRef<number | undefined>(undefined);
  const lastPartial = useRef("");
  const turnTaking = useRef(new TurnTakingController());
  const phraseDetector = useRef(new PhraseDetector());
  const latency = useRef(new LatencyClock());
  const callbacks = useRef({ controller, playback });
  callbacks.current = { controller, playback };
  playbackState.current = playback.playing;

  const sendJson = useCallback((value: object) => {
    if (socket.current?.readyState === WebSocket.OPEN)
      socket.current.send(JSON.stringify(value));
  }, []);

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
      callbacks.current.playback.stop();
      playbackState.current = false;
      generation.current += 1;
      latency.current.mark("interruption_detected");
      latency.current.mark("playback_stopped");
      sendJson({ type: "interrupt", generation: generation.current });
    }
    sequence.current = 0;
    capturing.current = true;
    speechStartedAt.current = performance.now();
    speechEndedAt.current = undefined;
    finalAt.current = undefined;
    partialGeneration.current = undefined;
    textGeneration.current = undefined;
    audibleGeneration.current = undefined;
    lastPartial.current = "";
    phraseDetector.current.reset();
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
      const decision = turnTaking.current.process({
        level,
        assistantPlaying: playbackState.current,
        partialText: lastPartial.current,
        sessionActive: active.current && ready.current,
        paused: pausedRef.current,
      });
      setMetrics((current) => ({ ...current, turnState: decision.state }));

      if (decision.bargeIn) {
        const started = performance.now();
        callbacks.current.playback.stop();
        playbackState.current = false;
        generation.current += 1;
        latency.current.mark("interruption_detected");
        latency.current.mark("playback_stopped");
        sendJson({ type: "interrupt", generation: generation.current });
        turnTaking.current.setSessionState("interrupted");
        setMetrics((current) => ({
          ...current,
          bargeInStopMs: Math.round(performance.now() - started),
        }));
        setDetail("Interrupted · listening again");
      }

      if (!capturing.current) {
        preRoll.current.push(frame);
        if (preRoll.current.length > 10) preRoll.current.shift();
      }
      if (decision.speechStart) beginSpeech();
      else if (capturing.current) sendFrame(frame);
      if (decision.speechCommit && capturing.current) {
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
        setDetail("Turn committed · waiting for HINAA…");
      }
    },
    [beginSpeech, sendFrame, sendJson],
  );

  const handleServerEvent = useCallback((event: LiveEvent) => {
    if (
      typeof event.generation === "number" &&
      event.generation < generation.current
    )
      return;
    const current = callbacks.current;
    if (event.type === "session.ready") {
      ready.current = true;
      reconnectAttempt.current = 0;
      setStatus(pausedRef.current ? "paused" : "listening");
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
      if (speechEndedAt.current !== undefined)
        setMetrics((value) => ({
          ...value,
          finalAfterSpeechMs: Math.round(
            finalAt.current! - speechEndedAt.current!,
          ),
        }));
      current.controller.applyLiveFinal(event.text);
    } else if (event.type === "assistant.thinking") {
      current.controller.setLiveState("thinking");
    } else if (event.type === "assistant.text.delta" && event.delta) {
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
      const phrases = phraseDetector.current.push(event.delta);
      if (phrases.length) latency.current.mark("first_stable_phrase");
      current.controller.applyLiveDelta(event.delta);
    } else if (event.type === "assistant.plan") {
      phraseDetector.current.flush();
      latency.current.mark("final_text");
      try {
        current.controller.applyLivePlan(parseAssistantTurnPlan(event.plan));
      } catch {
        current.controller.applyLiveError(
          "The live response plan was invalid and was not animated.",
        );
      }
    } else if (event.type === "tts.audio" && event.audioBase64) {
      const eventGeneration = event.generation;
      latency.current.mark("tts_request_started");
      latency.current.mark("first_audio_chunk");
      setVoiceMetadata(
        `${event.requestedVoice ?? "voice unknown"} → ${event.actualVoice ?? "not confirmed"} · ${event.calibration ?? "natural"}`,
      );
      const blob = decodeAudio(event.audioBase64, event.mediaType);
      playbackQueue.current = playbackQueue.current.then(async () => {
        if (eventGeneration !== generation.current) return;
        current.controller.setLiveState("speaking");
        turnTaking.current.setSessionState("speaking");
        await current.playback.play(blob, () => {
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
        });
        if (
          event.segment === (event.segments ?? 0) - 1 &&
          speechEndedAt.current !== undefined
        ) {
          latency.current.mark("final_audio");
          setMetrics((value) => ({
            ...value,
            playbackCompleteAfterSpeechMs: Math.round(
              performance.now() - speechEndedAt.current!,
            ),
          }));
        }
      });
    } else if (event.type === "turn.complete") {
      latency.current.mark("turn_completed");
      setMetrics((value) => ({
        ...value,
        sttMs: event.sttMs,
        llmMs: event.llmMs,
        llmFirstDeltaMs: event.llmFirstDeltaMs,
        ttsMs: event.ttsMs,
        totalMs: event.totalMs,
      }));
      if (current.controller.providerMode === "mock") {
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
      turnTaking.current.setSessionState(
        pausedRef.current ? "listening" : "listening",
      );
      setDetail(
        pausedRef.current
          ? "Turn complete · listening paused"
          : "Turn complete · automatically listening again",
      );
      current.controller.setLiveState("listening");
    } else if (event.type === "turn.cancelled") {
      latency.current.mark("server_cancel_acknowledged");
      current.controller.setLiveState("listening");
      turnTaking.current.setSessionState("listening");
      setDetail("Previous response interrupted · listening");
    } else if (event.type === "error") {
      capturing.current = false;
      const code = event.code ?? "error";
      const liveProviderUnavailable =
        code.includes("PROVIDER") || code.includes("CONFIGURATION");
      turnTaking.current.setSessionState(
        liveProviderUnavailable ? "provider_unavailable" : "error",
      );
      current.controller.applyLiveError(
        event.message ??
          (liveProviderUnavailable
            ? "Live providers are temporarily unavailable. Text fallback remains."
            : `Live session stopped safely (${code}).`),
      );
      setStatus("error");
      setDetail(
        liveProviderUnavailable
          ? "Provider unavailable · no mock reply was substituted"
          : "Live turn failed · text fallback remains available",
      );
    }
  }, []);

  const connect = useCallback(() => {
    const next = new WebSocket(websocketUrl());
    socket.current = next;
    next.binaryType = "arraybuffer";
    next.onopen = () => {
      sendJson({
        type: "session.hello",
        protocolVersion: "1.0",
        sessionId: "browser-live",
        companionId: callbacks.current.controller.companionId,
        providerMode: callbacks.current.controller.providerMode,
        brainModel:
          callbacks.current.controller.providerMode === "openai" ||
          callbacks.current.controller.providerMode === "custom" ||
          callbacks.current.controller.providerMode === "real"
            ? callbacks.current.controller.brainModel
            : undefined,
        generation: generation.current,
        language: "mixed",
        languageMode,
        calibration,
      });
      heartbeat.current = window.setInterval(
        () => sendJson({ type: "ping", sentAtMs: performance.now() }),
        15_000,
      );
    };
    next.onmessage = (message) => {
      if (typeof message.data !== "string") return;
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
      if (reconnectAttempt.current >= 3) {
        setStatus("error");
        turnTaking.current.setSessionState("error");
        callbacks.current.controller.applyLiveError(
          "Realtime reconnection stopped after three bounded attempts.",
        );
        return;
      }
      setStatus("reconnecting");
      turnTaking.current.setSessionState("reconnecting");
      const delay = 250 * 2 ** reconnectAttempt.current;
      reconnectAttempt.current += 1;
      reconnectTimer.current = window.setTimeout(connect, delay);
    };
  }, [calibration, handleServerEvent, languageMode, sendJson]);

  const start = useCallback(async () => {
    if (active.current) return;
    manualStop.current = false;
    pausedRef.current = false;
    setPaused(false);
    setStatus("connecting");
    setDetail("Requesting microphone permission…");
    setMetrics({});
    latency.current.reset();
    latency.current.mark("live_session_started");
    turnTaking.current = new TurnTakingController({
      startThreshold: 0.025,
      speakerThreshold: outputMode === "speaker" ? 0.07 : 0.035,
      startFrames: 3,
      minimumSpeechFrames: 5,
      hesitationFrames: 12,
      endOfTurnFrames: 28,
      maxSilenceFrames: 45,
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
      const context = new AudioContext({ latencyHint: "interactive" });
      await context.audioWorklet.addModule("/worklets/pcm-capture.js");
      const mediaSource = context.createMediaStreamSource(media);
      const node = new AudioWorkletNode(context, "hinaa-pcm-capture");
      const silent = context.createGain();
      silent.gain.value = 0;
      mediaSource.connect(node).connect(silent).connect(context.destination);
      node.port.onmessage = (message: MessageEvent) => {
        const value = message.data as { frame: ArrayBuffer; level: number };
        handleWorkletFrame(value.frame, value.level);
      };
      stream.current = media;
      audioContext.current = context;
      source.current = mediaSource;
      worklet.current = node;
      active.current = true;
      const mode = callbacks.current.controller.providerMode;
      setDetail(
        mode === "mock"
          ? "Diagnostic mock live · fixed demo transcript · pauses after one turn"
          : mode === "local"
            ? "Zero-credit local live · text/placeholder voice only until local STT is installed"
            : mode === "groq"
              ? "Groq brain live · local STT required before microphone speech works"
              : mode === "custom"
                ? "Custom gateway brain live · Microsoft Speech handles voice"
              : "Connecting realtime providers…",
      );
      connect();
    } catch (error) {
      setStatus("error");
      turnTaking.current.setSessionState("microphone_denied");
      setDetail(
        error instanceof DOMException && error.name === "NotAllowedError"
          ? "Microphone permission denied · text mode still works"
          : "Live microphone setup failed safely · use text fallback",
      );
    }
  }, [connect, handleWorkletFrame, outputMode]);

  const pause = useCallback(() => {
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
    manualStop.current = true;
    active.current = false;
    ready.current = false;
    capturing.current = false;
    pausedRef.current = false;
    setPaused(false);
    sendJson({ type: "session.close" });
    socket.current?.close();
    socket.current = undefined;
    if (heartbeat.current) window.clearInterval(heartbeat.current);
    if (reconnectTimer.current) window.clearTimeout(reconnectTimer.current);
    worklet.current?.disconnect();
    source.current?.disconnect();
    for (const track of stream.current?.getTracks() ?? []) track.stop();
    if (audioContext.current?.state !== "closed")
      void audioContext.current?.close();
    callbacks.current.playback.stop();
    stream.current = undefined;
    worklet.current = undefined;
    source.current = undefined;
    audioContext.current = undefined;
    preRoll.current = [];
    turnTaking.current.resetSpeech();
    turnTaking.current.setSessionState("inactive");
    phraseDetector.current.reset();
    setMicrophoneLevel(0);
    setStatus("idle");
    setDetail("Live microphone is off");
    callbacks.current.controller.setLiveState("idle");
  }, [sendJson]);

  useEffect(() => stop, [stop]);

  return {
    active: status !== "idle" && status !== "error",
    status,
    detail,
    microphoneLevel,
    metrics,
    voiceMetadata,
    paused,
    start,
    pause,
    resume,
    stop,
  };
}
