import { useCallback, useEffect, useRef, useState } from "react";

export const VISION_CONSENT_KEY = "hinaa.vision.consent";
const MAX_FRAME_WIDTH = 640;
const JPEG_QUALITY = 0.6;

export interface VisionReaction {
  emotion: string;
  remark: string;
  shouldSpeak: boolean;
  salientEvent: string;
  wellbeingFlag: string;
  memoryCandidate?: string;
}

export interface UseCompanionVisionOptions {
  /** Called only for reactions the backend marked should_speak. */
  onReaction?: (reaction: VisionReaction) => void;
  /** Seconds between sampled frames. */
  intervalSeconds?: number;
  sedentaryMinutes?: number;
  /** Opt-in: backend returns a text-only memory candidate. Frames are never stored. */
  storeObservations?: boolean;
  sessionId?: string;
  context?: string;
  getHeaders?: () => Record<string, string>;
  /** Test seam; defaults to a downscaling canvas capture. */
  captureFrame?: (video: HTMLVideoElement) => string | null;
}

function apiBase(): string {
  const raw = import.meta.env.VITE_HINAA_API_BASE_URL;
  return raw ? String(raw).replace(/\/+$/, "") : "";
}

export function defaultCaptureFrame(video: HTMLVideoElement): string | null {
  if (video.readyState < 2 || !video.videoWidth) return null;
  const scale = Math.min(1, MAX_FRAME_WIDTH / video.videoWidth);
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(video.videoWidth * scale);
  canvas.height = Math.round(video.videoHeight * scale);
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", JPEG_QUALITY);
}

function readConsent(): boolean {
  try {
    return localStorage.getItem(VISION_CONSENT_KEY) === "granted";
  } catch {
    return false;
  }
}

export function useCompanionVision(options: UseCompanionVisionOptions = {}) {
  const [consent, setConsentState] = useState<boolean>(readConsent);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastReaction, setLastReaction] = useState<VisionReaction | null>(null);

  const optionsRef = useRef(options);
  optionsRef.current = options;

  const setConsent = useCallback((granted: boolean) => {
    try {
      if (granted) localStorage.setItem(VISION_CONSENT_KEY, "granted");
      else localStorage.removeItem(VISION_CONSENT_KEY);
    } catch {
      /* storage unavailable: consent still applies for this session */
    }
    setConsentState(granted);
  }, []);

  useEffect(() => {
    if (!consent) {
      setStream(null);
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Camera is not available in this browser.");
      return;
    }

    let cancelled = false;
    let timer: number | null = null;
    let inflight: AbortController | null = null;
    let busy = false;
    let media: MediaStream | null = null;
    const video = document.createElement("video");
    video.muted = true;
    video.playsInline = true;

    const sample = async () => {
      if (busy || cancelled || document.hidden) return;
      const opts = optionsRef.current;
      const frame = (opts.captureFrame ?? defaultCaptureFrame)(video);
      if (!frame) return;
      busy = true;
      inflight = new AbortController();
      try {
        const response = await fetch(`${apiBase()}/api/v1/vision/react`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...(opts.getHeaders?.() ?? {}) },
          body: JSON.stringify({
            frame,
            consent: true,
            sessionId: opts.sessionId,
            context: opts.context,
            sedentaryMinutes: opts.sedentaryMinutes,
            storeObservations: opts.storeObservations ?? false,
          }),
          signal: inflight.signal,
        });
        if (!response.ok) throw new Error(`vision ${response.status}`);
        const data = await response.json();
        if (cancelled) return;
        const reaction: VisionReaction = {
          emotion: String(data.emotion ?? "neutral"),
          remark: String(data.remark ?? ""),
          shouldSpeak: Boolean(data.should_speak),
          salientEvent: String(data.salient_event ?? "none"),
          wellbeingFlag: String(data.wellbeing_flag ?? "none"),
          memoryCandidate: data.memory_candidate,
        };
        setError(null);
        setLastReaction(reaction);
        if (reaction.shouldSpeak) opts.onReaction?.(reaction);
      } catch (err) {
        if (!cancelled && (err as Error).name !== "AbortError") setError("Vision is unavailable right now.");
      } finally {
        busy = false;
      }
    };

    const start = () => {
      if (timer === null) {
        timer = window.setInterval(() => void sample(), (optionsRef.current.intervalSeconds ?? 20) * 1000);
      }
    };
    const stop = () => {
      if (timer !== null) {
        window.clearInterval(timer);
        timer = null;
      }
      inflight?.abort();
    };
    const onVisibility = () => (document.hidden ? stop() : start());

    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: "user", width: { ideal: 640 } }, audio: false })
      .then((s) => {
        if (cancelled) {
          s.getTracks().forEach((t) => t.stop());
          return;
        }
        media = s;
        video.srcObject = s;
        try {
          void Promise.resolve(video.play()).catch(() => undefined);
        } catch {
          /* autoplay can be blocked; frames still arrive once playing */
        }
        setStream(s);
        setError(null);
        if (!document.hidden) start();
        document.addEventListener("visibilitychange", onVisibility);
      })
      .catch(() => {
        if (cancelled) return;
        setError("Camera permission was denied.");
        setConsent(false);
      });

    return () => {
      cancelled = true;
      stop();
      document.removeEventListener("visibilitychange", onVisibility);
      media?.getTracks().forEach((t) => t.stop());
      video.srcObject = null;
      setStream(null);
    };
  }, [consent, setConsent]);

  return { consent, setConsent, active: stream !== null, stream, error, lastReaction };
}
