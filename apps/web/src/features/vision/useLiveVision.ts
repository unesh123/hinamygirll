import { useCallback, useEffect, useRef, useState } from "react";

export type VisionMode = "off" | "screen" | "camera";

export interface VisionObservation {
  ok: boolean;
  observation?: string;
  query?: string;
  provider?: string;
  timestamp?: number;
  error?: string;
}

export function useLiveVision(conversationId?: string) {
  const [mode, setMode] = useState<VisionMode>("off");
  const [latestFrame, setLatestFrame] = useState<string | null>(null);
  const [isObserving, setIsObserving] = useState(false);
  const [lastObservation, setLastObservation] = useState<VisionObservation | null>(null);
  const [error, setError] = useState<string | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const intervalRef = useRef<number | null>(null);

  const stopCapture = useCallback(() => {
    if (intervalRef.current) {
      window.clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
      videoRef.current = null;
    }
    setMode("off");
    setLatestFrame(null);
  }, []);

  const grabFrame = useCallback((): string | null => {
    const video = videoRef.current;
    if (!video || video.readyState < 2) return null;

    try {
      const canvas = document.createElement("canvas");
      // Scale down large screens for fast inference (max 1280px width)
      const maxDim = 1280;
      let width = video.videoWidth || 1280;
      let height = video.videoHeight || 720;
      if (width > maxDim) {
        height = Math.round((height * maxDim) / width);
        width = maxDim;
      }
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      if (!ctx) return null;
      ctx.drawImage(video, 0, 0, width, height);
      const dataUrl = canvas.toDataURL("image/jpeg", 0.82);
      setLatestFrame(dataUrl);
      return dataUrl;
    } catch (err) {
      console.warn("[LiveVision] Error capturing frame:", err);
      return null;
    }
  }, []);

  const startScreenShare = useCallback(async () => {
    try {
      stopCapture();
      setError(null);
      if (!navigator.mediaDevices?.getDisplayMedia) {
        throw new Error("Screen sharing is not supported in this browser.");
      }
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: { frameRate: { ideal: 5, max: 10 } },
        audio: false,
      });
      streamRef.current = stream;

      const video = document.createElement("video");
      video.autoplay = true;
      video.muted = true;
      video.playsInline = true;
      video.srcObject = stream;
      videoRef.current = video;

      await video.play().catch(() => undefined);

      // Handle user stopping share from browser banner
      const track = stream.getVideoTracks()[0];
      if (track) {
        track.onended = () => {
          stopCapture();
        };
      }

      setMode("screen");
      // Grab initial frame once video is playing
      window.setTimeout(() => {
        grabFrame();
      }, 500);

      // Periodic background frame refresh (every 4 seconds)
      intervalRef.current = window.setInterval(() => {
        grabFrame();
      }, 4000);
    } catch (err: any) {
      if (err.name !== "NotAllowedError") {
        setError(err.message || "Failed to start screen share");
      }
      stopCapture();
    }
  }, [grabFrame, stopCapture]);

  const startCamera = useCallback(async () => {
    try {
      stopCapture();
      setError(null);
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("Camera is not supported in this browser.");
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 1280 } },
        audio: false,
      });
      streamRef.current = stream;

      const video = document.createElement("video");
      video.autoplay = true;
      video.muted = true;
      video.playsInline = true;
      video.srcObject = stream;
      videoRef.current = video;

      await video.play().catch(() => undefined);

      setMode("camera");
      window.setTimeout(() => {
        grabFrame();
      }, 500);

      intervalRef.current = window.setInterval(() => {
        grabFrame();
      }, 4000);
    } catch (err: any) {
      if (err.name !== "NotAllowedError") {
        setError(err.message || "Failed to start camera");
      }
      stopCapture();
    }
  }, [grabFrame, stopCapture]);

  const observeScreen = useCallback(
    async (query?: string): Promise<VisionObservation> => {
      const frame = grabFrame() || latestFrame;
      if (!frame) {
        const fail = { ok: false, error: "NO_ACTIVE_FRAME" };
        setLastObservation(fail);
        return fail;
      }

      setIsObserving(true);
      try {
        const res = await fetch("/api/v1/vision/observe", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            frame,
            query: query || "What am I looking at right now? Give me key insights.",
            conversationId,
            companionId: "hinaa",
          }),
        });

        if (!res.ok) {
          // Fallback to /v1/vision/observe if /api/ prefix differs
          const fallbackRes = await fetch("/v1/vision/observe", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              frame,
              query: query || "What am I looking at right now?",
              conversationId,
            }),
          });
          const data = await fallbackRes.json();
          setLastObservation(data);
          return data;
        }

        const data = await res.json();
        setLastObservation(data);
        return data;
      } catch (err: any) {
        const fail = { ok: false, error: err.message || "OBSERVATION_FAILED" };
        setLastObservation(fail);
        return fail;
      } finally {
        setIsObserving(false);
      }
    },
    [conversationId, grabFrame, latestFrame],
  );

  useEffect(() => {
    return () => {
      stopCapture();
    };
  }, [stopCapture]);

  return {
    mode,
    isActive: mode !== "off",
    latestFrame,
    isObserving,
    lastObservation,
    error,
    startScreenShare,
    startCamera,
    stopCapture,
    observeScreen,
    grabFrame,
  };
}
