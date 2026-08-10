/**
 * useVSeeFace.ts — VSeeFace face tracking via HINAA VMC bridge
 *
 * HOW IT WORKS:
 * 1. VSeeFace runs and tracks your face via webcam
 * 2. VSeeFace sends data via VMC Protocol (UDP) to port 39539
 * 3. HINAA backend (Python/FastAPI) receives the UDP packets and parses blendshapes
 * 4. This hook connects to the backend WebSocket at ws://localhost:8000/ws/vmc
 * 5. Receives JSON { mouthOpen, mouthSmile, eyeBlinkL, eyeBlinkR, ... } at 30fps
 * 6. These values drive VRM expressions in AvatarPresence in real time
 *
 * VSeeFace setup (ONE TIME):
 *   General Settings → ✅ Send data with VMC protocol
 *   IP: 127.0.0.1   Port: 39539   → Save
 *
 * That's it! Click 🎭 Face in HINAA to start tracking.
 */

import { useCallback, useEffect, useRef, useState } from "react";

/* ── Expression output shape ─────────────────────────────────────────── */
export interface FaceExpressions {
  mouthOpen:  number;   // → aa  (lip sync when not speaking)
  mouthSmile: number;   // → happy
  eyeBlinkL:  number;   // 1=open, 0=closed (we flip: blink = 1 - open)
  eyeBlinkR:  number;
  browUpL:    number;   // → surprised
  browUpR:    number;
  browDownL:  number;   // → angry
  browDownR:  number;
  cheekPuff:  number;   // → relaxed
}

export type TrackingStatus =
  | "disconnected"
  | "connecting"
  | "active"
  | "error";

export interface VSeeFaceState {
  status:      TrackingStatus;
  expressions: FaceExpressions;
  error:       string | null;
  connect:     () => void;
  disconnect:  () => void;
}

const WS_URL = "ws://127.0.0.1:8000/ws/vmc";

const DEFAULT_EXPRESSIONS: FaceExpressions = {
  mouthOpen: 0, mouthSmile: 0,
  eyeBlinkL: 1, eyeBlinkR: 1,
  browUpL: 0, browUpR: 0,
  browDownL: 0, browDownR: 0,
  cheekPuff: 0,
};

export function useVSeeFace(): VSeeFaceState {
  const [status, setStatus]           = useState<TrackingStatus>("disconnected");
  const [expressions, setExpressions] = useState<FaceExpressions>(DEFAULT_EXPRESSIONS);
  const [error, setError]             = useState<string | null>(null);

  const wsRef      = useRef<WebSocket | null>(null);
  const mountedRef = useRef(true);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
    if (mountedRef.current) {
      setStatus("disconnected");
      setExpressions(DEFAULT_EXPRESSIONS);
      setError(null);
    }
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    wsRef.current?.close();

    setStatus("connecting");
    setError(null);

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      setStatus("active");
      setError(null);
    };

    ws.onmessage = (ev) => {
      if (!mountedRef.current) return;
      try {
        const data = JSON.parse(ev.data as string) as Partial<FaceExpressions>;
        setExpressions(prev => ({ ...prev, ...data }));
      } catch { /* ignore parse errors */ }
    };

    ws.onerror = () => {
      if (!mountedRef.current) return;
      setStatus("error");
      setError(
        "Cannot connect to HINAA backend (ws://localhost:8000/ws/vmc). " +
        "Make sure the HINAA API is running, then try again."
      );
    };

    ws.onclose = (ev) => {
      if (!mountedRef.current) return;
      setExpressions(DEFAULT_EXPRESSIONS);
      if (status !== "error") {
        if (ev.code === 1006) {
          setStatus("error");
          setError("Connection lost. Is VSeeFace running with VMC Protocol enabled on port 39539?");
        } else {
          setStatus("disconnected");
        }
      }
    };
  }, [status]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      disconnect();
    };
  }, [disconnect]);

  return { status, expressions, error, connect, disconnect };
}
