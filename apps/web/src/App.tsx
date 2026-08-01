import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import "./App.css";
import { ProceduralAvatar } from "./features/avatar/ProceduralAvatar";
import { PrivacyPanel } from "./features/privacy/PrivacyPanel";
import { detectWebGL } from "./features/avatar/webgl";
import { synthesizeSpeech, transcribeAudio } from "./features/audio/api";
import { MicrophoneRecorder } from "./features/audio/microphoneRecorder";
import { useAudioPlayback } from "./features/audio/useAudioPlayback";
import { useLiveConversation } from "./features/audio/useLiveConversation";
import {
  companionProfiles,
  type CompanionId,
  type CompanionState,
} from "./features/companion/types";
import { useCompanionController } from "./features/companion/useCompanionController";
import { useReducedMotionPreference } from "./shared/useReducedMotion";

const stateCopy: Record<CompanionState, { label: string; detail: string }> = {
  idle: { label: "Ready", detail: "Choose live, push-to-talk, or text" },
  listening: { label: "Listening", detail: "Microphone input is active" },
  thinking: { label: "Thinking", detail: "Preparing a safe response" },
  speaking: { label: "Speaking", detail: "Playing the response performance" },
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
  const playback = useAudioPlayback();
  const systemReducedMotion = useReducedMotionPreference();
  const [reduceMotionOverride, setReduceMotionOverride] = useState(false);
  const [textOnly, setTextOnly] = useState(false);
  const [calibration, setCalibration] = useState<"natural" | "soft" | "lively">(
    "natural",
  );
  const [outputMode, setOutputMode] = useState<"headphones" | "speaker">(
    "speaker",
  );
  const [languageMode, setLanguageMode] = useState<"fixed-ne-NP" | "auto">(
    "fixed-ne-NP",
  );
  const [input, setInput] = useState("");
  const [micStatus, setMicStatus] = useState<
    | "idle"
    | "requesting"
    | "recording"
    | "processing"
    | "denied"
    | "unsupported"
    | "error"
  >("idle");
  const [voiceDetail, setVoiceDetail] = useState(
    "No microphone permission requested",
  );
  const [latencies, setLatencies] = useState<{
    stt: number;
    gemini: number;
    tts: number;
    total: number;
  }>();
  const live = useLiveConversation({
    controller,
    playback,
    calibration,
    outputMode,
    languageMode,
  });
  const recorder = useRef<MicrophoneRecorder | undefined>(undefined);
  const voiceAbort = useRef<AbortController | undefined>(undefined);
  const recordingTimer = useRef<number | undefined>(undefined);
  const webglAvailable = useMemo(() => detectWebGL(), []);
  const reducedMotion = systemReducedMotion || reduceMotionOverride;
  const active =
    live.active ||
    ["listening", "thinking", "speaking"].includes(controller.state);
  const status = stateCopy[controller.state];

  const speakPlan = async (text: string, signal: AbortSignal) => {
    const speech = await synthesizeSpeech(
      text,
      controller.companionId,
      controller.providerMode,
      signal,
    );
    setVoiceDetail(
      `${controller.providerMode === "mock" ? "Synthetic mock voice" : "Azure voice configured"} · ${speech.provider}`,
    );
    await playback.play(speech.blob);
    return speech.latencyMs;
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = input.trim();
    if (!value) return;
    if (live.active) live.stop();
    setInput("");
    void (async () => {
      const completed = await controller.sendText(value);
      if (completed && controller.providerMode === "real") {
        voiceAbort.current?.abort();
        voiceAbort.current = new AbortController();
        try {
          await speakPlan(completed.plan.spokenText, voiceAbort.current.signal);
        } catch (error) {
          if (!(error instanceof DOMException && error.name === "AbortError"))
            setVoiceDetail(
              "Voice playback failed; the text response is preserved",
            );
        }
      }
    })();
  };

  async function startRecording() {
    if (live.active) live.stop();
    voiceAbort.current?.abort();
    playback.stop();
    const nextRecorder = new MicrophoneRecorder();
    recorder.current = nextRecorder;
    setMicStatus("requesting");
    setVoiceDetail("Waiting for browser microphone permission…");
    try {
      await nextRecorder.start();
      controller.beginListening();
      setMicStatus("recording");
      setVoiceDetail(
        "Microphone active · tap again to process · 20 second maximum",
      );
      recordingTimer.current = window.setTimeout(
        () => void finishRecording(),
        20_000,
      );
    } catch (error) {
      await nextRecorder.cancel();
      recorder.current = undefined;
      if (error instanceof DOMException && error.name === "NotAllowedError") {
        setMicStatus("denied");
        setVoiceDetail(
          "Microphone is off. Enable it in browser settings or use text.",
        );
      } else if (
        error instanceof DOMException &&
        error.name === "NotSupportedError"
      ) {
        setMicStatus("unsupported");
        setVoiceDetail(
          "This browser cannot capture audio; text and demo voice still work.",
        );
      } else {
        setMicStatus("error");
        setVoiceDetail(
          "Microphone setup failed safely; use text or the no-permission demo.",
        );
      }
    }
  }

  async function finishRecording() {
    if (recordingTimer.current) window.clearTimeout(recordingTimer.current);
    recordingTimer.current = undefined;
    const activeRecorder = recorder.current;
    if (!activeRecorder) return;
    recorder.current = undefined;
    setMicStatus("processing");
    setVoiceDetail("Processing this recording in memory…");
    setLatencies(undefined);
    const processingStarted = performance.now();
    voiceAbort.current?.abort();
    const abort = new AbortController();
    voiceAbort.current = abort;
    try {
      const wav = await activeRecorder.stop();
      const transcript = await transcribeAudio(
        wav,
        controller.providerMode,
        abort.signal,
      );
      setVoiceDetail(
        `${controller.providerMode === "mock" ? "Mock transcript" : "Azure transcript"} · ${transcript.provider}`,
      );
      const completed = await controller.sendText(transcript.text, {
        forceBackend: true,
      });
      if (completed) {
        const ttsLatency = await speakPlan(
          completed.plan.spokenText,
          abort.signal,
        );
        setLatencies({
          stt: transcript.latencyMs,
          gemini: completed.providerLatencyMs ?? 0,
          tts: ttsLatency,
          total: Math.round(performance.now() - processingStarted),
        });
      }
      setMicStatus("idle");
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setMicStatus("error");
      setVoiceDetail(
        error instanceof Error ? error.message : "Voice turn failed safely",
      );
    }
  }

  const stopAll = () => {
    if (recordingTimer.current) window.clearTimeout(recordingTimer.current);
    recordingTimer.current = undefined;
    void recorder.current?.cancel();
    recorder.current = undefined;
    voiceAbort.current?.abort();
    playback.stop();
    if (live.active) live.stop();
    else controller.stop();
    setMicStatus("idle");
    setVoiceDetail("Stopped; no captured audio was retained");
  };

  useEffect(
    () => () => {
      if (recordingTimer.current) window.clearTimeout(recordingTimer.current);
      void recorder.current?.cancel();
      voiceAbort.current?.abort();
    },
    [],
  );

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
              <small>Phase 3 realtime lab</small>
            </div>
          </div>
          <label className="provider-chip">
            <span className="status-dot" />
            <span className="sr-only">Provider mode</span>
            <select
              aria-label="Provider mode"
              value={controller.providerMode}
              disabled={live.active}
              onChange={(event) =>
                controller.setProviderMode(
                  event.target.value as "mock" | "real",
                )
              }
            >
              <option value="mock">Local mock</option>
              <option value="real">Real cascade</option>
            </select>
          </label>
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
            jawEnergy={playback.jawEnergy}
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
          onChange={(id) => {
            if (live.active) live.stop();
            controller.setCompanionId(id);
          }}
        />

        <PrivacyPanel />

        <section className="live-panel" aria-label="Live conversation controls">
          <div className="live-options">
            <label>
              Voice feel
              <select
                value={calibration}
                onChange={(event) =>
                  setCalibration(
                    event.target.value as "natural" | "soft" | "lively",
                  )
                }
                disabled={live.active}
              >
                <option value="natural">Natural</option>
                <option value="soft">Soft</option>
                <option value="lively">Lively</option>
              </select>
            </label>
            <label>
              Audio output
              <select
                value={outputMode}
                onChange={(event) =>
                  setOutputMode(event.target.value as "headphones" | "speaker")
                }
                disabled={live.active}
              >
                <option value="speaker">Speaker</option>
                <option value="headphones">Headphones</option>
              </select>
            </label>
            <label>
              Recognition
              <select
                value={languageMode}
                onChange={(event) =>
                  setLanguageMode(event.target.value as "fixed-ne-NP" | "auto")
                }
                disabled={live.active}
              >
                <option value="fixed-ne-NP">Fixed ne-NP</option>
                <option value="auto">Auto ne/en/hi</option>
              </select>
            </label>
          </div>
          <button
            className="live-button"
            type="button"
            onClick={() => (live.active ? live.stop() : void live.start())}
            aria-pressed={live.active}
          >
            <Icon name={live.active ? "stop" : "mic"} />
            {live.active ? "Stop Live Conversation" : "Start Live Conversation"}
          </button>
          <div className="live-mic" role="status" aria-live="polite">
            <span
              className={live.active ? "live-mic-dot active" : "live-mic-dot"}
              aria-hidden="true"
            />
            <span>{live.detail}</span>
            <meter
              min="0"
              max="0.2"
              value={Math.min(0.2, live.microphoneLevel)}
              aria-label="Live microphone level"
            />
          </div>
          {live.voiceMetadata && (
            <small className="voice-metadata">{live.voiceMetadata}</small>
          )}
          {import.meta.env.DEV && live.metrics.totalMs !== undefined && (
            <div className="latency-strip" data-testid="streaming-latencies">
              Goal / measured: partial ≤500 ms · final ≤900 ms · first text ≤800
              ms · audible ≤1800 ms · barge ≤150 ms
              <br />
              STT {live.metrics.sttMs ?? "—"} · Gemini first{" "}
              {live.metrics.llmFirstDeltaMs ?? "—"} · Gemini total{" "}
              {live.metrics.llmMs ?? "—"} · TTS {live.metrics.ttsMs ?? "—"} ·
              turn {live.metrics.totalMs ?? "—"} · barge{" "}
              {live.metrics.bargeInStopMs ?? "not tested"} ms
              <br />
              Browser: partial {live.metrics.partialFromSpeechMs ?? "—"} · final{" "}
              {live.metrics.finalAfterSpeechMs ?? "—"} · first text{" "}
              {live.metrics.firstTextAfterFinalMs ?? "—"} · first audible{" "}
              {live.metrics.firstAudibleAfterSpeechMs ?? "—"} · playback
              complete {live.metrics.playbackCompleteAfterSpeechMs ?? "—"} ms
            </div>
          )}
          <p className="voice-disclosure">
            Hemkala and Sagar are standard Azure Nepali neural voices, not
            custom anime voices. A unique Hinaa voice requires a licensed,
            consenting voice actor or approved dataset.
          </p>
          {import.meta.env.DEV && (
            <button className="calibration-sample" type="button" disabled>
              Generate calibration sample · separate live-call approval required
            </button>
          )}
        </section>

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
              onClick={stopAll}
              aria-label="Stop current turn"
            >
              <Icon name="stop" /> Stop
            </button>
          ) : (
            <span className="control-spacer" />
          )}
          <button
            className="mic-button"
            type="button"
            onClick={() =>
              micStatus === "recording"
                ? void finishRecording()
                : void startRecording()
            }
            disabled={micStatus === "requesting" || micStatus === "processing"}
            aria-label={
              micStatus === "recording"
                ? "Stop and process microphone recording"
                : "Start microphone recording"
            }
          >
            <Icon name="mic" />
            <span>
              {micStatus === "recording" ? "Process" : "Push-to-talk"}
            </span>
          </button>
          <button
            className="camera-button"
            type="button"
            disabled
            title="Camera is outside Phase 3"
          >
            Camera off
          </button>
        </div>
        <div className="voice-tools" aria-label="Voice and fallback controls">
          <button
            type="button"
            onClick={controller.startMockListening}
            aria-label="Simulate microphone listening without permission"
          >
            Demo without mic
          </button>
          <button
            type="button"
            onClick={() => void playback.replay()}
            disabled={!playback.hasReplay}
          >
            Replay
          </button>
          <button
            type="button"
            onClick={playback.toggleMute}
            aria-pressed={playback.muted}
          >
            {playback.muted ? "Unmute" : "Mute"}
          </button>
        </div>
        <p className={`mic-status mic-${micStatus}`} role="status">
          <span aria-hidden="true" /> {voiceDetail}
          {latencies && (
            <small data-testid="live-latencies">
              {` · STT ${latencies.stt} ms · Gemini ${latencies.gemini} ms · TTS ${latencies.tts} ms · total ${latencies.total} ms`}
            </small>
          )}
        </p>
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
          {controller.providerMode === "mock"
            ? "Deterministic mock providers · microphone capture only after tap · no API key"
            : "Real providers selected · backend-only credentials · session memory only"}
        </p>
      </section>
    </main>
  );
}
