import { useCallback, useEffect, useRef, useState } from "react";
import type { RichActivityStep } from "../features/chat/contracts/agentEvents";

export type LiveCallState = "idle" | "connecting" | "listening" | "thinking" | "speaking" | "error";

export interface LiveLatencyStats {
  asrMs: number | null;
  totalMs: number | null;
  route: string | null;
}

export function useLiveCall(wsPath = "/ws/live") {
  const [callState, setCallState] = useState<LiveCallState>("idle");
  const [partialCaption, setPartialCaption] = useState("");
  const [finalCaption, setFinalCaption] = useState("");
  const [assistantReply, setAssistantReply] = useState("");
  const [micLevel, setMicLevel] = useState(0);
  const [isPushToTalkActive, setIsPushToTalkActive] = useState(false);
  const [latency, setLatency] = useState<LiveLatencyStats>({ asrMs: null, totalMs: null, route: null });
  const [steps, setSteps] = useState<RichActivityStep[]>([]);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const disconnect = useCallback(() => {
    try {
      wsRef.current?.close();
    } catch {
      // ignore close errors
    }
    wsRef.current = null;
    if (streamRef.current) {
      for (const track of streamRef.current.getTracks()) {
        track.stop();
      }
      streamRef.current = null;
    }
    setCallState("idle");
    setMicLevel(0);
    setIsPushToTalkActive(false);
  }, []);

  useEffect(() => disconnect, [disconnect]);

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;
    setError(null);
    setCallState("connecting");
    try {
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(`${proto}//${window.location.host}${wsPath}`);
      ws.binaryType = "arraybuffer";
      ws.onopen = () => setCallState("listening");
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
            setAssistantReply(String(msg.text || ""));
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
  }, [wsPath]);

  const sendTextUtterance = useCallback((text: string) => {
    const clean = text.trim();
    if (!clean) return;
    setFinalCaption(clean);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "text", text: clean }));
    }
  }, []);

  const bargeIn = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "barge_in" }));
    }
    setCallState("listening");
  }, []);

  return {
    callState,
    partialCaption,
    finalCaption,
    assistantReply,
    micLevel,
    setMicLevel,
    isPushToTalkActive,
    setIsPushToTalkActive,
    latency,
    steps,
    error,
    connect,
    disconnect,
    sendTextUtterance,
    bargeIn,
  };
}
