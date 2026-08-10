/**
 * useVSeeFace.ts — VSeeFace face tracking via VTube Studio WebSocket API
 *
 * HOW IT WORKS:
 * 1. VSeeFace runs on your PC with "VTube Studio API" enabled (port 8001)
 * 2. This hook connects via WebSocket ws://localhost:8001
 * 3. First-time: requests an auth token → VSeeFace shows a dialog → user clicks Allow
 * 4. Token is saved to localStorage — future connections auto-authenticate
 * 5. Polls face parameters at ~30fps → returns expression blend values (0–1)
 * 6. These values are used to drive VRM blendshapes in real-time
 *
 * VSeeFace setup:
 *   General Settings → Enable VTube Studio API → Port: 8001
 */

import { useCallback, useEffect, useRef, useState } from "react";

/* ── Expression output ────────────────────────────────────── */
export interface FaceExpressions {
  mouthOpen:  number;   // → aa
  mouthSmile: number;   // → happy
  eyeBlinkL:  number;   // → blinkLeft  (1=open, 0=closed → we flip to blink amount)
  eyeBlinkR:  number;   // → blinkRight
  browUpL:    number;   // → surprised
  browUpR:    number;
  browDownL:  number;   // → angry
  browDownR:  number;
  cheekPuff:  number;   // → relaxed
}

export type TrackingStatus =
  | "disconnected"
  | "connecting"
  | "awaiting_auth"    // VSeeFace showing "Allow?" dialog
  | "authenticating"
  | "active"
  | "error";

export interface VSeeFaceState {
  status:      TrackingStatus;
  expressions: FaceExpressions;
  error:       string | null;
  connect:     () => void;
  disconnect:  () => void;
}

const WS_URL   = "ws://127.0.0.1:8001";
const STORAGE_KEY = "hinaa_vtube_token";
const PLUGIN_NAME = "HINAA";
const PLUGIN_DEV  = "HINAA Studio";

const PARAMS_TO_FETCH = [
  "MouthOpen",
  "MouthSmile",
  "EyeOpenLeft",
  "EyeOpenRight",
  "BrowUpLeftY",
  "BrowUpRightY",
  "BrowDownLeftAngle",
  "BrowDownRightAngle",
  "CheekPuffLeft",
  "CheekPuffRight",
];

const DEFAULT_EXPRESSIONS: FaceExpressions = {
  mouthOpen: 0, mouthSmile: 0,
  eyeBlinkL: 1, eyeBlinkR: 1,
  browUpL: 0, browUpR: 0,
  browDownL: 0, browDownR: 0,
  cheekPuff: 0,
};

function mapParams(values: Record<string, number>): FaceExpressions {
  return {
    mouthOpen:  clamp(values["MouthOpen"] ?? 0),
    mouthSmile: clamp(values["MouthSmile"] ?? 0),
    eyeBlinkL:  clamp(values["EyeOpenLeft"] ?? 1),   // 1=open, 0=closed
    eyeBlinkR:  clamp(values["EyeOpenRight"] ?? 1),
    browUpL:    clamp(values["BrowUpLeftY"] ?? 0),
    browUpR:    clamp(values["BrowUpRightY"] ?? 0),
    browDownL:  clamp(values["BrowDownLeftAngle"] ?? 0),
    browDownR:  clamp(values["BrowDownRightAngle"] ?? 0),
    cheekPuff:  clamp(((values["CheekPuffLeft"] ?? 0) + (values["CheekPuffRight"] ?? 0)) / 2),
  };
}

function clamp(v: number) { return Math.max(0, Math.min(1, v)); }

function makeRequest(messageType: string, data: object, id: string) {
  return JSON.stringify({
    apiName: "VTubeStudioPublicAPI",
    apiVersion: "1.0",
    requestID: id,
    messageType,
    data,
  });
}

export function useVSeeFace(): VSeeFaceState {
  const [status, setStatus] = useState<TrackingStatus>("disconnected");
  const [expressions, setExpressions] = useState<FaceExpressions>(DEFAULT_EXPRESSIONS);
  const [error, setError] = useState<string | null>(null);

  const wsRef       = useRef<WebSocket | null>(null);
  const tokenRef    = useRef<string | null>(null);
  const pollRef     = useRef<number | undefined>(undefined);
  const mountedRef  = useRef(true);

  const stopPolling = useCallback(() => {
    if (pollRef.current !== undefined) {
      window.clearInterval(pollRef.current);
      pollRef.current = undefined;
    }
  }, []);

  const disconnect = useCallback(() => {
    stopPolling();
    wsRef.current?.close();
    wsRef.current = null;
    if (mountedRef.current) {
      setStatus("disconnected");
      setExpressions(DEFAULT_EXPRESSIONS);
    }
  }, [stopPolling]);

  const startPolling = useCallback((ws: WebSocket) => {
    stopPolling();
    // Poll all parameters at ~30fps
    pollRef.current = window.setInterval(() => {
      if (ws.readyState !== WebSocket.OPEN) return;
      for (const name of PARAMS_TO_FETCH) {
        ws.send(makeRequest("ParameterValueRequest", { name }, `poll_${name}`));
      }
    }, 33);
  }, [stopPolling]);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    wsRef.current?.close();

    setStatus("connecting");
    setError(null);

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    const paramValues: Record<string, number> = {};

    ws.onopen = () => {
      if (!mountedRef.current) return;
      const savedToken = localStorage.getItem(STORAGE_KEY);

      if (savedToken) {
        // Try to authenticate with saved token
        tokenRef.current = savedToken;
        setStatus("authenticating");
        ws.send(makeRequest("AuthenticationRequest", {
          pluginName: PLUGIN_NAME,
          pluginDeveloper: PLUGIN_DEV,
          authenticationToken: savedToken,
        }, "auth"));
      } else {
        // Request a new token — VSeeFace will show "Allow?" dialog
        setStatus("awaiting_auth");
        ws.send(makeRequest("AuthenticationTokenRequest", {
          pluginName: PLUGIN_NAME,
          pluginDeveloper: PLUGIN_DEV,
          pluginIcon: null,
        }, "token_req"));
      }
    };

    ws.onmessage = (ev) => {
      if (!mountedRef.current) return;
      let msg: any;
      try { msg = JSON.parse(ev.data as string); } catch { return; }

      const type = msg.messageType as string;

      // Token received — save it and authenticate
      if (type === "AuthenticationTokenResponse") {
        const token: string = msg.data?.authenticationToken ?? "";
        if (token) {
          localStorage.setItem(STORAGE_KEY, token);
          tokenRef.current = token;
          setStatus("authenticating");
          ws.send(makeRequest("AuthenticationRequest", {
            pluginName: PLUGIN_NAME,
            pluginDeveloper: PLUGIN_DEV,
            authenticationToken: token,
          }, "auth"));
        } else {
          setStatus("error");
          setError("VSeeFace denied the auth request. Please click Allow in VSeeFace.");
        }
      }

      // Auth result
      if (type === "AuthenticationResponse") {
        const ok: boolean = msg.data?.authenticated ?? false;
        if (ok) {
          setStatus("active");
          setError(null);
          startPolling(ws);
        } else {
          // Token may be expired — clear it and retry
          localStorage.removeItem(STORAGE_KEY);
          tokenRef.current = null;
          setStatus("error");
          setError("Authentication failed. Click Connect again to re-authorize.");
        }
      }

      // Parameter value response — accumulate and update expressions
      if (type === "ParameterValueResponse") {
        const name: string  = msg.data?.name ?? "";
        const value: number = msg.data?.value ?? 0;
        if (name) {
          paramValues[name] = value;
          setExpressions(mapParams(paramValues));
        }
      }

      // Error from VTube Studio API
      if (type === "APIError") {
        const errID: number = msg.data?.errorID ?? 0;
        // 50 = unauthenticated
        if (errID === 50) {
          localStorage.removeItem(STORAGE_KEY);
          setStatus("error");
          setError("Session expired. Click Connect to re-authorize.");
          disconnect();
        }
      }
    };

    ws.onerror = () => {
      if (!mountedRef.current) return;
      setStatus("error");
      setError("Cannot connect to VSeeFace. Is VSeeFace running with VTube Studio API enabled on port 8001?");
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      stopPolling();
      if (status !== "error") setStatus("disconnected");
      setExpressions(DEFAULT_EXPRESSIONS);
    };
  }, [startPolling, stopPolling, disconnect, status]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      disconnect();
    };
  }, [disconnect]);

  return { status, expressions, error, connect, disconnect };
}
