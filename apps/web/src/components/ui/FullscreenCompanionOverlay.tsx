import { AnimatePresence, motion } from "framer-motion";
import { Mic, MicOff, Pause, Play, Radio, Sparkles, Square, Volume2 } from "lucide-react";
import type { TranscriptMessage } from "../../features/companion/types";
import type { CompanionState } from "../../features/companion/types";

export type FullscreenLiveStatus = {
  active: boolean;
  paused: boolean;
  detail: string;
  microphoneLevel: number;
};

interface FullscreenCompanionOverlayProps {
  open: boolean;
  companionName: string;
  companionState: CompanionState;
  live: FullscreenLiveStatus;
  messages: TranscriptMessage[];
  partialTranscript?: string;
  streamingText?: string;
  trackingActive?: boolean;
  onStartLive: () => void;
  onStopLive: () => void;
  onPauseLive: () => void;
  onResumeLive: () => void;
}

const stateCopy: Record<CompanionState, string> = {
  idle: "Ready when you are",
  listening: "Listening carefully",
  thinking: "Thinking through your request",
  speaking: "Speaking with you",
  interrupted: "Interrupted — ready again",
  error: "Connection needs attention",
};

function clipped(text: string, max = 240) {
  const clean = text.replace(/\s+/g, " ").trim();
  return clean.length > max ? `${clean.slice(0, max).trimEnd()}…` : clean;
}

function messageLabel(message: TranscriptMessage) {
  return message.role === "assistant" ? "HINAA" : "You";
}

export function FullscreenCompanionOverlay({
  open,
  companionName,
  companionState,
  live,
  messages,
  partialTranscript,
  streamingText,
  trackingActive = false,
  onStartLive,
  onStopLive,
  onPauseLive,
  onResumeLive,
}: FullscreenCompanionOverlayProps) {
  if (!open) return null;

  const recentMessages = messages.slice(-3);
  const liveLabel = live.active
    ? live.paused
      ? "Live conversation paused"
      : stateCopy[companionState]
    : "Press the microphone to begin live voice";
  const level = Math.max(0, Math.min(1, live.microphoneLevel || 0));

  return (
    <section className="fullscreen-companion-overlay" aria-label={`${companionName} live companion`}>
      <header className="fullscreen-companion-overlay__header">
        <div className="fullscreen-companion-overlay__identity">
          <span className="fullscreen-companion-overlay__mark" aria-hidden="true"><Sparkles size={15} /></span>
          <div>
            <p>{companionName}</p>
            <span>Live companion</span>
          </div>
        </div>
        <div className="fullscreen-companion-overlay__signals" aria-live="polite">
          <span className={`fullscreen-companion-overlay__signal${live.active && !live.paused ? " is-live" : ""}`}>
            <Radio size={12} aria-hidden="true" />
            {live.active && !live.paused ? "LIVE" : live.paused ? "PAUSED" : "VOICE READY"}
          </span>
          <span className={`fullscreen-companion-overlay__signal${trackingActive ? " is-tracking" : ""}`}>
            {trackingActive ? "VMC TRACKING" : "AUTONOMOUS PRESENCE"}
          </span>
        </div>
      </header>

      <aside className="fullscreen-companion-overlay__conversation" aria-live="polite" aria-label="Recent conversation">
        <AnimatePresence initial={false}>
          {recentMessages.map((message, index) => (
            <motion.article
              key={message.id}
              className={`fullscreen-turn fullscreen-turn--${message.role}`}
              initial={{ opacity: 0, x: -14, y: 8 }}
              animate={{ opacity: 1, x: 0, y: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ duration: 0.22, delay: index * 0.035, ease: [0.23, 1, 0.32, 1] }}
            >
              <span>{messageLabel(message)}</span>
              <p>{clipped(message.text)}</p>
            </motion.article>
          ))}
          {partialTranscript && (
            <motion.article
              key="live-partial-transcript"
              className="fullscreen-turn fullscreen-turn--partial"
              initial={{ opacity: 0, x: -14, y: 8 }}
              animate={{ opacity: 1, x: 0, y: 0 }}
              transition={{ duration: 0.18, ease: [0.23, 1, 0.32, 1] }}
            >
              <span><Mic size={12} aria-hidden="true" /> You are speaking</span>
              <p>{clipped(partialTranscript)}</p>
            </motion.article>
          )}
          {streamingText && (
            <motion.article
              key="live-streaming-response"
              className="fullscreen-turn fullscreen-turn--assistant fullscreen-turn--streaming"
              initial={{ opacity: 0, x: -14, y: 8 }}
              animate={{ opacity: 1, x: 0, y: 0 }}
              transition={{ duration: 0.18, ease: [0.23, 1, 0.32, 1] }}
            >
              <span><Volume2 size={12} aria-hidden="true" /> {companionName} is replying</span>
              <p>{clipped(streamingText)}</p>
            </motion.article>
          )}
        </AnimatePresence>
      </aside>

      <div className="fullscreen-companion-overlay__voice-dock">
        <p className="fullscreen-companion-overlay__status">{liveLabel}</p>
        <p className="fullscreen-companion-overlay__detail">{live.detail || "Microphone permission is requested only when you start."}</p>
        <div className="fullscreen-companion-overlay__meter" aria-hidden="true">
          {Array.from({ length: 9 }, (_, index) => {
            const threshold = (index + 1) / 9;
            const active = live.active && !live.paused && level >= threshold * 0.55;
            return <span key={index} className={active ? "is-active" : ""} style={{ height: `${8 + (index % 4) * 5}px` }} />;
          })}
        </div>
        <div className="fullscreen-companion-overlay__actions">
          {live.active && (
            <button
              type="button"
              className="fullscreen-companion-overlay__minor-action"
              onClick={live.paused ? onResumeLive : onPauseLive}
              aria-label={live.paused ? "Resume live conversation" : "Pause live conversation"}
              title={live.paused ? "Resume live conversation" : "Pause live conversation"}
            >
              {live.paused ? <Play size={15} fill="currentColor" aria-hidden="true" /> : <Pause size={15} fill="currentColor" aria-hidden="true" />}
            </button>
          )}
          <motion.button
            type="button"
            className={`fullscreen-companion-overlay__mic${live.active ? " is-active" : ""}${live.paused ? " is-paused" : ""}`}
            onClick={live.active ? onStopLive : onStartLive}
            aria-label={live.active ? "Stop live conversation" : "Start live conversation"}
            title={live.active ? "Stop live conversation" : "Start live conversation"}
            whileTap={{ scale: 0.96 }}
          >
            <span className="fullscreen-companion-overlay__mic-ring" style={{ transform: `scale(${1 + level * 0.18})` }} />
            {live.active ? <Square size={17} fill="currentColor" aria-hidden="true" /> : <Mic size={20} aria-hidden="true" />}
          </motion.button>
          {live.active && (
            <span className="fullscreen-companion-overlay__stop-label"><MicOff size={12} aria-hidden="true" /> Stop</span>
          )}
        </div>
        <p className="fullscreen-companion-overlay__hint">{live.active ? "Tap stop anytime. Your regular chat stays available when you exit." : "Start voice when ready. Text replies and live transcripts appear here."}</p>
      </div>
    </section>
  );
}

export default FullscreenCompanionOverlay;
