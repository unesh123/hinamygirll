import { useCallback, useRef, useState, type FormEvent, type MutableRefObject, type PointerEvent } from "react";
import { Brain, Camera, LayoutPanelLeft, Mic, MicOff, SendHorizontal } from "lucide-react";
import { Badge, GlowOrb, ParticleField } from "../hud";
import { LazyAvatarPresence as AvatarPresence } from "../../features/avatar/LazyAvatarPresence";
import type { AvatarPresentation } from "../../features/avatar/avatarPresentation";
import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";
import type { CompanionState, TranscriptMessage } from "../../features/companion/types";
import type { VisemeEvent } from "../../features/audio/textToViseme";
import "./companionStage.css";

export interface CompanionStageProps {
  backgroundBuild?: {
    runId: string;
    goal: string;
    status: string;
    phase?: string;
    headline?: string;
    filesChanged?: string[];
    previewUrls?: string[];
  } | null;
  onCancelBackgroundBuild?: () => void;
  avatarModel?: string;
  avatarPresentation?: AvatarPresentation;
  companionName?: string;
  companionState: CompanionState;
  plan?: AssistantTurnPlan;
  messages: TranscriptMessage[];
  streamingText?: string;
  partialTranscript?: string;
  jawEnergy?: MutableRefObject<number>;
  speakingRef?: MutableRefObject<boolean>;
  visemeEvents?: MutableRefObject<VisemeEvent[]>;
  audioStartTimeRef?: MutableRefObject<number>;
  isVoiceActive: boolean;
  microphoneLevel?: number;
  visionEnabled: boolean;
  onStartVoice: () => void;
  onStopVoice: () => void;
  onToggleVision: () => void;
  onOpenMemory: () => void;
  onOpenWorkspace: () => void;
  onSendText: (text: string) => void;
}

const STATE_LABEL: Record<string, string> = {
  idle: "Here with you",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking",
  interrupted: "Listening",
  error: "Something went wrong",
};

const orbState = (s: string) => (s === "listening" || s === "thinking" || s === "speaking" ? s : "idle");

/** Strip markdown noise so subtitles read as speech. */
function plain(text: string): string {
  return text.replace(/```[\s\S]*?```/g, " ").replace(/[*_`#>]+/g, "").replace(/\s+/g, " ").trim();
}

function tail(text: string, max = 280): string {
  return text.length > max ? `…${text.slice(-max).replace(/^\S*\s/, "")}` : text;
}

/** Calm, avatar-first companion view: cinematic backdrop, subtitles, floating composer. */
export function CompanionStage({
  backgroundBuild, onCancelBackgroundBuild,
  avatarModel, avatarPresentation, companionName = "Hina", companionState, plan, messages,
  streamingText, partialTranscript, jawEnergy, speakingRef, visemeEvents, audioStartTimeRef,
  isVoiceActive, microphoneLevel = 0, visionEnabled,
  onStartVoice, onStopVoice, onToggleVision, onOpenMemory, onOpenWorkspace, onSendText,
}: CompanionStageProps) {
  const [draft, setDraft] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);
  const frame = useRef(0);

  const latestReply = [...messages].reverse().find((m) => m.role === "assistant");
  const replyText = plain(streamingText || latestReply?.text || plan?.displayText || "");
  const heard = plain(partialTranscript || "");
  const mood = plan?.emotion?.primary ?? (companionState === "thinking" ? "thinking" : "calm");
  const stateLabel = STATE_LABEL[companionState] ?? STATE_LABEL.idle;
  const toggleVoice = isVoiceActive ? onStopVoice : onStartVoice;

  const onPointerMove = useCallback((e: PointerEvent<HTMLDivElement>) => {
    const el = rootRef.current;
    if (!el || window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches) return;
    const { clientX, clientY } = e;
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => {
      const r = el.getBoundingClientRect();
      el.style.setProperty("--px", String((clientX - r.left) / r.width - 0.5));
      el.style.setProperty("--py", String((clientY - r.top) / r.height - 0.5));
    });
  }, []);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const text = draft.trim();
    if (!text) return;
    onSendText(text);
    setDraft("");
  };

  return (
    <div ref={rootRef} className="companion-stage" data-testid="companion-stage" data-state={companionState} onPointerMove={onPointerMove}>
      <div className="companion-stage__backdrop" aria-hidden="true">
        <div className="companion-stage__sky" />
        <div className="companion-stage__layer companion-stage__layer--far">
          <span className="cs-bokeh cs-bokeh--a" />
          <span className="cs-bokeh cs-bokeh--b" />
          <span className="cs-bokeh cs-bokeh--c" />
        </div>
        <div className="companion-stage__particles"><ParticleField count={40} /></div>
        <div className="companion-stage__floor" />
      </div>

      <div className="companion-stage__avatar">
        <AvatarPresence
          mode="upperbody"
          state={companionState}
          liveStatus={{ active: isVoiceActive, paused: false, detail: isVoiceActive ? "listening" : "", status: companionState === "speaking" ? "idle" : "listening", microphoneLevel }}
          jawEnergy={jawEnergy}
          speakingRef={speakingRef}
          visemeEvents={visemeEvents}
          audioStartTimeRef={audioStartTimeRef}
          modelUrl={avatarModel}
          presentation={avatarPresentation}
          companionName={companionName}
          expressionText={companionState === "speaking" ? replyText || undefined : undefined}
          plan={plan}
        />
      </div>

      <div className="companion-stage__layer companion-stage__layer--near" aria-hidden="true">
        <span className="cs-bokeh cs-bokeh--d" />
        <span className="cs-bokeh cs-bokeh--e" />
      </div>
      <div className="companion-stage__vignette" aria-hidden="true" />

      <header className="companion-stage__top">
        <div className="cs-identity">
          <GlowOrb size={48} level={isVoiceActive ? microphoneLevel : companionState === "speaking" ? 0.5 : 0} state={orbState(companionState)} label={`Core: ${stateLabel}`} />
          <div className="cs-identity__text">
            <span className="cs-identity__name">{companionName}</span>
            <span className="cs-identity__state" role="status">{stateLabel}</span>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          {backgroundBuild && (
            <div
              data-testid="companion-build-pill"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                padding: "5px 10px",
                borderRadius: 999,
                background: "rgba(15, 23, 42, 0.78)",
                border: "1px solid rgba(56, 189, 248, 0.4)",
                color: "#e2e8f0",
                fontSize: 11.5,
                fontWeight: 600,
              }}
            >
              <span>
                {backgroundBuild.status === "running"
                  ? `Building${backgroundBuild.phase ? ` (${backgroundBuild.phase})` : ""}`
                  : backgroundBuild.status === "awaiting_approval"
                    ? "Build Approval Needed"
                    : `Build ${backgroundBuild.status}`}
                {backgroundBuild.filesChanged && backgroundBuild.filesChanged.length > 0
                  ? ` · ${backgroundBuild.filesChanged.length} files`
                  : ""}
              </span>
              <button
                type="button"
                onClick={onOpenWorkspace}
                style={{
                  background: "rgba(56, 189, 248, 0.2)",
                  border: "none",
                  borderRadius: 6,
                  padding: "2px 7px",
                  color: "#7dd3fc",
                  fontSize: 11,
                  fontWeight: 700,
                  cursor: "pointer",
                }}
              >
                Workspace
              </button>
              {onCancelBackgroundBuild &&
                (backgroundBuild.status === "running" || backgroundBuild.status === "awaiting_approval") && (
                  <button
                    type="button"
                    onClick={onCancelBackgroundBuild}
                    style={{
                      background: "rgba(239, 68, 68, 0.22)",
                      border: "none",
                      borderRadius: 6,
                      padding: "2px 7px",
                      color: "#fca5a5",
                      fontSize: 11,
                      fontWeight: 700,
                      cursor: "pointer",
                    }}
                  >
                    Stop
                  </button>
                )}
            </div>
          )}
          <Badge tone="accent" dot data-testid="companion-mood">Mood · {mood}</Badge>
        </div>
      </header>

      <section className="companion-stage__bottom">
        {(heard || replyText) && (
          <div className="cs-subtitle" data-testid="companion-subtitle" aria-live="polite">
            {heard && <p className="cs-subtitle__heard">You: {tail(heard, 160)}</p>}
            {replyText && <p className="cs-subtitle__reply">{tail(replyText)}</p>}
          </div>
        )}

        <div className="cs-chips" role="toolbar" aria-label="Quick actions">
          <button type="button" className="cs-chip" aria-pressed={isVoiceActive} onClick={toggleVoice}>
            {isVoiceActive ? <MicOff size={15} aria-hidden="true" /> : <Mic size={15} aria-hidden="true" />}
            {isVoiceActive ? "Stop talking" : "Talk"}
          </button>
          <button type="button" className="cs-chip" aria-pressed={visionEnabled} onClick={onToggleVision}>
            <Camera size={15} aria-hidden="true" />
            Camera awareness
          </button>
          <button type="button" className="cs-chip" onClick={onOpenMemory}>
            <Brain size={15} aria-hidden="true" />
            Memory
          </button>
          <button type="button" className="cs-chip" onClick={onOpenWorkspace}>
            <LayoutPanelLeft size={15} aria-hidden="true" />
            Workspace
          </button>
        </div>

        <form className="cs-composer" onSubmit={submit}>
          <input
            className="cs-composer__input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={`Say something to ${companionName}…`}
            aria-label={`Message ${companionName}`}
            autoComplete="off"
          />
          <button type="button" className="cs-composer__btn" aria-label={isVoiceActive ? "Stop voice" : "Start voice"} aria-pressed={isVoiceActive} onClick={toggleVoice}>
            {isVoiceActive ? <MicOff size={18} aria-hidden="true" /> : <Mic size={18} aria-hidden="true" />}
          </button>
          <button type="submit" className="cs-composer__btn cs-composer__btn--send" aria-label="Send message" disabled={!draft.trim()}>
            <SendHorizontal size={18} aria-hidden="true" />
          </button>
        </form>
      </section>
    </div>
  );
}
