import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import "./App.css";
import { ProceduralAvatar } from "./features/avatar/ProceduralAvatar";
import {
  AVATAR_THEMES,
  loadAvatarTheme,
  saveAvatarTheme,
  type AvatarThemeId,
} from "./features/avatar/themes";
import { PrivacyPanel } from "./features/privacy/PrivacyPanel";
import { detectWebGL } from "./features/avatar/webgl";
import {
  fetchProviderStatuses,
  synthesizeSpeech,
  transcribeAudio,
  type ProviderStatus,
  type ProviderMode,
} from "./features/audio/api";
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
  idle: { label: "Ready", detail: "Talk naturally or type a message" },
  listening: { label: "Listening", detail: "Microphone input is active" },
  thinking: { label: "Thinking", detail: "Preparing a safe response" },
  speaking: { label: "Speaking", detail: "Playing the response performance" },
  interrupted: { label: "Interrupted", detail: "The active turn was stopped" },
  error: { label: "Error", detail: "Mock fallback is still available" },
};

function voiceModeLabel(mode: ProviderMode): string {
  if (mode === "mock") return "Synthetic mock voice";
  if (mode === "local") return "Zero-credit local placeholder voice";
  if (mode === "groq") return "Groq brain with local placeholder voice";
  if (mode === "openai") return "Microsoft neural voice";
  return "Azure voice configured";
}

function transcriptModeLabel(mode: ProviderMode): string {
  if (mode === "mock") return "Mock transcript";
  if (mode === "local") return "Local STT unavailable";
  if (mode === "groq") return "Local STT for Groq unavailable";
  if (mode === "openai") return "Microsoft Speech transcript";
  return "Azure transcript";
}

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
  const { setBrainModel, setProviderMode } = controller;
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
  const [avatarTheme, setAvatarTheme] = useState<AvatarThemeId>(() =>
    loadAvatarTheme(),
  );
  const [lowPerformance, setLowPerformance] = useState(false);
  const [voiceDetail, setVoiceDetail] = useState(
    "No microphone permission requested",
  );
  const [providerStatuses, setProviderStatuses] = useState<ProviderStatus[]>(
    [],
  );
  const [providersLoaded, setProvidersLoaded] = useState(false);
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
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);
  const providerAutoSelected = useRef(false);
  const providerManuallySelected = useRef(false);
  const webglAvailable = useMemo(() => detectWebGL(), []);
  const reducedMotion = systemReducedMotion || reduceMotionOverride;
  const active =
    live.active ||
    ["listening", "thinking", "speaking"].includes(controller.state);
  const status = stateCopy[controller.state];
  const localProvider = providerStatuses.find((item) => item.id === "local");
  const openaiProvider = providerStatuses.find((item) => item.id === "openai");
  const customProvider = providerStatuses.find((item) => item.id === "custom");
  const geminiProvider = providerStatuses.find((item) => item.id === "gemini");
  const azureSpeechProvider = providerStatuses.find(
    (item) => item.id === "azure-speech",
  );
  const openaiModelOptions =
    openaiProvider?.capabilities
      .filter((capability) => capability.startsWith("model:"))
      .map((capability) => capability.slice("model:".length)) ?? [];
  const openaiDefaultModel = openaiProvider?.capabilities
    .find((capability) => capability.startsWith("default-model:"))
    ?.slice("default-model:".length);
  const customModelOptions =
    customProvider?.capabilities
      .filter((capability) => capability.startsWith("model:"))
      .map((capability) => capability.slice("model:".length)) ?? [];
  const customDefaultModel = customProvider?.capabilities
    .find((capability) => capability.startsWith("default-model:"))
    ?.slice("default-model:".length);
  const geminiModelOptions =
    geminiProvider?.capabilities
      .filter((capability) => capability.startsWith("model:"))
      .map((capability) => capability.slice("model:".length)) ?? [];
  const geminiDefaultModel = geminiProvider?.capabilities
    .find((capability) => capability.startsWith("default-model:"))
    ?.slice("default-model:".length);
  const activeBrainModelOptions =
    controller.providerMode === "custom"
      ? customModelOptions
      : controller.providerMode === "real"
        ? geminiModelOptions
        : openaiModelOptions;
  const activeBrainDefault =
    controller.providerMode === "custom"
      ? customDefaultModel
      : controller.providerMode === "real"
        ? geminiDefaultModel
        : openaiDefaultModel;
  const localSttReady =
    localProvider?.capabilities.includes("stt") &&
    localProvider.state === "healthy";
  const microsoftSpeechReady = azureSpeechProvider?.state === "healthy";
  const modeAvailability: Record<ProviderMode, boolean> = {
    mock: true,
    local: true,
    groq: false, // hidden / no key
    // Brain providers work for text chat even without Azure voice
    openai: openaiProvider?.state === "healthy",
    custom: customProvider?.state === "healthy",
    real: geminiProvider?.state === "healthy",
  };
  const localMicBlocked = controller.providerMode === "local" && localSttReady !== true;
  const providerNotice =
    controller.providerMode === "local"
      ? (localProvider?.userMessage ??
        "Zero-credit local text and placeholder voice are ready; local microphone STT is not configured.")
      : undefined;
  const voiceReadyLabel = localMicBlocked
    ? "Voice setup needed"
    : controller.providerMode === "custom"
      ? "Custom brain"
      : controller.providerMode === "openai"
        ? "OpenAI + Microsoft"
        : controller.providerMode === "real"
          ? "Cloud cascade"
          : controller.providerMode === "local"
            ? "Zero-credit"
            : "Ready";

  const speakPlan = async (text: string, signal: AbortSignal) => {
    const speech = await synthesizeSpeech(
      text,
      controller.companionId,
      controller.providerMode,
      signal,
    );
    setVoiceDetail(
      `${voiceModeLabel(controller.providerMode)} · ${speech.provider}`,
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
      if (completed) {
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
    if (localMicBlocked) {
      setMicStatus("error");
      setVoiceDetail(
        "Local microphone STT is not configured. Use text, Demo without mic, or configure HINAA_LOCAL_STT_COMMAND.",
      );
      controller.setLiveState("idle");
      return;
    }
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
        `${transcriptModeLabel(controller.providerMode)} · ${transcript.provider}`,
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

  useEffect(() => {
    const abort = new AbortController();
    let retryTimer: number | undefined;

    const loadProviders = () => {
      void fetchProviderStatuses(abort.signal)
        .then((statuses) => {
          setProviderStatuses(statuses);
          setProvidersLoaded(true);
          const byId = new Map(statuses.map((item) => [item.id, item]));
          const microsoftVoiceReady =
            byId.get("azure-speech")?.state === "healthy";
          const customBrainReady = byId.get("custom")?.state === "healthy";
          const openaiBrainReady = byId.get("openai")?.state === "healthy";
          if (
            (customBrainReady || openaiBrainReady) &&
            !providerAutoSelected.current &&
            !providerManuallySelected.current
          ) {
            providerAutoSelected.current = true;
            const selectedProvider = customBrainReady ? "custom" : "openai";
            setProviderMode(selectedProvider);
            const selectedCapabilities = byId.get(selectedProvider)?.capabilities ?? [];
            const defaultModel = selectedCapabilities
              .find((capability) => capability.startsWith("default-model:"))
              ?.slice("default-model:".length);
            const firstModel = selectedCapabilities
              .find((capability) => capability.startsWith("model:"))
              ?.slice("model:".length);
            if (defaultModel || firstModel) setBrainModel(defaultModel ?? firstModel!);
            setVoiceDetail(
              microsoftVoiceReady
                ? selectedProvider === "custom"
                  ? "Custom gateway + Microsoft voice ready"
                  : "Microsoft voice + OpenAI brain ready"
                : selectedProvider === "custom"
                  ? "Custom gateway ready · text chat active"
                  : "OpenAI brain ready · text chat active",
            );
          }
        })
        .catch(() => {
          // Keep retrying until backend is up
          retryTimer = window.setTimeout(loadProviders, 8000);
        });
    };

    loadProviders();
    return () => {
      abort.abort();
      if (retryTimer) window.clearTimeout(retryTimer);
    };
  }, [setBrainModel, setProviderMode]);

  useEffect(() => {
    if (providerNotice) setVoiceDetail(providerNotice);
  }, [providerNotice]);

  // Auto-scroll to bottom when messages or streaming text changes
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [controller.messages, controller.streamingText, controller.state]);

  const setProviderModeWithDefaultModel = (mode: ProviderMode) => {
    providerManuallySelected.current = true;
    controller.setProviderMode(mode);
    const model =
      mode === "custom"
        ? (customDefaultModel ?? customModelOptions[0])
        : mode === "openai"
          ? (openaiDefaultModel ?? openaiModelOptions[0])
          : mode === "real"
            ? (geminiDefaultModel ?? geminiModelOptions[0])
            : undefined;
    if (model) controller.setBrainModel(model);
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
              <small>Phase 3 realtime lab</small>
            </div>
          </div>
          <div className="provider-chip" aria-label="Voice status">
            <span className="status-dot" />
            <span>{voiceReadyLabel}</span>
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
            jawEnergy={playback.jawEnergy}
            theme={avatarTheme}
            lowPerformance={lowPerformance}
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
          <div className="engine-strip" aria-label="Choose brain and voice engine">
            {(
              [
                ["local", "Zero-credit", "Free · text only"],
                ["custom", "Custom cascade", "17 gateway models"],
                ["openai", "OpenAI", "Official GPT models"],
                ["real", "Cloud cascade", "11 Gemini models"],
                ["mock", "Demo", "No API needed"],
              ] as const
            ).map(([mode, label, detail]) => (
              <button
                key={mode}
                type="button"
                className={
                  controller.providerMode === mode ? "selected" : undefined
                }
                aria-pressed={controller.providerMode === mode}
                disabled={live.active || (!providersLoaded ? false : !modeAvailability[mode])}
                title={
                  !providersLoaded
                    ? "Checking availability…"
                    : modeAvailability[mode]
                    ? undefined
                    : mode === "custom"
                      ? "Custom gateway API key or URL is not configured."
                      : mode === "openai"
                        ? "OpenAI key is not configured in the backend."
                        : mode === "real"
                          ? "Gemini API key is not configured."
                          : undefined
                }
                onClick={() => {
                  setProviderModeWithDefaultModel(mode);
                }}
              >
                <span>{label}</span>
                <small>
                  {!providersLoaded
                    ? "Checking…"
                    : modeAvailability[mode]
                    ? detail
                    : "Unavailable"}
                </small>
              </button>
            ))}
          </div>
          <div className="live-session-controls">
            <button
              className="live-button"
              type="button"
              onClick={() => (live.active ? live.stop() : void live.start())}
              aria-pressed={live.active}
              disabled={!live.active && localMicBlocked}
              title={
                localMicBlocked
                  ? "Configure HINAA_LOCAL_STT_COMMAND before using local hands-free mic."
                  : undefined
              }
            >
              <Icon name={live.active ? "stop" : "mic"} />
              {live.active ? "Stop listening" : "Talk to Hinaa"}
            </button>
            {live.active && (
              <button
                className="ghost-button"
                type="button"
                onClick={() => (live.paused ? live.resume() : live.pause())}
                aria-pressed={live.paused}
              >
                {live.paused ? "Resume listening" : "Pause listening"}
              </button>
            )}
          </div>
          {(controller.providerMode === "openai" ||
            controller.providerMode === "custom" ||
            controller.providerMode === "real") && (
            <div className="live-options quick-brain-controls">
              <label>
                Brain model
                <select
                  aria-label="Brain model"
                  value={controller.brainModel}
                  onChange={(event) =>
                    controller.setBrainModel(event.target.value)
                  }
                  disabled={live.active}
                >
                  {(activeBrainModelOptions.length
                    ? activeBrainModelOptions
                    : [controller.brainModel]
                  ).map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              </label>
              <small>
                Active backend default:{" "}
                {activeBrainDefault ?? controller.brainModel}. If one model is
                rate-limited, switch here and try again.
              </small>
            </div>
          )}
          {localMicBlocked && (
            <div className="notice" role="note">
              Zero-credit brain is working for typed chat and placeholder voice.
              Local microphone understanding needs an offline STT command, so
              hands-free local mic is disabled instead of failing repeatedly.
            </div>
          )}
          <p className="live-privacy-note">
            Microphone starts only after you tap Start and grant permission. No
            per-turn mic button is required while the session is active. Stop
            ends capture immediately.
            {controller.providerMode === "mock"
              ? " Mock live uses one fixed demo transcript and pauses after one turn; use text or a real/local STT provider for your actual words."
              : controller.providerMode === "local"
                ? " Local mode never spends credits; microphone STT is still text/mock-only until offline models are installed."
                : controller.providerMode === "groq"
                  ? microsoftSpeechReady
                    ? " Groq mode uses Groq for the brain and Microsoft Speech for listening/speaking."
                    : " Groq mode needs Microsoft Speech or local STT before microphone speech works."
                  : controller.providerMode === "custom"
                    ? " Custom gateway mode uses your separate model API for the brain and Microsoft Speech for listening/speaking."
                  : controller.providerMode === "openai"
                    ? " Microsoft voice mode uses Azure Speech for listening/speaking and OpenAI for the brain."
                    : " Live mode uses real providers only; outages are shown truthfully."}
          </p>
          <div className="live-mic" role="status" aria-live="polite">
            <span
              className={
                live.active && !live.paused
                  ? "live-mic-dot active"
                  : "live-mic-dot"
              }
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
              STT {live.metrics.sttMs ?? "—"} · Brain first{" "}
              {live.metrics.llmFirstDeltaMs ?? "—"} · Brain total{" "}
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
          <details className="advanced-voice-settings">
            <summary>Advanced voice settings</summary>
            <div className="live-options">
              <label>
                Provider
                <select
                  aria-label="Provider mode"
                  value={controller.providerMode}
                  disabled={live.active}
                  onChange={(event) => {
                    setProviderModeWithDefaultModel(
                      event.target.value as ProviderMode,
                    );
                  }}
                >
                  <option value="mock">Safe local demo</option>
                  <option value="local">Zero-credit brain</option>
                  <option value="groq">Groq fast brain</option>
                  <option value="custom">Custom gateway + Microsoft</option>
                  <option value="openai">Microsoft voice + OpenAI brain</option>
                  <option value="real">Cloud cascade: Gemini + Microsoft</option>
                </select>
              </label>
              {(controller.providerMode === "openai" ||
                controller.providerMode === "custom" ||
                controller.providerMode === "real") && (
                <label>
                  Brain model (same as quick selector)
                  <select
                    aria-label="Advanced model picker"
                    value={controller.brainModel}
                    onChange={(event) =>
                      controller.setBrainModel(event.target.value)
                    }
                    disabled={live.active}
                  >
                    {(activeBrainModelOptions.length
                      ? activeBrainModelOptions
                      : [controller.brainModel]
                    ).map((model) => (
                      <option key={model} value={model}>
                        {model}
                      </option>
                    ))}
                  </select>
                </label>
              )}
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
                    setOutputMode(
                      event.target.value as "headphones" | "speaker",
                    )
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
                    setLanguageMode(
                      event.target.value as "fixed-ne-NP" | "auto",
                    )
                  }
                  disabled={live.active}
                >
                  <option value="fixed-ne-NP">Fixed ne-NP</option>
                  <option value="auto">Auto ne/en/hi</option>
                </select>
              </label>
              <label className="theme-picker">
                Visual style
                <select
                  aria-label="Avatar visual style"
                  value={avatarTheme}
                  onChange={(event) => {
                    const next = event.target.value as AvatarThemeId;
                    setAvatarTheme(next);
                    saveAvatarTheme(next);
                  }}
                >
                  {AVATAR_THEMES.map((theme) => (
                    <option key={theme.id} value={theme.id}>
                      {theme.label}
                    </option>
                  ))}
                </select>
              </label>
              <button
                className="ghost-button"
                type="button"
                aria-pressed={lowPerformance}
                onClick={() => setLowPerformance((value) => !value)}
              >
                {lowPerformance
                  ? "Auto performance on"
                  : "Auto performance off"}
              </button>
            </div>
          </details>
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
            disabled={
              micStatus === "requesting" ||
              micStatus === "processing" ||
              localMicBlocked
            }
            title={
              localMicBlocked
                ? "Local STT command is not configured. Use text or Demo without mic."
                : undefined
            }
            aria-label={
              micStatus === "recording"
                ? "Finish recording and send voice"
                : "Start microphone recording"
            }
          >
            <Icon name="mic" />
            <span>
              {micStatus === "recording" ? "Send voice" : "Tap to talk"}
            </span>
          </button>
          <span className="control-spacer" />
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
              {` · STT ${latencies.stt} ms · Brain ${latencies.gemini} ms · TTS ${latencies.tts} ms · total ${latencies.total} ms`}
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
          <span>
            {controller.providerMode === "custom"
              ? controller.brainModel || "Custom cascade"
              : controller.providerMode === "real"
                ? "Cloud cascade"
                : controller.providerMode === "openai"
                  ? "OpenAI"
                  : controller.providerMode === "local"
                    ? "Zero-credit"
                    : "Demo"}
          </span>
        </header>
        <div
          className="transcript"
          data-testid="transcript"
          aria-live="polite"
          aria-relevant="additions text"
        >
          {controller.messages.length === 0 &&
            !controller.streamingText &&
            controller.state !== "thinking" && (
              <div className="transcript-empty">
                <span aria-hidden="true">✦</span>
                <p>Say hi or type a message to start</p>
              </div>
            )}
          {controller.messages.map((message) => (
            <article
              className={`message message-${message.role}`}
              key={message.id}
            >
              <div className="message-header">
                <small>
                  {message.role === "assistant"
                    ? companionProfiles[controller.companionId].name
                    : "You"}
                </small>
                <time>{message.id.slice(-4) /* stable per-message marker */
                  ? new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                  : ""}
                </time>
              </div>
              <p>{message.text}</p>
            </article>
          ))}
          {controller.partialTranscript && (
            <article
              className="message message-user partial"
              data-testid="partial-transcript"
            >
              <div className="message-header">
                <small>You · partial</small>
              </div>
              <p>{controller.partialTranscript}</p>
            </article>
          )}
          {controller.streamingText && (
            <article
              className="message message-assistant streaming"
              data-testid="streaming-text"
            >
              <div className="message-header">
                <small>
                  {companionProfiles[controller.companionId].name} · typing
                </small>
              </div>
              <p>
                {controller.streamingText}
                <span className="cursor" aria-hidden="true" />
              </p>
            </article>
          )}
          {controller.state === "thinking" &&
            !controller.streamingText &&
            !controller.partialTranscript && (
              <article
                className="message message-assistant thinking-message"
                aria-label={`${companionProfiles[controller.companionId].name} is thinking`}
              >
                <div className="message-header">
                  <small>{companionProfiles[controller.companionId].name}</small>
                </div>
                <p>
                  <span className="thinking-dots" aria-hidden="true">
                    <span />
                    <span />
                    <span />
                  </span>
                  <span className="sr-only">Thinking...</span>
                </p>
              </article>
            )}
          <div ref={transcriptEndRef} aria-hidden="true" />
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
            ? "Demo mode · no API calls · deterministic responses"
            : controller.providerMode === "local"
              ? "Zero-credit brain · typed chat works · local mic STT pending"
              : controller.providerMode === "custom"
                ? `Custom gateway · ${controller.brainModel || "cx/gpt-5.6-sol"} · backend-only key`
                : controller.providerMode === "openai"
                  ? "OpenAI GPT · Microsoft Speech · backend-only credentials"
                  : "Gemini Cloud cascade · Microsoft Speech · backend-only credentials"}
        </p>
      </section>
    </main>
  );
}
