import { Suspense, lazy, useCallback, useState } from "react";
import { motion } from "framer-motion";
import {
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Maximize2,
  Minimize2,
  Keyboard,
  Camera,
  Activity,
} from "lucide-react";
import type { CompanionState, TranscriptMessage } from "../../features/companion/types";

const AvatarPresence = lazy(() =>
  import("../../components/ui/AvatarPresence").then((m) => ({
    default: m.AvatarPresence,
  }))
);

export type VisualMode = "vrm" | "orb" | "procedural_2d";

interface TalkModeProps {
  /** Real-time pipeline diagnostics */
  diagnostics?: any;
  /** Force commit any buffered audio */
  onManualCommit?: () => void;
  /** Show the diagnostics drawer */
  onToggleDiagnostics?: () => void;
  companionState: CompanionState;
  companionName: string;
  visualMode: VisualMode;
  onVisualModeChange: (mode: VisualMode) => void;
  isVoiceActive: boolean;
  isPaused: boolean;
  voiceDetail: string;
  microphoneLevel: number;
  onStartVoice: () => void;
  onStopVoice: () => void;
  onPauseVoice: () => void;
  onResumeVoice: () => void;
  partialTranscript: string;
  streamingText: string;
  avatarModel: string;
  avatarMode: any;
  jawEnergy: React.MutableRefObject<number>;
  speakingRef: React.MutableRefObject<boolean>;
  visemeEvents: React.MutableRefObject<any[]>;
  audioStartTimeRef: React.MutableRefObject<number>;
  faceExpressions: any;
  faceBones: any;
  faceTrackingActive: boolean;
  trackingCalibration: any;
  expressionText: string;
  avatarPresentation: any;
  messages: TranscriptMessage[];
  onOpenAvatarLab: () => void;
  onToggleFullscreen: () => void;
  onTypeInstead: () => void;
  isMuted: boolean;
  onToggleMute: () => void;
  onReplay: () => void;
  hasReplay: boolean;
}

const STATE_LABELS: Record<CompanionState, string> = {
  idle: "Ready",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking",
  interrupted: "Interrupted",
  error: "Error",
};

const STATE_COLORS: Record<CompanionState, string> = {
  idle: "var(--success)",
  listening: "var(--accent)",
  thinking: "var(--warning)",
  speaking: "var(--accent)",
  interrupted: "var(--danger)",
  error: "var(--danger)",
};

export function TalkMode({
  companionState,
  companionName,
  visualMode,
  onVisualModeChange,
  isVoiceActive,
  isPaused,
  voiceDetail,
  microphoneLevel,
  onStartVoice,
  onStopVoice,
  onPauseVoice,
  onResumeVoice,
  partialTranscript,
  streamingText,
  avatarModel,
  avatarMode,
  jawEnergy,
  speakingRef,
  visemeEvents,
  audioStartTimeRef,
  faceExpressions,
  faceBones,
  faceTrackingActive,
  trackingCalibration,
  expressionText,
  avatarPresentation,
  messages,
  onOpenAvatarLab,
  onToggleFullscreen,
  onTypeInstead,
  isMuted,
  onToggleMute,
  onReplay,
  hasReplay,
  diagnostics,
  onManualCommit,
  onToggleDiagnostics,
}: TalkModeProps) {
  const [showCaptions, setShowCaptions] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Get last assistant message for captions
  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  const captionText = streamingText || partialTranscript || lastAssistant?.text || "";

  // Get user's last message for live transcript
  const lastUser = [...messages].reverse().find((m) => m.role === "user");
  const userTranscript = partialTranscript || lastUser?.text || "";

  return (
    <div
      data-testid="talk-mode"
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        overflow: "hidden",
        background: "var(--bg-canvas)",
      }}
    >
      {/* ── Status Header ──────────────────────────── */}
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "0 var(--space-4)",
          borderBottom: "1px solid var(--border-subtle)",
          background: "var(--bg-surface)",
          flexShrink: 0,
          height: 40,
          gap: "var(--space-3)",
        }}
      >
        <StatusPill state={companionState} />
        <span style={{ fontSize: "var(--text-xs)", color: "var(--text-tertiary)" }}>
          {companionName}
        </span>
      </header>

      {/* ── Main: Avatar Stage fills available height ─ */}
      <div
        data-testid="hinaa-stage"
        style={{
          flex: 1,
          position: "relative",
          overflow: "hidden",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background:
            "radial-gradient(circle at 50% 30%, rgb(255 255 255 / 0.98) 0%, rgb(255 244 248 / 0.90) 38%, rgb(246 235 242 / 0.92) 100%)",
          borderRadius: "0",
          minHeight: 0,
        }}
      >
        {/* Soft Sakura illumination overlay */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            pointerEvents: "none",
            background:
              "radial-gradient(circle at 20% 20%, rgb(239 127 165 / 0.12), transparent 32%), radial-gradient(circle at 80% 72%, rgb(150 49 80 / 0.08), transparent 34%)",
            zIndex: 0,
          }}
        />

        {/* Grounding shadow */}
        <div
          style={{
            position: "absolute",
            left: "18%",
            right: "18%",
            bottom: "5%",
            height: "18%",
            pointerEvents: "none",
            background: "radial-gradient(ellipse, rgb(76 43 61 / 0.10), transparent 68%)",
            filter: "blur(22px)",
            zIndex: 0,
          }}
        />

        {/* Avatar container — fills the stage */}
        <div
          style={{
            width: "100%",
            height: "100%",
            position: "relative",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1,
          }}
        >
          {visualMode === "vrm" ? (
            <Suspense
              fallback={
                <div
                  style={{
                    display: "grid",
                    placeItems: "center",
                    color: "var(--text-tertiary)",
                    fontSize: "var(--text-sm)",
                  }}
                >
                  Loading avatar...
                </div>
              }
            >
              <AvatarPresence
                mode={avatarMode}
                state={companionState}
                jawEnergy={jawEnergy}
                speakingRef={speakingRef}
                visemeEvents={visemeEvents}
                audioStartTimeRef={audioStartTimeRef}
                modelUrl={avatarModel}
                faceExpressions={faceExpressions}
                faceBones={faceBones}
                faceTrackingActive={faceTrackingActive}
                trackingCalibration={trackingCalibration}
                expressionText={expressionText}
                presentation={avatarPresentation}
                companionName={companionName}
              />
            </Suspense>
          ) : (
            /* Orb fallback — audio reactive */
            <div
              style={{
                width: 160,
                height: 160,
                borderRadius: "50%",
                background: `radial-gradient(circle, var(--accent) 0%, var(--accent-soft) 60%, transparent 100%)`,
                opacity: companionState === "speaking" ? 1 : 0.7,
                transition: "opacity 300ms ease",
              }}
            />
          )}
        </div>

        {/* Live user transcript — small, above controls */}
        {isVoiceActive && userTranscript && (
          <div
            data-testid="user-transcript"
            style={{
              position: "absolute",
              bottom: 140,
              left: "50%",
              transform: "translateX(-50%)",
              maxWidth: "min(500px, 80%)",
              padding: "var(--space-2) var(--space-3)",
              background: "var(--bg-surface)",
              border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-lg)",
              boxShadow: "var(--shadow-sm)",
              color: "var(--text-secondary)",
              fontSize: "var(--text-xs)",
              textAlign: "center",
              zIndex: 5,
            }}
          >
            <span style={{ fontWeight: 600, color: "var(--text-tertiary)" }}>You: </span>
            {userTranscript}
          </div>
        )}

        {/* HINAA caption — below face, above controls */}
        {showCaptions && captionText && (
          <div
            data-testid="hinaa-caption"
            style={{
              position: "absolute",
              bottom: 80,
              left: "50%",
              transform: "translateX(-50%)",
              maxWidth: "min(640px, 85%)",
              padding: "var(--space-3) var(--space-4)",
              background: "var(--bg-surface)",
              border: "1px solid var(--border-default)",
              borderRadius: "var(--radius-xl)",
              boxShadow: "var(--shadow-md)",
              color: "var(--text-primary)",
              fontSize: "var(--text-sm)",
              lineHeight: "var(--leading-normal)",
              textAlign: "center",
              zIndex: 5,
            }}
          >
            <span
              style={{
                fontSize: "var(--text-xs)",
                fontWeight: 600,
                color: "var(--accent)",
                display: "block",
                marginBottom: "var(--space-1)",
              }}
            >
              HINAA
            </span>
            {captionText}
          </div>
        )}
      </div>

      {/* ── Voice Control Dock ──────────────────────── */}
      {isVoiceActive && diagnostics && (
        <div
          data-testid="voice-pipeline-quick"
          style={{
            position: "absolute",
            top: "var(--space-2)",
            right: "var(--space-2)",
            display: "flex",
            alignItems: "center",
            gap: "var(--space-1-5)",
            padding: "2px var(--space-2)",
            background: "var(--bg-surface)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-md)",
            boxShadow: "var(--shadow-sm)",
            zIndex: 10,
            cursor: "pointer",
          }}
          onClick={onToggleDiagnostics}
          title="Open voice diagnostics"
          role="button"
          aria-label="Open voice diagnostics"
        >
          <Activity size={12} style={{ color: diagnostics.currentStage?.includes("error") ? "var(--danger-text)" : "var(--accent)" }} />
          <span style={{ fontSize: 11, color: "var(--text-tertiary)", fontFamily: "monospace" }}>
            RMS {diagnostics.rmsLevel?.toFixed(3) ?? "0"} · {diagnostics.currentStage ?? "—"}
          </span>
          {diagnostics.lastError && (
            <span style={{ fontSize: 11, color: "var(--danger-text)", fontFamily: "monospace" }}>
              ⚠ {diagnostics.lastError}
            </span>
          )}
        </div>
      )}
      <div
        data-testid="voice-control-dock"
        style={{
          position: "absolute",
          bottom: "var(--space-4)",
          left: "50%",
          transform: "translateX(-50%)",
          display: "flex",
          alignItems: "center",
          gap: "var(--space-2)",
          padding: "var(--space-2) var(--space-3)",
          background: "var(--bg-surface)",
          border: "1px solid var(--border-default)",
          borderRadius: "var(--radius-2xl, 24px)",
          boxShadow: "var(--shadow-lg)",
          zIndex: 10,
        }}
      >
        {/* Mic toggle */}
        <DockButton
          onClick={isVoiceActive ? onStopVoice : onStartVoice}
          active={isVoiceActive}
          danger={isVoiceActive}
          title={isVoiceActive ? "Stop voice" : "Start voice"}
          ariaLabel={isVoiceActive ? "Stop voice" : "Start voice"}
        >
          {isVoiceActive ? <MicOff size={18} /> : <Mic size={18} />}
        </DockButton>

        {/* Mute */}
        <DockButton
          onClick={onToggleMute}
          active={!isMuted}
          title={isMuted ? "Unmute" : "Mute"}
          ariaLabel={isMuted ? "Unmute" : "Mute"}
        >
          {isMuted ? <VolumeX size={18} /> : <Volume2 size={18} />}
        </DockButton>

        {/* Keyboard input */}
        <DockButton
          onClick={onTypeInstead}
          title="Type instead"
          ariaLabel="Type instead"
        >
          <Keyboard size={18} />
        </DockButton>

        {/* Manual commit (when listening but stuck) */}
        {isVoiceActive && onManualCommit && (
          <DockButton
            onClick={onManualCommit}
            title="Manual commit — force transcribe what you said"
            ariaLabel="Manual commit"
          >
            <span style={{ fontSize: 14 }}>⏎</span>
          </DockButton>
        )}

        {/* Diagnostics toggle */}
        {isVoiceActive && onToggleDiagnostics && (
          <DockButton
            onClick={onToggleDiagnostics}
            title="Voice diagnostics"
            ariaLabel="Voice diagnostics"
          >
            <Activity size={18} />
          </DockButton>
        )}

        {/* Fullscreen */}
        <DockButton
          onClick={() => {
            setIsFullscreen(!isFullscreen);
            onToggleFullscreen();
          }}
          title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
          ariaLabel={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
        >
          {isFullscreen ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
        </DockButton>

        {/* Divider */}
        <div
          style={{
            width: 1,
            height: 20,
            background: "var(--border-default)",
            margin: "0 var(--space-1)",
          }}
        />

        {/* Visual mode selector */}
        {(["vrm", "orb"] as const).map((mode) => (
          <button
            key={mode}
            onClick={() => onVisualModeChange(mode)}
            title={mode === "vrm" ? "3D Avatar" : "Orb"}
            aria-label={mode === "vrm" ? "3D Avatar" : "Orb"}
            aria-pressed={visualMode === mode}
            style={{
              width: 32,
              height: 32,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: "var(--radius-md)",
              border:
                visualMode === mode
                  ? "1px solid var(--accent)"
                  : "1px solid transparent",
              background: visualMode === mode ? "var(--accent-pale)" : "transparent",
              color: visualMode === mode ? "var(--accent)" : "var(--text-tertiary)",
              cursor: "pointer",
              fontSize: "var(--text-xs)",
              fontWeight: 600,
            }}
          >
            {mode === "vrm" ? "3D" : "○"}
          </button>
        ))}
      </div>
    </div>
  );
}

/* ── Dock Button ─────────────────────────────────────────── */
function DockButton({
  children,
  onClick,
  active,
  danger,
  title,
  ariaLabel,
}: {
  children: React.ReactNode;
  onClick: () => void;
  active?: boolean;
  danger?: boolean;
  title: string;
  ariaLabel: string;
}) {
  return (
    <button
      onClick={onClick}
      title={title}
      aria-label={ariaLabel}
      style={{
        width: 40,
        height: 40,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        borderRadius: "var(--radius-lg)",
        border: "none",
        background: danger
          ? "var(--danger-bg)"
          : active
            ? "var(--accent-pale)"
            : "transparent",
        color: danger
          ? "var(--danger-text)"
          : active
            ? "var(--accent)"
            : "var(--text-secondary)",
        cursor: "pointer",
        transition: "background 150ms ease, color 150ms ease",
      }}
    >
      {children}
    </button>
  );
}

/* ── Status Pill ─────────────────────────────────────────── */
function StatusPill({ state }: { state: CompanionState }) {
  const label = STATE_LABELS[state] || state;
  const color = STATE_COLORS[state] || "var(--text-tertiary)";

  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "var(--space-1-5)",
        padding: "2px var(--space-2)",
        borderRadius: "var(--radius-pill)",
        background: `${color}12`,
        border: `1px solid ${color}30`,
      }}
    >
      <div
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: color,
        }}
      />
      <span
        style={{
          fontSize: "var(--text-xs)",
          fontWeight: 600,
          color: color,
        }}
      >
        {label}
      </span>
    </div>
  );
}
