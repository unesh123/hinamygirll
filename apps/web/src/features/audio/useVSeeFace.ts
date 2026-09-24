import { useCallback, useEffect, useRef, useState } from "react";

/** Values consumed directly by AvatarPresence on its render loop. */
export interface FaceExpressions {
  mouthOpen: number;
  mouthA: number;
  mouthI: number;
  mouthU: number;
  mouthE: number;
  mouthO: number;
  mouthSmile: number;
  eyeBlinkL: number;
  eyeBlinkR: number;
  browUpL: number;
  browUpR: number;
  browDownL: number;
  browDownR: number;
  cheekPuff: number;
  angry: number;
  sad: number;
  relaxed: number;
}

export type TrackingStatus =
  | "disabled"
  | "connecting"
  | "listening"
  | "live"
  | "stale"
  | "test"
  | "disconnected"
  | "error";

export type VmcDiagnostics = {
  state: "disconnected" | "listening" | "live" | "stale" | "test";
  listening: boolean;
  receiverInstanceId: string | null;
  host: string;
  port: number;
  lastPacketTimestamp: string | null;
  packetAgeMs: number | null;
  packetRate: number;
  packetCount: number;
  detectedChannels: string[];
  source: "none" | "external" | "synthetic";
  sender: string | null;
  webSocketClients: number;
  connectionAttempts: number;
  staleAfterMs: number;
  sequence: number;
};

export type TrackingCalibration = {
  capturedAt: string;
  /** Captured only while fresh external packets are live; never a webcam frame. */
  headBaseline?: [number, number, number, number];
  /** Complete neutral facial baseline so sender-specific resting offsets do not become an expression. */
  expressionBaseline: FaceExpressions;
};

export interface VSeeFaceState {
  status: TrackingStatus;
  /** A stable mutable sample: AvatarPresence reads it per frame without React rerenders per packet. */
  expressions: FaceExpressions;
  expressionsRef: React.MutableRefObject<FaceExpressions>;
  bonesRef: React.MutableRefObject<Record<string, [number, number, number, number]>>;
  diagnostics: VmcDiagnostics | null;
  /** True only after the bridge has observed at least one supported expression channel. */
  hasFacialSignal: boolean;
  calibration: TrackingCalibration | null;
  error: string | null;
  connectionId: string | null;
  connect: () => void;
  disconnect: () => void;
  reconnect: () => void;
  refresh: () => Promise<void>;
  testSignal: () => Promise<void>;
  calibrate: () => boolean;
  resetCalibration: () => void;
}

const WS_URL = "ws://127.0.0.1:8000/ws/vmc";
const STATUS_URL = "/api/v1/vmc/status";
const TEST_URL = "/api/v1/vmc/test-signal";
const POLL_MS = 500;

const DEFAULT_EXPRESSIONS: FaceExpressions = {
  mouthOpen: 0, mouthA: 0, mouthI: 0, mouthU: 0, mouthE: 0, mouthO: 0, mouthSmile: 0,
  // VMC publishes `Fcl_EYE_Close_*` closure weights: zero is an open eye.
  eyeBlinkL: 0, eyeBlinkR: 0, browUpL: 0, browUpR: 0, browDownL: 0, browDownR: 0,
  cheekPuff: 0, angry: 0, sad: 0, relaxed: 0,
};

function emptyDiagnostics(): VmcDiagnostics {
  return {
    state: "disconnected", listening: false, receiverInstanceId: null, host: "127.0.0.1", port: 39539,
    lastPacketTimestamp: null, packetAgeMs: null, packetRate: 0, packetCount: 0, detectedChannels: [],
    source: "none", sender: null, webSocketClients: 0, connectionAttempts: 0, staleAfterMs: 1500, sequence: 0,
  };
}

function toClientStatus(diagnostics: VmcDiagnostics, connected: boolean): TrackingStatus {
  if (!connected) return "disconnected";
  if (diagnostics.state === "live") return "live";
  if (diagnostics.state === "test") return "test";
  if (diagnostics.state === "stale") return "stale";
  if (diagnostics.state === "listening") return "listening";
  return diagnostics.listening ? "listening" : "disconnected";
}

function safeExpressionUpdate(target: FaceExpressions, value: unknown): void {
  if (!value || typeof value !== "object") return;
  for (const key of Object.keys(DEFAULT_EXPRESSIONS) as Array<keyof FaceExpressions>) {
    const candidate = (value as Record<string, unknown>)[key];
    if (typeof candidate === "number" && Number.isFinite(candidate)) {
      target[key] = Math.max(0, Math.min(1, candidate));
    }
  }
}

/**
 * One browser VMC consumer. It treats WebSocket connectivity as transport only;
 * only fresh externally sourced bridge diagnostics may produce `live`.
 */
export function useVSeeFace(): VSeeFaceState {
  const [status, setStatus] = useState<TrackingStatus>("disconnected");
  const [diagnostics, setDiagnostics] = useState<VmcDiagnostics | null>(null);
  const [calibration, setCalibration] = useState<TrackingCalibration | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connectionId, setConnectionId] = useState<string | null>(null);

  const expressionsRef = useRef<FaceExpressions>({ ...DEFAULT_EXPRESSIONS });
  const bonesRef = useRef<Record<string, [number, number, number, number]>>({});
  const wsRef = useRef<WebSocket | null>(null);
  const pollTimerRef = useRef<number | null>(null);
  const mountedRef = useRef(true);
  const connectedRef = useRef(false);
  const manualDisconnectRef = useRef(false);

  const clearPolling = useCallback(() => {
    if (pollTimerRef.current !== null) window.clearInterval(pollTimerRef.current);
    pollTimerRef.current = null;
  }, []);

  const resetSamples = useCallback(() => {
    Object.assign(expressionsRef.current, DEFAULT_EXPRESSIONS);
    bonesRef.current = {};
  }, []);

  const refresh = useCallback(async () => {
    try {
      const response = await fetch(STATUS_URL);
      if (!response.ok) throw new Error("HINAA VMC diagnostics are unavailable.");
      const next = await response.json() as VmcDiagnostics;
      if (!mountedRef.current) return;
      setDiagnostics(next);
      if (connectedRef.current) setStatus(toClientStatus(next, true));
    } catch (cause) {
      if (!mountedRef.current || !connectedRef.current) return;
      setStatus("error");
      setError(cause instanceof Error ? cause.message : "Could not read HINAA VMC diagnostics.");
    }
  }, []);

  const startPolling = useCallback(() => {
    clearPolling();
    void refresh();
    pollTimerRef.current = window.setInterval(() => void refresh(), POLL_MS);
  }, [clearPolling, refresh]);

  const disconnect = useCallback(() => {
    manualDisconnectRef.current = true;
    clearPolling();
    connectedRef.current = false;
    wsRef.current?.close(1000, "HINAA user disconnected tracking");
    wsRef.current = null;
    resetSamples();
    if (mountedRef.current) {
      setStatus("disconnected");
      setConnectionId(null);
      setError(null);
    }
  }, [clearPolling, resetSamples]);

  const connect = useCallback(() => {
    const readyState = wsRef.current?.readyState;
    if (readyState === WebSocket.OPEN || readyState === WebSocket.CONNECTING) {
      void refresh();
      return;
    }
    manualDisconnectRef.current = false;
    setStatus("connecting");
    setError(null);
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current || wsRef.current !== ws) return;
      connectedRef.current = true;
      setConnectionId(`vmc-ws-${Date.now().toString(36)}`);
      startPolling();
    };

    ws.onmessage = (event) => {
      if (!mountedRef.current || wsRef.current !== ws) return;
      try {
        const data = JSON.parse(event.data as string) as {
          blendshapes?: unknown;
          bones?: Record<string, [number, number, number, number]>;
          tracking?: VmcDiagnostics;
        };
        const externallyLive = data.tracking?.state === "live" && data.tracking.source === "external";
        if (data.tracking) {
          setDiagnostics(data.tracking);
          setStatus(toClientStatus(data.tracking, true));
        }
        // WebSocket connectivity, synthetic test packets, and stale diagnostics
        // are transport information—not avatar motion authority. Only fresh
        // external packets may influence HINAA’s expression/head samples.
        if (externallyLive) {
          safeExpressionUpdate(expressionsRef.current, data.blendshapes);
          if (data.bones && typeof data.bones === "object") bonesRef.current = data.bones;
        } else if (data.tracking) {
          resetSamples();
        }
      } catch {
        // One malformed sender payload must not terminate chat or the tracking receiver.
      }
    };

    ws.onerror = () => {
      if (!mountedRef.current || wsRef.current !== ws) return;
      setStatus("error");
      setError("Cannot connect to HINAA's local VMC bridge. Keep chat open and retry after the API is running.");
    };

    ws.onclose = () => {
      if (!mountedRef.current || wsRef.current !== ws) return;
      clearPolling();
      connectedRef.current = false;
      wsRef.current = null;
      resetSamples();
      setConnectionId(null);
      if (manualDisconnectRef.current) {
        setStatus("disconnected");
        return;
      }
      setStatus("error");
      setError("The VMC bridge connection closed. Reconnect after checking local VSeeFace settings.");
    };
  }, [clearPolling, refresh, resetSamples, startPolling]);

  const reconnect = useCallback(() => {
    disconnect();
    window.setTimeout(connect, 0);
  }, [connect, disconnect]);

  const testSignal = useCallback(async () => {
    try {
      const response = await fetch(TEST_URL, { method: "POST" });
      if (!response.ok) throw new Error("The HINAA test signal could not be started.");
      const next = await response.json() as VmcDiagnostics;
      if (!mountedRef.current) return;
      setDiagnostics(next);
      if (connectedRef.current) setStatus(toClientStatus(next, true));
    } catch (cause) {
      if (!mountedRef.current) return;
      setStatus("error");
      setError(cause instanceof Error ? cause.message : "The HINAA test signal failed.");
    }
  }, []);

  const calibrate = useCallback(() => {
    if (status !== "live") {
      setError("Neutral calibration requires fresh external VSeeFace tracking, not a listening socket or test signal.");
      return false;
    }
    const source = expressionsRef.current;
    const head = bonesRef.current.Head;
    const headBaseline = head && head.length === 4 && head.every((value) => Number.isFinite(value))
      ? [head[0], head[1], head[2], head[3]] as [number, number, number, number]
      : undefined;
    setCalibration({
      capturedAt: new Date().toISOString(),
      headBaseline,
      expressionBaseline: { ...source },
    });
    return true;
  }, [status]);

  const resetCalibration = useCallback(() => setCalibration(null), []);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      clearPolling();
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [clearPolling]);

  const hasFacialSignal = status === "live" && diagnostics?.source === "external" && (diagnostics.detectedChannels.some((channel) => channel.startsWith("expression:")) ?? false);

  return {
    status,
    expressions: expressionsRef.current,
    expressionsRef,
    bonesRef,
    diagnostics,
    hasFacialSignal,
    calibration,
    error,
    connectionId,
    connect,
    disconnect,
    reconnect,
    refresh,
    testSignal,
    calibrate,
    resetCalibration,
  };
}
