import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./App.css";
import { motion } from "framer-motion";
import { TranscriptView } from "./features/chat/components/TranscriptView";
import { extractCodeBlock, isOtakuXWearTopic } from "./features/avatar/stageModes";
import {
  type AvatarPresentation,
  defaultAvatarPresentation,
  getPersistedAvatarPresentation,
  persistAvatarPresentation,
} from "./features/avatar/avatarPresentation";
import { FullScreenAura } from "./components/ui/FullScreenAura";
import { SearchingLoader } from "./components/ui/SearchingLoader";
import { PremiumComposer } from "./components/ui/PremiumComposer";
import ParticleOrbitEffect from "./components/lightswind/ParticleOrbitEffect";
import type { PresenceMode } from "./components/ui/AvatarPresence";
import { HinaDrawer } from "./components/lightswind/Drawer";
import { SidebarProvider } from "./components/lightswind/Sidebar";
import { synthesizeSpeech } from "./features/audio/api";
import { useAudioPlayback } from "./features/audio/useAudioPlayback";
import { useLiveConversation } from "./features/audio/useLiveConversation";
import { useVSeeFace } from "./features/audio/useVSeeFace";
import { companionProfiles, type CompanionId, type CompanionState } from "./features/companion/types";
import { useCompanionController } from "./features/companion/useCompanionController";
import { useProviders } from "./features/providers/hooks/useProviders";
import { useProviderRouting } from "./features/providers/hooks/useProviderRouting";
import { SettingsDialog, SettingsTrigger, useSettings, useSettingsPersistence } from "./features/settings";
import { AppearanceSettings } from "./features/settings/sections/AppearanceSettings";
import { LanguageSettings } from "./features/settings/sections/LanguageSettings";
import { ProviderSettings } from "./features/settings/sections/ProviderSettings";
import { DiagnosticsSettings } from "./features/settings/sections/DiagnosticsSettings";
import { NavRail, type NavSection } from "./components/ui/NavRail";
import { ActivityPanel, type AgentStep } from "./components/ui/ActivityPanel";
import { ActionChips, type ActionChip } from "./components/ui/ActionChips";
import type { ContextMode } from "./components/ui/ContextWorkspace";
import { SidebarPanel } from "./components/ui/SidebarPanel";
import { VmcControlPanel } from "./components/ui/VmcControlPanel";

import type { PowerUp } from "./components/ui/PowerUpMentions";
import useMemory from "./features/memory/useMemory";

const AvatarPresence = lazy(() => import("./components/ui/AvatarPresence").then((module) => ({ default: module.AvatarPresence })));
const ContextWorkspace = lazy(() => import("./components/ui/ContextWorkspace").then((module) => ({ default: module.ContextWorkspace })));
const MemoryPanel = lazy(() => import("./components/ui/MemoryPanel").then((module) => ({ default: module.MemoryPanel })));
const LocalProjectWorkspace = lazy(() => import("./components/ui/LocalProjectWorkspace").then((module) => ({ default: module.LocalProjectWorkspace })));
const LocalImageStudio = lazy(() => import("./components/ui/LocalImageStudio").then((module) => ({ default: module.LocalImageStudio })));
const LocalHumanizerStudio = lazy(() => import("./components/ui/LocalHumanizerStudio").then((module) => ({ default: module.LocalHumanizerStudio })));
const AvatarLab = lazy(() => import("./components/ui/AvatarLab").then((module) => ({ default: module.AvatarLab })));

const lazyPanelFallback = <div style={{ padding: 12, color: "#94a3b8", fontSize: 12 }}>Loading local workspace…</div>;

const AVATAR_MODEL_STORAGE_KEY = "hinaa.avatar-model";
const AVATAR_CAMERA_STORAGE_KEY = "hinaa.avatar-camera.v1";
const HINAA_AVATAR_MODELS = [
  { url: "/models/model_6164.vrm", label: "Hinaa" },
  { url: "/models/model_5447.vrm", label: "Hinaa Classic" },
] as const;
const DEFAULT_AVATAR_MODEL = HINAA_AVATAR_MODELS[0].url;
const MANAGED_AVATAR_URL = /^\/api\/v1\/avatar-assets\/avatar-[0-9a-f-]+\/file$/i;

function isSelectableAvatarUrl(value: string | null): value is string {
  return Boolean(value && (HINAA_AVATAR_MODELS.some((model) => model.url === value) || MANAGED_AVATAR_URL.test(value)));
}

function getPersistedAvatarModel(): string {
  if (typeof window === "undefined") return DEFAULT_AVATAR_MODEL;
  try {
    const stored = window.localStorage.getItem(AVATAR_MODEL_STORAGE_KEY);
    return isSelectableAvatarUrl(stored) ? stored : DEFAULT_AVATAR_MODEL;
  } catch {
    return DEFAULT_AVATAR_MODEL;
  }
}

function getPersistedAvatarCamera(modelUrl: string): PresenceMode {
  if (typeof window === "undefined") return "portrait";
  try {
    const values = JSON.parse(window.localStorage.getItem(AVATAR_CAMERA_STORAGE_KEY) ?? "{}") as Record<string, PresenceMode>;
    const selected = values[modelUrl];
    return selected === "closeup" || selected === "portrait" || selected === "upperbody" || selected === "full" ? selected : "portrait";
  } catch {
    return "portrait";
  }
}

function persistAvatarCamera(modelUrl: string, mode: PresenceMode): void {
  try {
    const values = JSON.parse(window.localStorage.getItem(AVATAR_CAMERA_STORAGE_KEY) ?? "{}") as Record<string, PresenceMode>;
    values[modelUrl] = mode;
    window.localStorage.setItem(AVATAR_CAMERA_STORAGE_KEY, JSON.stringify(values));
  } catch {
    // Camera remains usable when local browser storage is unavailable.
  }
}

/* NOTE: HinaaCommandCenter removed — it broke the UI on click.
   Use ⌘K in-app menu: HINAA → in-page quick action menu instead. */

/* ─── Helpers ──────────────────────────────────────────── */
function extractYouTubeIntent(text: string): string | null {
  const u = text.match(/https?:\/\/(www\.)?youtube\.com\/\S+/i);
  if (u) return u[0];
  const s = text.match(/https?:\/\/youtu\.be\/\S+/i);
  if (s) return s[0];
  const p = text.match(/play\s+(.+?)(?:\s+on youtube)?[.!?]?$/i);
  return p ? `https://www.youtube.com/results?search_query=${encodeURIComponent(p[1].trim())}` : null;
}

const stateLabels: Record<CompanionState, string> = {
  idle: "Ready", listening: "Listening", thinking: "Understanding",
  speaking: "Speaking", interrupted: "Interrupted", error: "Connection Issue",
};

type AvatarTrackingMode = "autonomous" | "exact-vseeface" | "tracking-proxy";

type VoiceReplyState = {
  kind: "idle" | "cloud" | "browser" | "unavailable";
  label: string;
  detail?: string;
};

type PlaybackSessionStatus =
  | "preparing"
  | "buffering"
  | "playing"
  | "completed"
  | "interrupted"
  | "failed";

type PlaybackSession = {
  playbackId: string;
  turnId: string;
  conversationId: string;
  companionId: CompanionId;
  provider: string;
  spokenText: string;
  locale: string;
  status: PlaybackSessionStatus;
  startedAt?: string;
  completedAt?: string;
  error?: string;
};

function CompanionSwitch({ value, onChange }: { value: CompanionId; onChange: (id: CompanionId) => void }) {
  return (
    <div className="companion-switch" role="group" aria-label="Choose companion">
      {(Object.keys(companionProfiles) as CompanionId[]).map((id) => (
        <motion.button type="button" className={value === id ? "selected" : ""} aria-pressed={value === id}
          onClick={() => onChange(id)} key={id} whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.95 }}>
          <span>{companionProfiles[id].name}</span><small>{companionProfiles[id].label}</small>
        </motion.button>
      ))}
    </div>
  );
}

/* ─── Main App ─────────────────────────────────────────── */
export default function App() {
  const playback = useAudioPlayback();
  const providers = useProviders();
  const { settings, setAppearance, setLanguage, setProvider } = useSettings();
  useSettingsPersistence(settings);

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<"info" | "image" | "web" | "music" | "slides" | "code">("info");
  const [drawerTitle, setDrawerTitle] = useState("");
  const [drawerContent, setDrawerContent] = useState<React.ReactNode>(null);
  const [input, setInput] = useState("");
  const [searching, setSearching] = useState(false);
  const [attachedImage, setAttachedImage] = useState<string | null>(null);
  const [voiceReply, setVoiceReply] = useState<VoiceReplyState>({
    kind: "idle",
    label: "Voice ready",
  });
  const [playbackSession, setPlaybackSession] = useState<PlaybackSession | null>(null);
  const activePlaybackId = useRef<string | null>(null);

  const [navSection, setNavSection] = useState<NavSection>("chat");
  const [sidebarExpanded, setSidebarExpanded] = useState<NavSection | null>(null);
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [contextMode, setContextMode] = useState<ContextMode>("hidden");
  const [agentSteps, setAgentSteps] = useState<AgentStep[]>([]);
  const [actionChips, setActionChips] = useState<ActionChip[]>([]);
  const [contextSources] = useState<any[]>([]);
  // Use the owner-supplied local model as the preferred avatar. The procedural
  // renderer remains the safe fallback if an asset cannot load.
  const [avatarModel, setAvatarModel] = useState<string>(getPersistedAvatarModel);
  const [avatarMode, setAvatarMode] = useState<PresenceMode>(() => getPersistedAvatarCamera(getPersistedAvatarModel()));
  const [avatarPresentation, setAvatarPresentation] = useState<AvatarPresentation>(() => getPersistedAvatarPresentation(getPersistedAvatarModel()));
  const [avatarUploadMessage, setAvatarUploadMessage] = useState<string | null>(null);
  const avatarUploadRef = useRef<HTMLInputElement>(null);
  const [avatarTrackingMode, setAvatarTrackingMode] = useState<AvatarTrackingMode>("autonomous");
  const changeAvatarMode = (mode: PresenceMode) => {
    if (mode === "hidden") return;
    setAvatarMode(mode);
    persistAvatarCamera(avatarModel, mode);
  };
  const updateAvatarPresentation = (next: AvatarPresentation) => {
    setAvatarPresentation(next);
    persistAvatarPresentation(avatarModel, next);
  };
  const selectAvatarModel = (modelUrl: string, resetCompanionView = false) => {
    if (!isSelectableAvatarUrl(modelUrl)) return;
    const nextMode = resetCompanionView ? "portrait" : getPersistedAvatarCamera(modelUrl);
    const nextPresentation = resetCompanionView
      ? defaultAvatarPresentation(modelUrl)
      : getPersistedAvatarPresentation(modelUrl);
    setAvatarModel(modelUrl);
    setAvatarMode(nextMode);
    setAvatarPresentation(nextPresentation);
    if (resetCompanionView) {
      persistAvatarCamera(modelUrl, nextMode);
      persistAvatarPresentation(modelUrl, nextPresentation);
    }
    try {
      window.localStorage.setItem(AVATAR_MODEL_STORAGE_KEY, modelUrl);
    } catch {
      // The renderer still works when browser storage is unavailable.
    }
  };
  const importAndSelectAvatar = async (file: File) => {
    setAvatarUploadMessage(`Preparing ${file.name} locally…`);
    const form = new FormData();
    form.append("file", file, file.name);
    try {
      const response = await fetch("/api/v1/avatar-assets/import", { method: "POST", body: form });
      const body = await response.json();
      if (!response.ok || !body?.asset?.browserUrl) throw new Error(body?.detail || "HINAA could not import that VRM.");
      selectAvatarModel(body.asset.browserUrl, true);
      setAvatarUploadMessage(`${body.asset.displayName} is selected in HINAA’s centered portrait companion view with the strong relaxed-arm preset. Your original VRM was not changed.`);
    } catch (error) {
      setAvatarUploadMessage(error instanceof Error ? error.message : "HINAA could not import that VRM.");
    }
  };

  // A WebSocket is transport only. Head data needs fresh external VMC while
  // facial animation additionally needs at least one supported blendshape.
  const faceTrack = useVSeeFace();
  const faceActive = faceTrack.status === "live";
  const facialSignalActive = faceActive && faceTrack.hasFacialSignal;

  const routing = useProviderRouting(settings.provider, providers);
  const controller = useCompanionController({
    routing,
    languagePolicy: settings.language.activePolicy,
  });
  // This is HINAA's own text only. The avatar director uses it for a subtle
  // deterministic expression accent; it never classifies webcam/user emotion.
  const latestAssistantExpressionText = [...controller.messages].reverse().find((message) => message.role === "assistant")?.text;
  useMemory();

  // Keep the first interactive paint light, then warm the local-only panels in
  // the background so opening Projects or Image Studio feels immediate.
  useEffect(() => {
    const preload = () => {
      void import("./components/ui/LocalProjectWorkspace");
      void import("./components/ui/LocalImageStudio");
      void import("./components/ui/LocalHumanizerStudio");
    };
    const idleWindow = window as Window & {
      requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number;
      cancelIdleCallback?: (handle: number) => void;
    };
    const usedIdleCallback = typeof idleWindow.requestIdleCallback === "function";
    const handle = usedIdleCallback
      ? idleWindow.requestIdleCallback!(preload, { timeout: 1800 })
      : window.setTimeout(preload, 1200);
    return () => {
      if (usedIdleCallback) idleWindow.cancelIdleCallback?.(handle);
      else window.clearTimeout(handle);
    };
  }, []);

  const live = useLiveConversation({
    controller,
    playback,
    calibration: "natural",
    outputMode: "headphones",
    activeLanguagePolicy: settings.language.activePolicy,
  });

  const interruptPlayback = useCallback((status: "interrupted" | "failed" = "interrupted", error?: string) => {
    const playbackId = activePlaybackId.current;
    if (!playbackId) return;
    activePlaybackId.current = null;
    playback.stop();
    setPlaybackSession((current) => current?.playbackId === playbackId
      ? { ...current, status, completedAt: new Date().toISOString(), error }
      : current);
  }, [playback]);

  // A started playback owns its own terminal transition. The hook changes
  // `playing` when decoded audio or browser speech ends; no render effect can
  // initiate another playback, so refresh/rerender cannot replay a turn.
  useEffect(() => {
    if (!playbackSession || playbackSession.status !== "playing" || playback.playing) return;
    const playbackId = playbackSession.playbackId;
    const timer = window.setTimeout(() => {
      if (activePlaybackId.current !== playbackId) return;
      activePlaybackId.current = null;
      setPlaybackSession((current) => current?.playbackId === playbackId
        ? { ...current, status: "completed", completedAt: new Date().toISOString() }
        : current);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [playback.playing, playbackSession]);

  /* ─── Submit ─────────────────────────────────────────── */
  const submit = useCallback((event?: any) => {
    if (event && "preventDefault" in event) event.preventDefault();
    if ((!input.trim() && !attachedImage) || live.active) return;
    interruptPlayback();
    const text = input || (attachedImage ? "Look at this image" : "");
    const imageData = attachedImage;
    setInput("");
    setAttachedImage(null);
    void (async () => {
      const result = await controller.sendText(text + (imageData ? " [image attached]" : ""));
      const plan = result?.plan;
      const spoken = plan?.spokenText?.trim();
      if (!result || !plan || !spoken) return;

      const playbackId = `playback-${result.turnId}-${Date.now()}`;
      activePlaybackId.current = playbackId;
      const createSession = (provider: string, status: PlaybackSessionStatus): PlaybackSession => ({
        playbackId,
        turnId: result.turnId,
        conversationId: "browser-session",
        companionId: controller.companionId,
        provider,
        spokenText: spoken,
        locale: plan.language,
        status,
      });
      const updateSession = (status: PlaybackSessionStatus, patch: Partial<PlaybackSession> = {}) => {
        if (activePlaybackId.current !== playbackId) return false;
        setPlaybackSession((current) => current?.playbackId === playbackId
          ? { ...current, status, ...patch }
          : { ...createSession(patch.provider ?? "browser", status), ...patch });
        return true;
      };
      const startBrowserFallback = async (detail: string) => {
        updateSession("preparing", { provider: "browser-speech" });
        const started = await playback.speakBrowser(spoken, plan.language);
        if (!started || activePlaybackId.current !== playbackId) {
          updateSession("failed", { error: "Browser speech could not start." });
          setVoiceReply({
            kind: "unavailable",
            label: "Voice could not start",
            detail: "Enable a browser voice or configure ElevenLabs in Settings.",
          });
          return;
        }
        updateSession("playing", { provider: "browser-speech", startedAt: new Date().toISOString() });
        setVoiceReply({ kind: "browser", label: "Speaking with local browser voice", detail });
      };

      const ttsMode = controller.routing.activeMode;
      if (!ttsMode || ttsMode === "mock") {
        await startBrowserFallback(
          "Demo mode uses your device voice until a cloud or local TTS engine is configured.",
        );
        return;
      }

      try {
        updateSession("buffering", { provider: ttsMode });
        const speech = await synthesizeSpeech(
          spoken,
          controller.companionId,
          ttsMode,
          new AbortController().signal,
        );
        if (activePlaybackId.current !== playbackId) return;
        if (/placeholder|mock/i.test(speech.provider)) {
          await startBrowserFallback(
            "The selected mode has no intelligible server voice yet, so Hinaa is using your device voice.",
          );
          return;
        }
        await playback.play(speech.blob, spoken);
        if (!updateSession("playing", {
          provider: speech.provider,
          startedAt: new Date().toISOString(),
        })) return;
        setVoiceReply({
          kind: "cloud",
          label: `Speaking with ${speech.provider}`,
          detail: speech.latencyMs > 0 ? `${speech.latencyMs} ms synthesis` : undefined,
        });
      } catch (error) {
        if (activePlaybackId.current !== playbackId) return;
        await startBrowserFallback(
          error instanceof Error
            ? `${error.message} Using the device voice instead.`
            : "Cloud voice is unavailable, so Hinaa is using the device voice instead.",
        );
      }
    })();
  }, [input, live.active, controller, playback, attachedImage, interruptPlayback]);

  const openHumanizer = () => {
    setDrawerMode("info");
    setDrawerTitle("HINAA Text Humanizer");
    setDrawerContent(<Suspense fallback={lazyPanelFallback}><LocalHumanizerStudio onClose={() => setDrawerOpen(false)} /></Suspense>);
    setDrawerOpen(true);
  };

  const handlePowerUp = useCallback((p: PowerUp) => {
    // A command changes HINAA's working surface and leaves an explicit intent
    // tag in the composer. It never performs an external action by itself.
    const map: Record<string, () => void> = {
      "search-web": () => { setContextMode("research"); setSearching(true); },
      "image-search": () => setContextMode("images"),
      "generate-image": () => setContextMode("images"),
      "browser-navigate": () => setContextMode("browser"),
      "browser-read": () => setContextMode("browser"),
      "write-code": () => { setNavSection("tools"); setSidebarExpanded(null); },
      "play-music": () => setContextMode("music"),
      "check-email": () => setContextMode("email"),
      "show-calendar": () => { setNavSection("tools"); setSidebarExpanded(null); },
      "search-files": () => { setNavSection("files"); setSidebarExpanded(null); },
      "remember-this": () => setMemoryOpen(true),
      "agent-mode": () => { setNavSection("tasks"); setSidebarExpanded(null); },
      "automation": () => { setNavSection("tasks"); setSidebarExpanded(null); },
      "system-open": () => { setNavSection("tools"); setSidebarExpanded(null); },
      "export": () => { setNavSection("files"); setSidebarExpanded(null); },
      "humanize-text": openHumanizer,
    };
    map[p.action]?.();
  }, [openHumanizer]);

  const handleNav = useCallback((s: NavSection) => {
    if (s === "memory") { setMemoryOpen(v => !v); return; }
    setNavSection(s);
    if (s === "tasks" || s === "files") {
      setSidebarExpanded(null);
      return;
    }
    setSidebarExpanded(prev => prev === s ? null : s);
  }, []);

  const openAvatarLab = () => {
    setDrawerMode("info");
    setDrawerTitle("Avatar Lab");
    setDrawerContent(<Suspense fallback={lazyPanelFallback}><AvatarLab
      tracker={faceTrack}
      selectedModelUrl={avatarModel}
      mode={avatarMode}
      onModeChange={changeAvatarMode}
      onSelectModel={selectAvatarModel}
      presentation={avatarPresentation}
      onPresentationChange={updateAvatarPresentation}
      trackingMode={avatarTrackingMode}
      onTrackingModeChange={setAvatarTrackingMode}
      onClose={() => setDrawerOpen(false)}
    /></Suspense>);
    setDrawerOpen(true);
  };

  const openImageStudio = () => {
    setDrawerMode("image");
    setDrawerTitle("Hinaa Image Studio");
    setDrawerContent(<Suspense fallback={lazyPanelFallback}><LocalImageStudio onClose={() => setDrawerOpen(false)} /></Suspense>);
    setDrawerOpen(true);
  };

  const handleWelcome = (action: string) => {
    if (action === "voice") live.start();
    else if (action === "research") setInput("Search for: ");
    else if (action === "create") openImageStudio();
    else if (action === "work") setInput("Help me plan my work: ");
  };

  /* ─── Agent steps ────────────────────────────────────── */
  useEffect(() => {
    const latestUserText = [...controller.messages].reverse().find(m => m.role === "user")?.text?.toLowerCase() ?? "";
    const isResearch = /search|find|research|look up|source|citation/i.test(latestUserText);

    if (controller.state === "thinking") {
      setSearching(isResearch);
      if (isResearch) {
        setContextMode("research");
        setAgentSteps([
          { id: "scope", label: "Understand the question", detail: "Checking scope and evidence needs", status: "done" },
          { id: "strategy", label: "Prepare source strategy", detail: "Selecting a focused research route — no web pages fetched yet", status: "active" },
          { id: "approval", label: "Wait for your approval", detail: "Live research begins only after you confirm the proposed action", status: "pending" },
          { id: "synthesis", label: "Prepare concise findings", detail: "Returned sources stay visible and attributable", status: "pending" },
        ]);
      } else {
        setAgentSteps([
          { id: "scope", label: "Understand the request", detail: "Identifying the useful outcome", status: "done" },
          { id: "work", label: "Build the response", detail: "Working through the next best action", status: "active" },
        ]);
      }
      return;
    }

    setSearching(false);
    if (controller.state === "speaking" || controller.state === "idle") {
      setAgentSteps((previous) => previous.map((step) => ({ ...step, status: "done" as const })));
      const timer = window.setTimeout(() => setAgentSteps([]), 1800);
      return () => window.clearTimeout(timer);
    }
  }, [controller.state, controller.messages]);

  /* ─── Action chips ───────────────────────────────────── */
  useEffect(() => {
    if (controller.state !== "idle") return;
    const msgs = controller.messages; if (msgs.length === 0) return;
    const last = msgs[msgs.length - 1]; if (last?.role !== "assistant") return;
    const txt = last.text.toLowerCase(); const chips: ActionChip[] = [];
    if (/search|source|found|research/i.test(txt)) {
      chips.push({ id: "src", label: "Review sources", icon: "search" });
      chips.push({ id: "deepen", label: "Go deeper", icon: "search" });
    }
    if (/image|photo|visual/i.test(txt)) {
      chips.push({ id: "img", label: "Open image studio", icon: "image" });
    }
    if (/code|```/i.test(txt)) chips.push({ id: "code", label: "Explain simply", icon: "book" });
    chips.push({ id: "plan", label: "Turn this into a plan", icon: "default" });
    chips.push({ id: "cont", label: "Continue", icon: "default" });
    setActionChips(chips.slice(0, 4));
  }, [controller.messages, controller.state]);

  const showWelcome = controller.messages.length <= 1 && !controller.streamingText && !controller.partialTranscript && controller.state === "idle" && !live.active;

  return (
    <SidebarProvider defaultExpanded={false}>
      <div className="hinaa-shell">
        <ParticleOrbitEffect particleCount={12} radius={80} intensity={0.4} fadeOpacity={0.03} particleSize={1.5} colorRange={[140, 175]} autoColors={false} />
        <div className="hinaa-cursor-dot" aria-hidden="true" id="hinaa-cursor-dot" />
        <FullScreenAura state={controller.state} />

        <div className="hinaa-layout">
          {/* Nav Rail */}
          <NavRail active={navSection} onNavigate={handleNav} onNewChat={controller.resetConversation} onSettings={() => setSettingsOpen(true)} />
          {navSection === "tasks" || navSection === "files" ? (
            <Suspense fallback={lazyPanelFallback}><LocalProjectWorkspace active /></Suspense>
          ) : (
            <SidebarPanel
              section={sidebarExpanded}
              onClose={() => setSidebarExpanded(null)}
              onNewChat={() => { controller.resetConversation(); setSidebarExpanded(null); }}
              onStartVoice={() => { setSidebarExpanded(null); interruptPlayback(); live.start(); }}
              onOpenMemory={() => { setSidebarExpanded(null); setMemoryOpen(true); }}
              onOpenImageStudio={() => { setSidebarExpanded(null); openImageStudio(); }}
              onOpenProjects={() => { setSidebarExpanded(null); setNavSection("tasks"); }}
              onOpenSettings={() => { setSidebarExpanded(null); setSettingsOpen(true); }}
              onQuickPrompt={(prompt) => { setSidebarExpanded(null); setInput(prompt); }}
            />
          )}

          {/* Center: Avatar LEFT, Chat RIGHT */}
          <div className="layout-body">
            {/* Left: Avatar + Model Switcher */}
            <div className="avatar-pane">
              <Suspense fallback={<div style={{ display: "grid", placeItems: "center", height: "100%", color: "#94a3b8", fontSize: 12 }}>Preparing Hinaa…</div>}><AvatarPresence
                mode={avatarMode}
                state={controller.state}
                jawEnergy={playback.jawEnergy}
                speakingRef={playback.playingRef}
                visemeEvents={playback.visemeEvents}
                audioStartTimeRef={playback.audioStartTimeRef}
                modelUrl={avatarModel}
                onModeChange={changeAvatarMode}
                faceExpressions={facialSignalActive ? faceTrack.expressionsRef.current : null}
                faceBones={faceActive ? faceTrack.bonesRef.current : null}
                faceTrackingActive={faceActive}
                trackingCalibration={faceTrack.calibration}
                expressionText={latestAssistantExpressionText}
                presentation={avatarPresentation}
                companionName={companionProfiles[controller.companionId].name}
                liveStatus={{
                  active: live.active,
                  paused: live.paused,
                  detail: live.detail,
                  microphoneLevel: live.microphoneLevel,
                }}
                messages={controller.messages}
                partialTranscript={controller.partialTranscript}
                streamingText={controller.streamingText}
                onStartLive={() => { interruptPlayback(); live.start(); }}
                onStopLive={() => live.stop()}
                onPauseLive={() => live.pause()}
                onResumeLive={() => live.resume()}
              /></Suspense>
              {/* A small, direct selector: choose Hinaa, choose Classic, or add a local VRM.
                  Rejected legacy B/C assets remain absent. */}
              <div className="vrm-switcher" role="group" aria-label="Choose Hinaa avatar">
                <input
                  ref={avatarUploadRef}
                  type="file"
                  accept=".vrm,.glb,.gltf"
                  aria-label="Upload a local avatar model"
                  className="vrm-file-input"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) void importAndSelectAvatar(file);
                    event.currentTarget.value = "";
                  }}
                />
                {HINAA_AVATAR_MODELS.map((m) => (
                  <button
                    key={m.url}
                    type="button"
                    className={`vrm-pill${avatarModel === m.url ? " vrm-pill--active" : ""}`}
                    onClick={() => selectAvatarModel(m.url)}
                    title={m.label}
                    aria-label={`Use ${m.label}`}
                  >
                    {m.label}
                  </button>
                ))}
                <button
                  type="button"
                  className="vrm-pill vrm-pill--add"
                  onClick={() => avatarUploadRef.current?.click()}
                  title="Choose a local VRM file and use it in HINAA"
                  aria-label="Add a local avatar model"
                >
                  + Add avatar
                </button>
                <button
                  type="button"
                  className={`vrm-pill vrm-pill--face${faceActive ? " vrm-pill--face-active" : ""}`}
                  onClick={() => {
                    setDrawerMode("info");
                    setDrawerTitle("VSeeFace and VMC");
                    setDrawerContent(<VmcControlPanel
                      tracker={faceTrack}
                      selectedModelLabel={HINAA_AVATAR_MODELS.find((model) => model.url === avatarModel)?.label ?? "Imported HINAA avatar"}
                      selectedModelMode={avatarTrackingMode}
                      onClose={() => setDrawerOpen(false)}
                      onOpenAvatarLab={openAvatarLab}
                    />);
                    setDrawerOpen(true);
                  }}
                  title="Open VSeeFace and VMC connection controls"
                  aria-label="Open VSeeFace and VMC connection controls"
                >
                  {faceTrack.status === "connecting" ? "⏳ Connecting" :
                   faceTrack.status === "live" ? "🎭 LIVE" :
                   faceTrack.status === "test" ? "🎭 TEST" : "🎭 VSeeFace"}
                </button>
              </div>
              {avatarUploadMessage && <div className="vrm-upload-status" role="status">{avatarUploadMessage}</div>}
              <div style={{ fontSize:"0.62rem", color: faceActive ? "#15803d" : faceTrack.status === "stale" ? "#b45309" : faceTrack.status === "test" ? "#6d28d9" : faceTrack.status === "error" ? "#dc2626" : "#64748b", padding:"3px 12px 5px", textAlign:"center", lineHeight:1.4 }} aria-live="polite">
                {facialSignalActive ? "VSeeFace Live — fresh external facial channels are driving HINAA's expression layer."
                  : faceActive ? "VSeeFace Live — motion packets are fresh; waiting for supported blendshape channels before mirroring expressions."
                  : faceTrack.status === "listening" ? "VMC Listening — waiting for VSeeFace packets."
                  : faceTrack.status === "stale" ? "Tracking Stale — the avatar is returning safely to autonomous presence."
                  : faceTrack.status === "test" ? "Test Signal — diagnostic fixture only, not live camera tracking."
                  : faceTrack.status === "connecting" ? "Starting local VMC connection…"
                  : faceTrack.status === "error" ? `VMC error — ${faceTrack.error ?? "open the control panel to retry."}`
                  : "VSeeFace is disconnected — open the control panel to connect/listen."}
              </div>
            </div>

            {/* Right: Chat */}
            <main className="chat-pane">
              {/* Header */}
              <header className="app-header">
                <div className="brand-group">
                  <motion.span className="brand-mark" aria-hidden="true" animate={{ rotate: [0, 360] }} transition={{ duration: 30, repeat: Infinity, ease: "linear" }}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" /></svg>
                  </motion.span>
                  <span className="brand-name">HINAA</span>
                </div>
                <div className="header-right">
                  <span className="header-status"><span className="header-status-dot" />{stateLabels[controller.state]}</span>
                  {routing.activeMode === "cx-gateway" && <span title="CX Gateway is the active Hinaa brain" style={{ color: "#0f766e", fontSize: 11, fontWeight: 750 }}>CX Brain</span>}
                  {routing.activeMode === "claude" && <span title="Claude is the active Hinaa brain" style={{ color: "#d97706", fontSize: 11, fontWeight: 750 }}>Claude</span>}
                  {routing.reason === "recovery" && <button type="button" onClick={() => setSettingsOpen(true)} title="CX is not available locally; open settings to configure it" style={{ border: "1px solid rgba(245,158,11,.30)", borderRadius: 999, color: "#92400e", background: "rgba(254,243,199,.70)", padding: "4px 7px", cursor: "pointer", fontSize: 10, fontWeight: 750 }}>CX offline · safe mode</button>}
                  <SearchingLoader visible={searching} />
                  <SettingsTrigger onClick={() => setSettingsOpen(true)} isOpen={settingsOpen} />
                </div>
              </header>

              {/* Conversation */}
              <div className="chat-scroll">
                {agentSteps.length > 0 && <ActivityPanel steps={agentSteps} title={contextMode === "research" ? "Research workflow" : "Execution workflow"} mode={contextMode === "research" ? "research" : "execution"} />}

                {showWelcome ? (
                  <div className="welcome-center">
                    <motion.h1 className="welcome-greeting" initial={{ opacity: 0, y: 16, filter: "blur(4px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0)" }} transition={{ duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] }}>Hello</motion.h1>
                    <motion.p className="welcome-subtitle" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3, duration: 0.5 }}>Main tumhare liye ready hoon. What would you like to do?</motion.p>
                    <motion.div className="welcome-cards" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }}>
                      {[
                        { icon: "🔍", title: "Research", desc: "Search with sources", action: "research" },
                        { icon: "✨", title: "Create", desc: "Images, documents, ideas", action: "create" },
                        { icon: "💼", title: "Continue work", desc: "Projects & tasks", action: "work" },
                        { icon: "🎤", title: "Talk to HINAA", desc: "Voice conversation", action: "voice" },
                      ].map((c, i) => (
                        <motion.button type="button" key={c.action} className="welcome-card" aria-label={c.title} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6 + i * 0.08 }} onClick={() => handleWelcome(c.action)} whileHover={{ y: -2 }} whileTap={{ scale: 0.98 }}>
                          <span className="welcome-card-icon" aria-hidden="true">{c.icon}</span>
                          <span className="welcome-card-title">{c.title}</span>
                          <span className="welcome-card-desc">{c.desc}</span>
                        </motion.button>
                      ))}
                    </motion.div>
                  </div>
                ) : (
                  <TranscriptView messages={controller.messages} streamingText={controller.streamingText}
                    partialTranscript={controller.partialTranscript} companionName={companionProfiles[controller.companionId].name}
                    isThinking={controller.state === "thinking" && !controller.streamingText && !controller.partialTranscript}
                    onWelcomeAction={handleWelcome}
                    onResolveTool={controller.resolveToolRequest} />
                )}

                {actionChips.length > 0 && controller.state === "idle" && (
                  <ActionChips chips={actionChips} onChip={c => {
                    if (c.id === "src") setContextMode("research");
                    else if (c.id === "img") openImageStudio();
                    else if (c.id === "deepen") setInput("Go deeper with a researched answer and clear sources: ");
                    else if (c.id === "plan") setInput("Turn this into a clear task plan with milestones, dependencies, and approval steps: ");
                    else setInput("Continue, and ask me the most useful next question: ");
                  }} />
                )}
              </div>

              {/* Composer */}
              <div className="premium-composer-wrapper">
                <PremiumComposer value={input} onChange={setInput} onSend={() => submit()} onVoiceStart={() => { interruptPlayback(); live.start(); }}
                  onVoiceStop={() => live.stop()} onPowerUp={handlePowerUp} onImageAttach={setAttachedImage}
                  imagePreview={attachedImage}
                  isVoiceActive={live.active}
                  isGenerating={controller.state === "thinking"} disabled={controller.state !== "idle" && controller.state !== "thinking"}
                  companionName={companionProfiles[controller.companionId].name}
                  voiceFeedback={voiceReply}
                  hasReplay={playback.hasReplay}
                  muted={playback.muted}
                  onReplay={() => void playback.replay()}
                  onToggleMute={playback.toggleMute} />
              </div>
            </main>
          </div>

          {/* Context workspace */}
          <Suspense fallback={lazyPanelFallback}><ContextWorkspace mode={contextMode} onClose={() => setContextMode("hidden")} sources={contextSources} isSearching={searching} steps={agentSteps} /></Suspense>
        </div>

        {/* Overlays */}
        <Suspense fallback={null}><MemoryPanel isOpen={memoryOpen} onClose={() => setMemoryOpen(false)} /></Suspense>
        <SettingsDialog isOpen={settingsOpen} onClose={() => setSettingsOpen(false)}>
          <CompanionSwitch value={controller.companionId} onChange={id => { if (id === controller.companionId) return; if (live.active) live.stop(); controller.switchCompanion(id); }} />
          <AppearanceSettings appearance={settings.appearance} onChange={setAppearance} />
          <LanguageSettings language={settings.language} onChange={setLanguage} />
          <ProviderSettings provider={settings.provider} providers={providers} onChange={setProvider} activeMode={routing.activeMode as any} />
          <DiagnosticsSettings providers={providers} />
        </SettingsDialog>
        <HinaDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} mode={drawerMode} title={drawerTitle} side="bottom">{drawerContent}</HinaDrawer>
      </div>
    </SidebarProvider>
  );
}
