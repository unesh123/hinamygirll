import { useEffect } from "react";

export interface MediaSessionOptions {
  title?: string;
  companionName?: string;
  isPlaying?: boolean;
  isListening?: boolean;
  onPlay?: () => void;
  onPause?: () => void;
  onStop?: () => void;
}

export function useMediaSession({
  title = "HINAA Companion",
  companionName = "HINAA",
  isPlaying = false,
  isListening = false,
  onPlay,
  onPause,
  onStop,
}: MediaSessionOptions) {
  useEffect(() => {
    if (typeof window === "undefined" || !("mediaSession" in navigator)) {
      return;
    }

    try {
      const stateDescription = isPlaying
        ? "Speaking..."
        : isListening
        ? "Listening..."
        : "Ready";

      if (typeof MediaMetadata !== "undefined") {
        navigator.mediaSession.metadata = new MediaMetadata({
          title,
          artist: companionName,
          album: `Sakura OS · ${stateDescription}`,
          artwork: [
            { src: "/favicon.ico", sizes: "64x64", type: "image/x-icon" },
          ],
        });
      }

      navigator.mediaSession.playbackState = isPlaying
        ? "playing"
        : isListening
        ? "paused"
        : "none";

      const setHandler = (action: MediaSessionAction, handler?: () => void) => {
        try {
          if (handler) {
            navigator.mediaSession.setActionHandler(action, handler);
          } else {
            navigator.mediaSession.setActionHandler(action, null);
          }
        } catch {
          // Action may not be supported by the current user agent
        }
      };

      setHandler("play", onPlay);
      setHandler("pause", onPause);
      setHandler("stop", onStop);
    } catch {
      // MediaSession initialization safety guard
    }

    return () => {
      if (typeof window !== "undefined" && "mediaSession" in navigator) {
        try {
          navigator.mediaSession.setActionHandler("play", null);
          navigator.mediaSession.setActionHandler("pause", null);
          navigator.mediaSession.setActionHandler("stop", null);
        } catch {}
      }
    };
  }, [title, companionName, isPlaying, isListening, onPlay, onPause, onStop]);
}
