import { useMemo, useState, type FormEvent } from "react";
import "./App.css";
import { ProceduralAvatar } from "./features/avatar/ProceduralAvatar";
import { detectWebGL } from "./features/avatar/webgl";
import {
  companionProfiles,
  type CompanionId,
  type CompanionState,
} from "./features/companion/types";
import { useCompanionController } from "./features/companion/useCompanionController";
import { useReducedMotionPreference } from "./shared/useReducedMotion";

const stateCopy: Record<CompanionState, { label: string; detail: string }> = {
  idle: { label: "Ready", detail: "Mock mode is waiting" },
  listening: { label: "Listening", detail: "Simulated microphone input" },
  thinking: { label: "Thinking", detail: "Building a local response" },
  speaking: { label: "Speaking", detail: "Playing a simulated performance" },
  interrupted: { label: "Interrupted", detail: "The active turn was stopped" },
  error: { label: "Error", detail: "Mock fallback is still available" },
};

function Icon({ name }: { name: "mic" | "stop" | "send" | "text" | "motion" }) {
  const paths = {
    mic: (
      <path d="M12 3a3 3 0 0 0-3 3v5a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3Zm-6 8a6 6 0 0 0 12 0M12 17v4m-3 0h6" />
    ),
    stop: (
      <>
        <rect x="6" y="6" width="12" height="12" rx="2" />
      </>
    ),
    send: <path d="m4 4 16 8-16 8 3-8-3-8Zm3 8h13" />,
    text: (
      <>
        <path d="M4 6h16M8 6v12m8-12v12M6 18h4m4 0h4" />
      </>
    ),
    motion: <path d="M4 12h3l2-5 4 10 2-5h5" />,
  };
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

function CompanionSwitch({
  value,
  onChange,
}: {
  value: CompanionId;
  onChange: (id: CompanionId) => void;
}) {
  return (
    <div
      className="companion-switch"
      role="group"
      aria-label="Choose companion"
    >
      {(Object.keys(companionProfiles) as CompanionId[]).map((id) => (
        <button
          type="button"
          className={value === id ? "selected" : ""}
          aria-pressed={value === id}
          onClick={() => onChange(id)}
          key={id}
        >
          <span>{companionProfiles[id].name}</span>
          <small>{companionProfiles[id].label}</small>
        </button>
      ))}
    </div>
  );
}

export default function App() {
  const controller = useCompanionController();
  const systemReducedMotion = useReducedMotionPreference();
  const [reduceMotionOverride, setReduceMotionOverride] = useState(false);
  const [textOnly, setTextOnly] = useState(false);
  const [input, setInput] = useState("");
  const webglAvailable = useMemo(() => detectWebGL(), []);
  const reducedMotion = systemReducedMotion || reduceMotionOverride;
  const active = ["listening", "thinking", "speaking"].includes(
    controller.state,
  );
  const status = stateCopy[controller.state];

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = input.trim();
    if (!value) return;
    setInput("");
    void controller.sendText(value);
  };

  return (
    <main className={`app-shell companion-${controller.companionId}`}>
      <section
        className="companion-panel"
        aria-label="HINAA companion playground"
      >
        <header className="topbar">
          <div className="brand-lockup">
            <span className="brand-mark" aria-hidden="true">
              H
            </span>
            <div>
              <strong>HINAA</strong>
              <small>Phase 1 playground</small>
            </div>
          </div>
          <div
            className="provider-chip"
            title="No network provider is connected"
          >
            <span className="status-dot" /> Local mock
          </div>
        </header>

        <div className="status-line" role="status" aria-live="polite">
          <span className={`state-indicator state-${controller.state}`} />
          <strong>{status.label}</strong>
          <span>{status.detail}</span>
        </div>

        {!webglAvailable && !textOnly && (
          <div className="notice" role="note">
            WebGL is unavailable. The safe procedural placeholder is active;
            chat is unaffected.
          </div>
        )}

        <div className="stage-wrap">
          <ProceduralAvatar
            companionId={controller.companionId}
            state={controller.state}
            plan={controller.activePlan}
            reducedMotion={reducedMotion}
            textOnly={textOnly}
          />
          {!textOnly && (
            <div className="performance-caption">
              <span>{controller.activePlan?.emotion.primary ?? "neutral"}</span>
              <span>
                {controller.activePlan?.performance.gesture.replaceAll(
                  "_",
                  " ",
                ) ?? "base life"}
              </span>
            </div>
          )}
        </div>

        <CompanionSwitch
          value={controller.companionId}
          onChange={controller.setCompanionId}
        />

        <div className="accessibility-bar" aria-label="Accessibility controls">
          <button
            type="button"
            aria-pressed={textOnly}
            onClick={() => setTextOnly((value) => !value)}
          >
            <Icon name="text" /> {textOnly ? "Show avatar" : "Text only"}
          </button>
          <button
            type="button"
            aria-pressed={reducedMotion}
            onClick={() => setReduceMotionOverride((value) => !value)}
            disabled={systemReducedMotion}
            title={
              systemReducedMotion
                ? "Your device already requests reduced motion"
                : undefined
            }
          >
            <Icon name="motion" /> Reduced motion {reducedMotion ? "on" : "off"}
          </button>
        </div>

        <div className="primary-controls">
          {active ? (
            <button
              className="stop-button"
              type="button"
              onClick={controller.stop}
              aria-label="Stop current mock turn"
            >
              <Icon name="stop" /> Stop
            </button>
          ) : (
            <span className="control-spacer" />
          )}
          <button
            className="mic-button"
            type="button"
            onClick={controller.startMockListening}
            aria-label="Simulate microphone listening"
            title="No microphone permission is requested in mock mode"
          >
            <Icon name="mic" />
            <span>Try voice</span>
          </button>
          <button
            className="camera-button"
            type="button"
            disabled
            title="Camera is outside Phase 1"
          >
            Camera off
          </button>
        </div>
      </section>

      <section className="chat-panel" aria-label="Conversation transcript">
        <header className="chat-header">
          <div>
            <small>Conversation with</small>
            <strong>{companionProfiles[controller.companionId].name}</strong>
          </div>
          <span>Saved nowhere</span>
        </header>
        <div
          className="transcript"
          data-testid="transcript"
          aria-live="polite"
          aria-relevant="additions text"
        >
          {controller.messages.map((message) => (
            <article
              className={`message message-${message.role}`}
              key={message.id}
            >
              <small>
                {message.role === "assistant"
                  ? companionProfiles[controller.companionId].name
                  : "You"}
              </small>
              <p>{message.text}</p>
            </article>
          ))}
          {controller.partialTranscript && (
            <article
              className="message message-user partial"
              data-testid="partial-transcript"
            >
              <small>You · simulated partial</small>
              <p>{controller.partialTranscript}</p>
            </article>
          )}
          {controller.streamingText && (
            <article
              className="message message-assistant streaming"
              data-testid="streaming-text"
            >
              <small>
                {companionProfiles[controller.companionId].name} · streaming
              </small>
              <p>
                {controller.streamingText}
                <span className="cursor" aria-hidden="true" />
              </p>
            </article>
          )}
        </div>
        <form className="composer" onSubmit={submit}>
          <label htmlFor="message-input" className="sr-only">
            Type a message
          </label>
          <input
            id="message-input"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Type Nepali, Romanized, English…"
            autoComplete="off"
            maxLength={8000}
          />
          <button
            type="submit"
            disabled={!input.trim()}
            aria-label="Send message"
          >
            <Icon name="send" />
          </button>
        </form>
        <p className="privacy-note">
          Deterministic local mock · No API key · No microphone capture
        </p>
      </section>
    </main>
  );
}
