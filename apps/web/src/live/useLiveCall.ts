import { useCallback, useEffect, useRef, useState } from "react";
import type { RichActivityStep } from "../features/chat/contracts/agentEvents";

export type LiveCallState = "idle" | "connecting" | "listening" | "thinking" | "speaking" | "error";

export type LiveVoiceEngine = "thalia" | "ana" | "luna" | "browser";

export interface LiveLatencyStats {
  asrMs: number | null;
  totalMs: number | null;
  route: string | null;
}

interface SpeechRecognitionAlternativeLike {
  transcript: string;
}

interface SpeechRecognitionResultLike {
  isFinal: boolean;
  length: number;
  0?: SpeechRecognitionAlternativeLike;
}

interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: {
    length: number;
    [index: number]: SpeechRecognitionResultLike;
  };
}

interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: { error?: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort?: () => void;
}

function getSpeechRecognitionCtor(): (new () => SpeechRecognitionLike) | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: new () => SpeechRecognitionLike;
    webkitSpeechRecognition?: new () => SpeechRecognitionLike;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function useLiveCall(wsPath = "/ws/live") {
  const [callState, setCallState] = useState<LiveCallState>("idle");
  const [partialCaption, setPartialCaption] = useState("");
  const [finalCaption, setFinalCaption] = useState("");
  const [assistantReply, setAssistantReply] = useState("");
  const [micLevel, setMicLevel] = useState(0);
  const [isPushToTalkActive, setIsPushToTalkActive] = useState(false);
  const [micActive, setMicActive] = useState(false);
  const [voiceEngine, setVoiceEngineState] = useState<LiveVoiceEngine>("thalia");
  const [audioMuted, setAudioMuted] = useState(false);
  const [lastAudioProvider, setLastAudioProvider] = useState<string | null>(null);
  const [latency, setLatency] = useState<LiveLatencyStats>({ asrMs: null, totalMs: null, route: null });
  const [steps, setSteps] = useState<RichActivityStep[]>([]);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioUrlRef = useRef<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const meterRafRef = useRef<number | null>(null);
  const audioMutedRef = useRef(false);
  const voiceEngineRef = useRef<LiveVoiceEngine>("thalia");
  const pendingUtterancesRef = useRef<string[]>([]);

  useEffect(() => {
    audioMutedRef.current = audioMuted;
  }, [audioMuted]);

  const stopAudioPlayback = useCallback(() => {
    if (audioRef.current) {
      try {
        audioRef.current.pause();
        audioRef.current.currentTime = 0;
      } catch {
        // ignore audio reset errors
      }
      audioRef.current = null;
    }
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current);
      audioUrlRef.current = null;
    }
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      try {
        window.speechSynthesis.cancel();
      } catch {
        // ignore speech synthesis cancellation issues
      }
    }
  }, []);

  const stopMic = useCallback(() => {
    if (meterRafRef.current != null) {
      cancelAnimationFrame(meterRafRef.current);
      meterRafRef.current = null;
    }
    if (recognitionRef.current) {
      try {
        recognitionRef.current.onresult = null;
        recognitionRef.current.onerror = null;
        recognitionRef.current.onend = null;
        recognitionRef.current.stop();
      } catch {
        // ignore recognition stop errors
      }
      recognitionRef.current = null;
    }
    if (audioCtxRef.current) {
      try {
        void audioCtxRef.current.close();
      } catch {
        // ignore AudioContext close errors
      }
      audioCtxRef.current = null;
    }
    if (streamRef.current) {
      for (const track of streamRef.current.getTracks()) {
        track.stop();
      }
      streamRef.current = null;
    }
    setMicActive(false);
    setMicLevel(0);
  }, []);

  const speakBrowserFallback = useCallback((text: string) => {
    if (audioMutedRef.current || typeof window === "undefined" || !("speechSynthesis" in window)) return;
    const clean = text.trim();
    if (!clean) return;
    try {
      window.speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(clean);
      const voices = window.speechSynthesis.getVoices();
      const preferred = voices.find((v) => /ana|jenny|aria|zira|samantha|female|google us english/i.test(v.name));
      if (preferred) utter.voice = preferred;
      utter.pitch = 1.12;
      utter.rate = 1.05;
      utter.onstart = () => setCallState("speaking");
      utter.onend = () => setCallState("listening");
      utter.onerror = () => setCallState("listening");
      window.speechSynthesis.speak(utter);
    } catch {
      // keep silent if speechSynthesis blocked
    }
  }, []);

  const playServerAudio = useCallback(
    (base64Data: string, mimeType: string, fallbackText?: string) => {
      if (audioMutedRef.current) return;
      stopAudioPlayback();
      try {
        const binary = window.atob(base64Data);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
          bytes[i] = binary.charCodeAt(i);
        }
        const blob = new Blob([bytes], { type: mimeType || "audio/mpeg" });
        const url = URL.createObjectURL(blob);
        audioUrlRef.current = url;
        const audio = new Audio(url);
        audioRef.current = audio;
        setCallState("speaking");
        audio.onended = () => {
          if (audioUrlRef.current === url) {
            URL.revokeObjectURL(url);
            audioUrlRef.current = null;
          }
          setCallState((prev) => (prev === "speaking" ? "listening" : prev));
        };
        audio.onerror = () => {
          if (fallbackText) speakBrowserFallback(fallbackText);
        };
        void audio.play().catch(() => {
          if (fallbackText) speakBrowserFallback(fallbackText);
        });
      } catch {
        if (fallbackText) speakBrowserFallback(fallbackText);
      }
    },
    [speakBrowserFallback, stopAudioPlayback],
  );

  const disconnect = useCallback(() => {
    stopAudioPlayback();
    stopMic();
    try {
      wsRef.current?.close();
    } catch {
      // ignore close errors
    }
    wsRef.current = null;
    setCallState("idle");
    setMicLevel(0);
    setIsPushToTalkActive(false);
  }, [stopAudioPlayback, stopMic]);

  useEffect(() => disconnect, [disconnect]);

  const setVoiceEngine = useCallback((next: LiveVoiceEngine) => {
    voiceEngineRef.current = next;
    setVoiceEngineState(next);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "config", voiceEngine: next }));
    }
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;
    setError(null);
    setCallState("connecting");
    try {
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(`${proto}//${window.location.host}${wsPath}`);
      ws.binaryType = "arraybuffer";
      ws.onopen = () => {
        setCallState("listening");
        ws.send(JSON.stringify({ type: "config", voiceEngine: voiceEngineRef.current }));
        const queued = pendingUtterancesRef.current.splice(0);
        for (const msgText of queued) {
          ws.send(JSON.stringify({ type: "text", text: msgText }));
        }
      };
      ws.onerror = () => {
        setError("Live voice connection failed.");
        setCallState("error");
      };
      ws.onclose = () => {
        setCallState((prev) => (prev === "error" ? "error" : "idle"));
      };
      ws.onmessage = (ev) => {
        if (typeof ev.data !== "string") return;
        try {
          const msg = JSON.parse(ev.data) as Record<string, unknown>;
          if (msg.type === "asr.partial") {
            setPartialCaption(String(msg.text || ""));
          } else if (msg.type === "asr.final") {
            setFinalCaption(String(msg.text || ""));
            setPartialCaption("");
          } else if (msg.type === "assistant.spoken") {
            const spoken = String(msg.text || "");
            setAssistantReply(spoken);
            if (voiceEngineRef.current === "browser") {
              speakBrowserFallback(spoken);
            }
          } else if (msg.type === "assistant.audio" && typeof msg.audioBase64 === "string" && msg.audioBase64) {
            if (typeof msg.provider === "string") setLastAudioProvider(msg.provider);
            playServerAudio(
              msg.audioBase64,
              typeof msg.mimeType === "string" ? msg.mimeType : "audio/mpeg",
            );
          } else if (msg.type === "tts.stop") {
            stopAudioPlayback();
            setCallState("listening");
          } else if (msg.type === "latency") {
            setLatency({
              asrMs: typeof msg.asrMs === "number" ? msg.asrMs : null,
              totalMs: typeof msg.totalMs === "number" ? msg.totalMs : null,
              route: typeof msg.route === "string" ? msg.route : null,
            });
          } else if (msg.type === "tool.started") {
            setSteps((prev) => [
              ...prev,
              {
                id: `live-step-${prev.length + 1}`,
                toolName: String(msg.toolName || "tool"),
                title: String(msg.label || msg.toolName || "Running tool"),
                status: "running",
              },
            ]);
          } else if (msg.type === "state" && typeof msg.state === "string") {
            const st = msg.state as LiveCallState;
            if (["idle", "listening", "thinking", "speaking"].includes(st)) {
              setCallState(st);
            }
          }
        } catch {
          // ignore malformed control message
        }
      };
      wsRef.current = ws;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not initialize WebSocket");
      setCallState("error");
    }
  }, [playServerAudio, speakBrowserFallback, stopAudioPlayback, wsPath]);

  const startMic = useCallback(async () => {
    setError(null);
    if (micActive) return;

    const SpeechCtor = getSpeechRecognitionCtor();
    let startedAny = false;

    if (SpeechCtor) {
      try {
        const rec = new SpeechCtor();
        rec.continuous = true;
        rec.interimResults = true;
        rec.lang = "en-US";
        rec.onresult = (event) => {
          for (let i = event.resultIndex; i < event.results.length; i++) {
            const res = event.results[i];
            const transcript = res?.[0]?.transcript?.trim();
            if (!transcript) continue;
            if (res.isFinal) {
              setPartialCaption("");
              setFinalCaption(transcript);
              if (wsRef.current?.readyState === WebSocket.OPEN) {
                wsRef.current.send(
                  JSON.stringify({ type: "audio.transcript", text: transcript, isFinal: true }),
                );
              }
            } else {
              setPartialCaption(transcript);
            }
          }
        };
        rec.onerror = (ev) => {
          if (ev.error && ev.error !== "aborted" && ev.error !== "no-speech") {
            setError(`Mic speech capture: ${ev.error}`);
          }
        };
        rec.onend = () => {
          if (recognitionRef.current === rec) {
            setMicActive(false);
          }
        };
        recognitionRef.current = rec;
        rec.start();
        startedAny = true;
      } catch {
        // Fallback smoothly to getUserMedia or typed input below
      }
    }

    if (typeof navigator !== "undefined" && navigator.mediaDevices?.getUserMedia) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        streamRef.current = stream;
        const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        if (AudioCtx) {
          const ctx = new AudioCtx();
          audioCtxRef.current = ctx;
          const src = ctx.createMediaStreamSource(stream);
          const analyser = ctx.createAnalyser();
          analyser.fftSize = 256;
          src.connect(analyser);
          const bins = new Uint8Array(analyser.frequencyBinCount);
          const pumpLevel = () => {
            analyser.getByteFrequencyData(bins);
            let sum = 0;
            for (let i = 0; i < bins.length; i++) sum += bins[i]!;
            const avg = sum / Math.max(1, bins.length);
            setMicLevel(Math.min(1, avg / 90));
            meterRafRef.current = requestAnimationFrame(pumpLevel);
          };
          meterRafRef.current = requestAnimationFrame(pumpLevel);
        }
        startedAny = true;
      } catch (err) {
        if (!startedAny) {
          setError(err instanceof Error ? err.message : "Microphone access unavailable. Use text box below.");
        }
      }
    }

    if (startedAny) {
      setMicActive(true);
    }
  }, [micActive]);

  const sendTextUtterance = useCallback((text: string) => {
    const clean = text.trim();
    if (!clean) return;
    stopAudioPlayback();
    setFinalCaption(clean);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "text", text: clean }));
      return;
    }
    pendingUtterancesRef.current.push(clean);
    if (!wsRef.current || wsRef.current.readyState === WebSocket.CLOSED) {
      connect();
    }
  }, [connect, stopAudioPlayback]);

  const bargeIn = useCallback(() => {
    stopAudioPlayback();
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "barge_in" }));
    }
    setCallState("listening");
  }, [stopAudioPlayback]);

  return {
    callState,
    partialCaption,
    finalCaption,
    assistantReply,
    micLevel,
    setMicLevel,
    isPushToTalkActive,
    setIsPushToTalkActive,
    micActive,
    startMic,
    stopMic,
    voiceEngine,
    setVoiceEngine,
    audioMuted,
    setAudioMuted,
    lastAudioProvider,
    latency,
    steps,
    error,
    connect,
    disconnect,
    sendTextUtterance,
    bargeIn,
  };
}
