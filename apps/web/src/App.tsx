import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { SignInButton, SignUpButton, UserButton, useAuth } from "@clerk/react";
import "./App.css";
import { motion, AnimatePresence } from "framer-motion";
import { AudioLines, ListChecks, ScanFace, Search, Wand2, Sparkles } from "lucide-react";
import { AppShell } from "./design-system/layout/AppShell";
import { TalkMode, type VisualMode } from "./design-system/modes/TalkMode";
import { WorkMode } from "./design-system/modes/WorkMode";
import { OperateMode } from "./design-system/modes/OperateMode";
import { VoiceDiagnosticsDrawer } from "./features/voice/VoiceDiagnosticsDrawer";
import { VoiceLab } from "./features/voice/VoiceLab";
import { TranscriptView } from "./features/chat/components/TranscriptView";
import { extractCodeBlock, isOtakuXWearTopic } from "./features/avatar/stageModes";
import {
  type AvatarPresentation,
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
import { AutomationSettings } from "./features/settings/sections/AutomationSettings";
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
const AvatarLab = lazy(() => import("./components/ui/AvatarLab").then((module) => ({ default: module.AvatarLab })));
const HumanizerStudio = lazy(() => import("./features/tools/HumanizerStudio").then((module) => ({ default: module.HumanizerStudio })));

function ClerkAuthWrapper() {
  const { isSignedIn } = useAuth();
  return (
    <>
      <ClerkFetchInterceptor />
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginLeft: '8px' }}>
        {isSignedIn ? (
          <UserButton />
        ) : (
          <>
            <SignInButton mode="modal" />
            <SignUpButton mode="modal" />
          </>
        )}
      </div>
    </>
  );
}

function ClerkFetchInterceptor() {
  const { getToken } = useAuth();
  useEffect(() => {
    const originalFetch = window.fetch;
    window.fetch = async (...args) => {
      let [resource, config] = args;
      const url = typeof resource === 'string' ? resource : resource instanceof URL ? resource.toString() : (resource as Request).url;
      if (url.startsWith('/api') || url.startsWith('/v1') || url.startsWith('http://localhost:8000/v1')) {
        try {
          const token = await getToken();
          if (token) {
            config = config || {};
            config.headers = {
              ...config.headers,
              Authorization: `Bearer ${token}`
            };
          }
        } catch (e) {
          console.error("Failed to get Clerk token", e);
        }
      }
      return originalFetch(resource, config);
    };
    return () => {
      window.fetch = originalFetch;
    };
  }, [getToken]);
  return null;
}

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

/* ─── SpokenText derivation ───────────────────────────── */
/**
 * Derive a natural spoken form from displayText when the model omits spokenText.
 * This is a FALLBACK — the primary source is AssistantTurnPlan.spokenText.
 *
 * Rules:
 * - Preserve sentence meaning
 * - Do not speak raw URLs, markdown, code, citation IDs, or table syntax
 * - Preserve Devanagari, Hindi, and mixed-language text
 * - Do not remove decimal points from numbers or corrupt abbreviations
 * - Cut at sentence boundaries, not arbitrary character boundaries
 * - For long content, speak a short summary
 * - Record when fallback derivation was used (via wasFallbackDerived)
 */
let wasFallbackDerived = false;
export function deriveSpokenText(displayText: string): string {
  if (!displayText) return "";
  wasFallbackDerived = true;
  const originalLength = displayText.length;
  let spoken = displayText
    // Remove fenced code blocks (``` ... ```)
    .replace(/```[\s\S]*?```/g, "")
    // Remove inline code but keep the content
    .replace(/`([^`]+)`/g, "$1")
    // Remove markdown links, keep the link text
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    // Remove bare URLs
    .replace(/https?:\/\/\S+/g, "")
    // Remove reference-style citation links like [1] [2] [^note]
    .replace(/\[\^[a-zA-Z0-9]+\]/g, "")
    .replace(/\[\d+\]/g, "")
    // Remove headings (# ## ###)
    .replace(/^#{1,6}\s+/gm, "")
    // Remove bold/italic markers but keep content
    .replace(/[*_]{1,3}/g, "")
    // Remove table rows (| col | col |)
    .replace(/^\|.*\|\s*$/gm, "")
    // Remove table separator rows (|---|---|)
    .replace(/^\|?\s*[-:]+\s*(\|\s*[-:]+\s*)*\|?\s*$/gm, "")
    // Remove horizontal rules (--- ***)
    .replace(/^[-*_]{3,}\s*$/gm, "")
    // Remove blockquote markers (>
    .replace(/^>\s*/gm, "")
    // Remove image markdown ![alt](url)
    .replace(/!\[[^\]]*\]\([^)]+\)/g, "")
    // Remove HTML tags
    .replace(/<[^>]+>/g, "")
    // Collapse whitespace
    .replace(/\s+/g, " ")
    .trim();
  // Truncate to a natural speaking length with sentence-aware cutting
  const MAX_SPOKEN_LENGTH = 280;
  const LOOKAHEAD_LIMIT = 40; // allow looking a few words past the target
  if (spoken.length > MAX_SPOKEN_LENGTH) {
    // Search for the last sentence boundary in a window around the target length
    const searchEnd = Math.min(spoken.length, MAX_SPOKEN_LENGTH + LOOKAHEAD_LIMIT);
    const searchWindow = spoken.substring(0, searchEnd);
    const lastPeriod = searchWindow.lastIndexOf(".");
    const lastExcl = searchWindow.lastIndexOf("!");
    const lastQ = searchWindow.lastIndexOf("?");
    const lastColon = searchWindow.lastIndexOf(":");
    const bestCut = Math.max(lastPeriod, lastExcl, lastQ, lastColon);
    if (bestCut > 80) {
      // Cut at sentence boundary — keep the sentence-ending punctuation for natural speech
      spoken = searchWindow.substring(0, bestCut + 1).trimEnd();
      // Add continuation hint if there's more meaningful content remaining
      const remainingAfterCut = originalLength - (bestCut + 1);
      if (remainingAfterCut > 20) {
        spoken += " Details are available in the chat.";
      }
    } else {
      // No good sentence boundary — cut at word boundary
      const lastSpace = searchWindow.lastIndexOf(" ");
      spoken = (lastSpace > 100 ? searchWindow.substring(0, lastSpace) : searchWindow).trimEnd() + "...";
    }
  }
  return spoken;
}

/** Check if the last spokenText was derived from displayText (fallback). */
export function wasSpokenTextDerived(): boolean {
  return wasFallbackDerived;
}

/* ─── Main App ─────────────────────────────────────────── */
export default function App() {
  const playback = useAudioPlayback();
  const providers = useProviders();
  const { settings, setAppearance, setLanguage, setProvider, setAutomation } = useSettings();
  useSettingsPersistence(settings);

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(false);
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
  // Audio unlock state: AudioContext may be suspended by browser autoplay policy.
  // When blocked, we show an unlock button so the user can tap to resume audio.
  const [audioBlocked, setAudioBlocked] = useState(false);
  const audioBlockedRef = useRef(false);
  useEffect(() => {
    const checkAudioContext = () => {
      const ctx = (window as any).__hinaaAudioCtx as AudioContext | undefined;
      if (ctx && ctx.state === "suspended" && !audioBlockedRef.current) {
        audioBlockedRef.current = true;
        setAudioBlocked(true);
      }
    };
    // Check periodically (low frequency)
    const interval = setInterval(checkAudioContext, 2000);
    return () => clearInterval(interval);
  }, []);
  const unlockAudio = useCallback(async () => {
    try {
      const ctx = (window as any).__hinaaAudioCtx as AudioContext | undefined;
      if (ctx && ctx.state === "suspended") {
        await ctx.resume();
      }
      audioBlockedRef.current = false;
      setAudioBlocked(false);
    } catch {
      // AudioContext unlock failed — browser may require a different gesture
    }
  }, []);

  // ─── Sakura OS mode state ──────────────────────────────
  const [sakuraView, setSakuraView] = useState<"talk" | "work" | "operate">("work");
  const [visualMode, setVisualMode] = useState<VisualMode>(() => {
    try {
      return (window.localStorage.getItem("hinaa-visual-mode") as VisualMode) || "vrm";
    } catch { return "vrm"; }
  });
  const changeVisualMode = (mode: VisualMode) => {
    setVisualMode(mode);
    try { window.localStorage.setItem("hinaa-visual-mode", mode); } catch {}
  };

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
  const selectAvatarModel = (modelUrl: string) => {
    if (!isSelectableAvatarUrl(modelUrl)) return;
    setAvatarModel(modelUrl);
    setAvatarMode(getPersistedAvatarCamera(modelUrl));
    setAvatarPresentation(getPersistedAvatarPresentation(modelUrl));
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
      selectAvatarModel(body.asset.browserUrl);
      setAvatarUploadMessage(`${body.asset.displayName} is selected. HINAA applied the safe relaxed pose and facing preset; use Avatar Lab only if this model needs a one-click correction.`);
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
    autoRunTools: settings.automation.autoRunTools,
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
      if (!result || !plan) return;
      // Derive spokenText from displayText when the model omits it.
      // Strip markdown, URLs, code blocks, and keep it under 200 chars.
      const spoken = plan.spokenText?.trim() || deriveSpokenText(plan.displayText);

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

      // Track TTS terminal state to prevent duplicate fallback.
      // Backend has a 10s TTS timeout; frontend has 12s.
      // Once one fires, the other must not start another voice.
      let ttsTerminalReached = false;
      const markTtsTerminal = () => { ttsTerminalReached = true; };

      try {
        updateSession("buffering", { provider: ttsMode });
        // TTS with 12-second timeout — falls back to browser speech on timeout
        const ttsController = new AbortController();
        const ttsTimeout = setTimeout(() => {
          if (!ttsTerminalReached) ttsController.abort();
        }, 12_000);
        const speech = await synthesizeSpeech(
          spoken,
          controller.companionId,
          ttsMode,
          ttsController.signal,
        );
        clearTimeout(ttsTimeout);
        if (activePlaybackId.current !== playbackId) return;
        if (/placeholder|mock/i.test(speech.provider)) {
          markTtsTerminal();
          await startBrowserFallback(
            "The selected mode has no intelligible server voice yet, so Hinaa is using your device voice.",
          );
          return;
        }
        await playback.play(speech.blob, spoken);
        markTtsTerminal();
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
        // Prevent duplicate fallback — only one terminal outcome per turn
        if (ttsTerminalReached) return;
        markTtsTerminal();
        // If TTS timed out or failed, try browser speech as fallback
        const reason = error instanceof Error ? error.message : "Cloud voice is unavailable";
        if (reason.includes("aborted") || reason.includes("timeout")) {
          await startBrowserFallback(
            "Voice synthesis took too long. Using your device voice instead.",
          );
        } else {
          await startBrowserFallback(
            `${reason}. Using the device voice instead.`,
          );
        }
      }
    })();
  }, [input, live.active, controller, playback, attachedImage, interruptPlayback]);

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
      "open-humanizer": openHumanizerStudio,
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

  const openHumanizerStudio = () => {
    setDrawerMode("info");
    setDrawerTitle("Text Humanizer Studio");
    setDrawerContent(<Suspense fallback={lazyPanelFallback}><HumanizerStudio onClose={() => setDrawerOpen(false)} /></Suspense>);
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

  // Map existing CompanionState to the modes' expected types
  const mapCompanionState = (s: CompanionState): "idle" | "listening" | "thinking" | "speaking" | "interrupted" | "error" => s;

  // Voice Lab — developer-only diagnostic route
  const isVoiceLab = typeof window !== "undefined" && window.location.pathname === "/dev/voice-lab";
  if (isVoiceLab) return <VoiceLab />;

  return (
    <SidebarProvider defaultExpanded={false}>
      <div className="hinaa-shell">
      {/* ─── Sakura OS (Canonical) ──────────────────────────── */}
          <AppShell>
            {/* Mode navigation tabs */}
            <div style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "var(--space-1)",
              padding: "var(--space-2) var(--space-4)",
              borderBottom: "1px solid var(--border-subtle)",
              background: "var(--bg-secondary)",
              flexShrink: 0,
            }}>
              {(["talk", "work", "operate"] as const).map((mode) => (
                <motion.button
                  key={mode}
                  onClick={() => setSakuraView(mode)}
                  whileTap={{ scale: 0.95 }}
                  style={{
                    padding: "var(--space-1-5) var(--space-4)",
                    borderRadius: "var(--radius-pill)",
                    border: "none",
                    background: sakuraView === mode ? "var(--accent-pale)" : "transparent",
                    color: sakuraView === mode ? "var(--accent)" : "var(--text-tertiary)",
                    fontSize: "var(--text-sm)",
                    fontWeight: sakuraView === mode ? 600 : 500,
                    fontFamily: "var(--font-body)",
                    cursor: "pointer",
                    textTransform: "capitalize",
                  }}
                  aria-pressed={sakuraView === mode}
                >
                  {mode}
                </motion.button>
              ))}
            </div>

            {/* Mode content */}
            {sakuraView === "talk" && (
              <TalkMode
                companionState={mapCompanionState(controller.state)}
                companionName={companionProfiles[controller.companionId].name}
                visualMode={visualMode}
                onVisualModeChange={changeVisualMode}
                isVoiceActive={live.active}
                isPaused={live.paused}
                voiceDetail={live.detail}
                microphoneLevel={live.microphoneLevel}
                onStartVoice={() => { interruptPlayback(); live.start(); }}
                onStopVoice={() => live.stop()}
                onPauseVoice={() => live.pause()}
                onResumeVoice={() => live.resume()}
                partialTranscript={controller.partialTranscript}
                streamingText={controller.streamingText}
                avatarModel={avatarModel}
                avatarMode={avatarMode}
                jawEnergy={playback.jawEnergy}
                speakingRef={playback.playingRef}
                visemeEvents={playback.visemeEvents}
                audioStartTimeRef={playback.audioStartTimeRef}
                faceExpressions={facialSignalActive ? faceTrack.expressionsRef.current : null}
                faceBones={faceActive ? faceTrack.bonesRef.current : null}
                faceTrackingActive={faceActive}
                trackingCalibration={faceTrack.calibration}
                expressionText={latestAssistantExpressionText ?? ""}
                avatarPresentation={avatarPresentation}
                messages={controller.messages}
                onOpenAvatarLab={openAvatarLab}
                onToggleFullscreen={() => {}}
                onTypeInstead={() => setSakuraView("work")}
                isMuted={playback.muted}
                onToggleMute={playback.toggleMute}
                onReplay={() => void playback.replay()}
                hasReplay={playback.hasReplay}
                diagnostics={live.diagnostics}
                onManualCommit={live.manualCommit}
                onToggleDiagnostics={() => setDiagnosticsOpen((v) => !v)}
              />
            )}

            {sakuraView === "work" && (
              <WorkMode
                companionState={mapCompanionState(controller.state)}
                messages={controller.messages}
                streamingText={controller.streamingText}
                partialTranscript={controller.partialTranscript}
                isThinking={controller.state === "thinking" && !controller.streamingText && !controller.partialTranscript}
                input={input}
                onInputChange={setInput}
                onSend={() => submit()}
                onStop={() => controller.stop()}
                disabled={controller.state !== "idle" && controller.state !== "thinking"}
                isVoiceActive={live.active}
                onStartVoice={() => { interruptPlayback(); live.start(); }}
                onStopVoice={() => live.stop()}
                voiceFeedback={voiceReply}
                powerUps={[]}
                onPowerUpToggle={() => {}}
                onResolveTool={controller.resolveToolRequest}
                autoRunTools={settings.automation.autoRunTools}
                agentSteps={agentSteps}
                onWelcomeAction={handleWelcome}
                attachedImage={attachedImage}
                onImageAttach={setAttachedImage}
              />
            )}

            {sakuraView === "operate" && (
              <OperateMode />
            )}
          </AppShell>

        {/* Audio unlock overlay — shows when AudioContext is suspended by browser autoplay policy */}
        <AnimatePresence>
          {audioBlocked && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 20 }}
              style={{
                position: "fixed",
                bottom: 80,
                left: "50%",
                transform: "translateX(-50%)",
                zIndex: 2000,
                background: "var(--accent-pale)",
                border: "1px solid var(--accent)",
                borderRadius: "var(--radius-lg)",
                padding: "var(--space-3) var(--space-5)",
                display: "flex",
                alignItems: "center",
                gap: "var(--space-3)",
                boxShadow: "var(--shadow-lg)",
                cursor: "pointer",
              }}
              onClick={unlockAudio}
              role="button"
              aria-label="Enable HINAA voice"
            >
              <span style={{ fontSize: 20 }}>🔊</span>
              <span style={{ fontFamily: "var(--font-body)", color: "var(--text-primary)", fontSize: "var(--text-sm)", fontWeight: 500 }}>
                Tap to enable HINAA's voice
              </span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Overlays */}
        <Suspense fallback={null}><MemoryPanel isOpen={memoryOpen} onClose={() => setMemoryOpen(false)} /></Suspense>
        <SettingsDialog isOpen={settingsOpen} onClose={() => setSettingsOpen(false)}>
          <AppearanceSettings appearance={settings.appearance} onChange={setAppearance} />
          <LanguageSettings language={settings.language} onChange={setLanguage} />
          <ProviderSettings provider={settings.provider} providers={providers} onChange={setProvider} activeMode={routing.activeMode as any} />
          <AutomationSettings automation={settings.automation} onChange={setAutomation} />
          <DiagnosticsSettings providers={providers} />
        </SettingsDialog>
        <HinaDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} mode={drawerMode} title={drawerTitle} side="bottom">{drawerContent}</HinaDrawer>
        <VoiceDiagnosticsDrawer
          isOpen={diagnosticsOpen}
          onClose={() => setDiagnosticsOpen(false)}
          data={live.diagnostics}
          onManualCommit={live.manualCommit}
          isListening={live.active}
        />
      </div>
    </SidebarProvider>
  );
}
