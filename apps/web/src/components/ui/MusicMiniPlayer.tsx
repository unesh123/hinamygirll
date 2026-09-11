import React, { useState, useEffect } from "react";
import {
  Play,
  Pause,
  Square,
  Volume2,
  VolumeX,
  Music,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Radio,
} from "lucide-react";

export interface MusicTrack {
  id: string;
  title: string;
  artist?: string;
  source: string;
  url?: string;
}

interface MusicMiniPlayerProps {
  initialTrack?: MusicTrack | null;
  isOpen?: boolean;
  onClose?: () => void;
}

const DEFAULT_TRACK: MusicTrack = {
  id: "lofi-stream-1",
  title: "Sakura Rain & Study Lo-Fi",
  artist: "HINAA Companion Radio",
  source: "External Source: YouTube / Web Audio Stream",
  url: "https://www.youtube.com",
};

export function MusicMiniPlayer({
  initialTrack,
  isOpen = true,
  onClose,
}: MusicMiniPlayerProps) {
  const [track, setTrack] = useState<MusicTrack>(initialTrack || DEFAULT_TRACK);
  const [isPlaying, setIsPlaying] = useState(false);
  const [volume, setVolume] = useState(0.7);
  const [isMuted, setIsMuted] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);

  // Sync initialTrack if changed
  useEffect(() => {
    if (initialTrack) {
      setTrack(initialTrack);
      setIsPlaying(true);
    }
  }, [initialTrack]);

  // Synthetic or WebAudio timer when playing
  useEffect(() => {
    let timer: any;
    if (isPlaying) {
      timer = setInterval(() => {
        setCurrentTime((t) => t + 1);
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [isPlaying]);

  const handlePlayToggle = () => {
    setIsPlaying((prev) => !prev);
  };

  const handleStop = () => {
    setIsPlaying(false);
    setCurrentTime(0);
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? "0" : ""}${secs}`;
  };

  if (!isOpen) return null;

  return (
    <div
      data-testid="music-mini-player"
      style={{
        position: "fixed",
        bottom: "84px",
        right: "24px",
        zIndex: 9990,
        backgroundColor: "rgba(18, 18, 24, 0.88)",
        backdropFilter: "blur(16px)",
        WebkitBackdropFilter: "blur(16px)",
        border: "1px solid rgba(255, 255, 255, 0.12)",
        borderRadius: "16px",
        boxShadow: "0 12px 32px rgba(0, 0, 0, 0.45)",
        color: "#ffffff",
        fontFamily: "system-ui, -apple-system, sans-serif",
        width: isMinimized ? "260px" : "340px",
        transition: "all 0.25s cubic-bezier(0.16, 1, 0.3, 1)",
        overflow: "hidden",
      }}
    >
      {/* Top Header Bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 14px",
          borderBottom: isMinimized ? "none" : "1px solid rgba(255, 255, 255, 0.08)",
          background: isPlaying
            ? "linear-gradient(90deg, rgba(236, 72, 153, 0.15), rgba(99, 102, 241, 0.15))"
            : "transparent",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: 0 }}>
          <div
            style={{
              width: "28px",
              height: "28px",
              borderRadius: "8px",
              backgroundColor: isPlaying ? "#ec4899" : "rgba(255, 255, 255, 0.1)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#fff",
              flexShrink: 0,
            }}
          >
            {isPlaying ? (
              <Radio size={15} style={{ animation: "pulse 1.5s infinite" }} />
            ) : (
              <Music size={15} />
            )}
          </div>
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                fontSize: "13px",
                fontWeight: 600,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              {track.title}
            </div>
            {track.artist && !isMinimized && (
              <div
                style={{
                  fontSize: "11px",
                  color: "rgba(255, 255, 255, 0.6)",
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
              >
                {track.artist}
              </div>
            )}
          </div>
        </div>

        {/* Controls: Minimize & Close */}
        <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
          <button
            onClick={() => setIsMinimized((v) => !v)}
            title={isMinimized ? "Expand Player" : "Minimize Player"}
            style={{
              background: "transparent",
              border: "none",
              color: "rgba(255, 255, 255, 0.7)",
              cursor: "pointer",
              padding: "4px",
              borderRadius: "6px",
              display: "flex",
              alignItems: "center",
            }}
          >
            {isMinimized ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
          {onClose && (
            <button
              onClick={onClose}
              title="Close Player"
              style={{
                background: "transparent",
                border: "none",
                color: "rgba(255, 255, 255, 0.7)",
                cursor: "pointer",
                padding: "4px",
                borderRadius: "6px",
                fontSize: "14px",
                lineHeight: 1,
              }}
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Expanded Controls & Attribution */}
      {!isMinimized && (
        <div style={{ padding: "12px 14px" }}>
          {/* External Source Attribution Badge */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              fontSize: "10px",
              color: "rgba(255, 255, 255, 0.5)",
              marginBottom: "12px",
              padding: "4px 8px",
              borderRadius: "6px",
              backgroundColor: "rgba(255, 255, 255, 0.04)",
              border: "1px solid rgba(255, 255, 255, 0.06)",
            }}
          >
            <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
              <span
                style={{
                  width: "6px",
                  height: "6px",
                  borderRadius: "50%",
                  backgroundColor: isPlaying ? "#10b981" : "#6b7280",
                }}
              />
              {track.source}
            </span>
            {track.url && (
              <a
                href={track.url}
                target="_blank"
                rel="noopener noreferrer"
                title="Open Source"
                style={{ color: "#ec4899", display: "flex", alignItems: "center" }}
              >
                <ExternalLink size={11} />
              </a>
            )}
          </div>

          {/* Player Controls Bar */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "8px",
            }}
          >
            {/* Play / Pause / Stop Buttons */}
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <button
                onClick={handlePlayToggle}
                style={{
                  width: "36px",
                  height: "36px",
                  borderRadius: "50%",
                  backgroundColor: isPlaying ? "#ec4899" : "#3b82f6",
                  border: "none",
                  color: "#fff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                  boxShadow: "0 4px 12px rgba(236, 72, 153, 0.3)",
                  transition: "transform 0.1s",
                }}
                title={isPlaying ? "Pause" : "Play"}
              >
                {isPlaying ? <Pause size={17} /> : <Play size={17} style={{ marginLeft: "2px" }} />}
              </button>

              <button
                onClick={handleStop}
                style={{
                  width: "32px",
                  height: "32px",
                  borderRadius: "50%",
                  backgroundColor: "rgba(255, 255, 255, 0.1)",
                  border: "none",
                  color: "rgba(255, 255, 255, 0.8)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  cursor: "pointer",
                }}
                title="Stop"
              >
                <Square size={14} />
              </button>

              <span
                style={{
                  fontSize: "11px",
                  color: "rgba(255, 255, 255, 0.6)",
                  fontVariantNumeric: "tabular-nums",
                }}
              >
                {formatTime(currentTime)}
              </span>
            </div>

            {/* Volume Control */}
            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              <button
                onClick={() => setIsMuted((v) => !v)}
                style={{
                  background: "transparent",
                  border: "none",
                  color: isMuted ? "#ef4444" : "rgba(255, 255, 255, 0.7)",
                  cursor: "pointer",
                  padding: "4px",
                }}
                title={isMuted ? "Unmute" : "Mute"}
              >
                {isMuted ? <VolumeX size={15} /> : <Volume2 size={15} />}
              </button>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={isMuted ? 0 : volume}
                onChange={(e) => {
                  setVolume(parseFloat(e.target.value));
                  if (isMuted) setIsMuted(false);
                }}
                style={{
                  width: "60px",
                  accentColor: "#ec4899",
                  cursor: "pointer",
                }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
