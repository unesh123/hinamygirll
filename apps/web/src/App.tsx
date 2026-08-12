import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./App.css";
import { motion } from "framer-motion";
import { TranscriptView } from "./features/chat/components/TranscriptView";
import { extractCodeBlock, isOtakuXWearTopic } from "./features/avatar/stageModes";
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

import type { PowerUp } from "./components/ui/PowerUpMentions";
import useMemory from "./features/memory/useMemory";

const AvatarPresence = lazy(() => import("./components/ui/AvatarPresence").then((module) => ({ default: module.AvatarPresence })));
const ContextWorkspace = lazy(() => import("./components/ui/ContextWorkspace").then((module) => ({ default: module.ContextWorkspace })));
const MemoryPanel = lazy(() => import("./components/ui/MemoryPanel").then((module) => ({ default: module.MemoryPanel })));
const LocalProjectWorkspace = lazy(() => import("./components/ui/LocalProjectWorkspace").then((module) => ({ default: module.LocalProjectWorkspace })));
const LocalImageStudio = lazy(() => import("./components/ui/LocalImageStudio").then((module) => ({ default: module.LocalImageStudio })));

const lazyPanelFallback = <div style={{ padding: 12, color: "#94a3b8", fontSize: 12 }}>Loading local workspace…</div>;

const AVATAR_MODEL_STORAGE_KEY = "hinaa.avatar-model";
const HINAA_AVATAR_MODELS = [
  { url: "/models/model_6164.vrm", label: "Hinaa" },
  { url: "/models/model_5447.vrm", label: "Hinaa Classic" },
] as const;
const DEFAULT_AVATAR_MODEL = HINAA_AVATAR_MODELS[0].url;

function getPersistedAvatarModel(): string {
  if (typeof window === "undefined") return DEFAULT_AVATAR_MODEL;
  try {
    const stored = window.localStorage.getItem(AVATAR_MODEL_STORAGE_KEY);
    return stored && HINAA_AVATAR_MODELS.some((model) => model.url === stored)
      ? stored
      : DEFAULT_AVATAR_MODEL;
  } catch {
    return DEFAULT_AVATAR_MODEL;
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
  const [avatarMode, setAvatarMode] = useState<PresenceMode>("portrait");
  // Use the owner-supplied local model as the preferred avatar. The procedural
  // renderer remains the safe fallback if an asset cannot load.
  const [avatarModel, setAvatarModel] = useState<string>(getPersistedAvatarModel);
  const selectAvatarModel = (modelUrl: string) => {
    if (!HINAA_AVATAR_MODELS.some((model) => model.url === modelUrl)) return;
    setAvatarModel(modelUrl);
    try {
      window.localStorage.setItem(AVATAR_MODEL_STORAGE_KEY, modelUrl);
    } catch {
      // The renderer still works when browser storage is unavailable.
    }
  };

  // VSeeFace face tracking
  const faceTrack = useVSeeFace();
  const faceActive = faceTrack.status === "active";

  const routing = useProviderRouting(settings.provider, providers);
  const controller = useCompanionController({
    routing,
    languagePolicy: settings.language.activePolicy,
  });
  useMemory();

  // Keep the first interactive paint light, then warm the local-only panels in
  // the background so opening Projects or Image Studio feels immediate.
  useEffect(() => {
    const preload = () => {
      void import("./components/ui/LocalProjectWorkspace");
      void import("./components/ui/LocalImageStudio");
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

  /* ─── Avatar mode — stays stable, no zoom changes ────── */
  useEffect(() => {
    setAvatarMode("portrait");
  }, [live.active, controller.state]);

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

  const handlePowerUp = useCallback((p: PowerUp) => {
    const map: Record<string, () => void> = {
      "search-web": () => { setContextMode("research"); setSearching(true); },
      "image-search": () => setContextMode("images"),
      "browser-navigate": () => setContextMode("browser"),
      "play-music": () => window.open("https://www.youtube.com/results?search_query=hindi+songs", "_blank", "noopener,noreferrer"),
      "remember-this": () => setMemoryOpen(true),
    };
    map[p.action]?.();
  }, []);

  const handleNav = useCallback((s: NavSection) => {
    if (s === "memory") { setMemoryOpen(v => !v); return; }
    setNavSection(s);
    if (s === "tasks" || s === "files") {
      setSidebarExpanded(null);
      return;
    }
    setSidebarExpanded(prev => prev === s ? null : s);
  }, []);

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
          { id: "strategy", label: "Plan source strategy", detail: "Selecting the best research path", status: "active" },
          { id: "synthesis", label: "Prepare concise findings", detail: "Sources stay visible and attributable", status: "pending" },
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
            <SidebarPanel section={sidebarExpanded} onClose={() => setSidebarExpanded(null)} />
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
                onModeChange={setAvatarMode}
                faceExpressions={faceActive ? faceTrack.expressions : null}
                faceBones={faceActive ? faceTrack.bones : null}
                faceTrackingActive={faceActive}
              /></Suspense>
              {/* Owner-supplied VRM choices. The previous sample B/C models are
                  intentionally excluded because they were not the preferred character. */}
              <div className="vrm-switcher" role="group" aria-label="Switch Hinaa avatar">
                {HINAA_AVATAR_MODELS.map((m) => (
                  <button
                    key={m.url}
                    type="button"
                    className={`vrm-pill${avatarModel === m.url ? " vrm-pill--active" : ""}`}
                    onClick={() => selectAvatarModel(m.url)}
                    title={m.label}
                  >
                    {m.label}
                  </button>
                ))}
                {/* VSeeFace face tracking button */}
                <button
                  type="button"
                  className={`vrm-pill vrm-pill--face${faceActive ? " vrm-pill--face-active" : ""}`}
                  onClick={() => faceActive ? faceTrack.disconnect() : faceTrack.connect()}
                  title={
                    faceActive
                      ? "🎭 VSeeFace tracking LIVE — click to stop"
                      : "🎭 Start VSeeFace tracking\n\nSetup (one time):\n1. Open VSeeFace\n2. General Settings → ✅ VMC Protocol\n3. IP: 127.0.0.1  Port: 39539\n4. Click Save & start VSeeFace\n5. Then click this button"
                  }
                >
                  {faceTrack.status === "connecting" ? "⏳ Connecting..." :
                   faceActive ? "🎭 LIVE" : "🎭 VSeeFace"}
                </button>
              </div>
              {/* VSeeFace status strip */}
              {faceTrack.status === "error" && faceTrack.error && (
                <div style={{ fontSize:"0.62rem", color:"#dc2626", padding:"3px 12px 5px", textAlign:"center", lineHeight:1.4, background:"rgba(254,226,226,0.7)", borderTop:"1px solid rgba(252,165,165,0.4)" }}>
                  ⚠️ {faceTrack.error.length > 90 ? faceTrack.error.slice(0, 90) + "…" : faceTrack.error}
                </div>
              )}
              {!faceActive && faceTrack.status === "disconnected" && (
                <div style={{ fontSize:"0.6rem", color:"#64748b", padding:"2px 12px 4px", textAlign:"center", lineHeight:1.4 }}>
                  VSeeFace → VMC Protocol → 127.0.0.1:39539 → click 🎭 VSeeFace
                </div>
              )}
              {faceActive && (
                <div style={{ fontSize:"0.6rem", color:"#15803d", padding:"2px 12px 4px", textAlign:"center", lineHeight:1.4 }}>
                  ✅ Face tracking active — expressions mirrored live
                </div>
              )}
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
          <Suspense fallback={lazyPanelFallback}><ContextWorkspace mode={contextMode} onClose={() => setContextMode("hidden")} sources={contextSources} isSearching={searching} /></Suspense>
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
