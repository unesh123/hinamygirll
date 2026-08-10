import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./App.css";
import { motion } from "framer-motion";
import { TranscriptView } from "./features/chat/components/TranscriptView";
import { extractCodeBlock, isOtakuXWearTopic } from "./features/avatar/stageModes";
import { FullScreenAura } from "./components/ui/FullScreenAura";
import { SearchingLoader } from "./components/ui/SearchingLoader";
import { PremiumComposer } from "./components/ui/PremiumComposer";
import ParticleOrbitEffect from "./components/lightswind/ParticleOrbitEffect";
import { AvatarPresence, type PresenceMode } from "./components/ui/AvatarPresence";
import { HinaDrawer } from "./components/lightswind/Drawer";
import { SidebarProvider } from "./components/lightswind/Sidebar";
import { synthesizeSpeech } from "./features/audio/api";
import { useAudioPlayback } from "./features/audio/useAudioPlayback";
import { useLiveConversation } from "./features/audio/useLiveConversation";
import { companionProfiles, type CompanionId, type CompanionState } from "./features/companion/types";
import { useCompanionController } from "./features/companion/useCompanionController";
import { useProviders } from "./features/providers/hooks/useProviders";
import { useProviderRouting } from "./features/providers/hooks/useProviderRouting";
import { SettingsDialog, SettingsTrigger, useSettings, useSettingsPersistence } from "./features/settings";
import { AppearanceSettings } from "./features/settings/sections/AppearanceSettings";
import { ProviderSettings } from "./features/settings/sections/ProviderSettings";
import { DiagnosticsSettings } from "./features/settings/sections/DiagnosticsSettings";
import { NavRail, type NavSection } from "./components/ui/NavRail";
import { ActivityPanel, type AgentStep } from "./components/ui/ActivityPanel";
import { ActionChips, type ActionChip } from "./components/ui/ActionChips";
import { ContextWorkspace, type ContextMode } from "./components/ui/ContextWorkspace";
import { SidebarPanel } from "./components/ui/SidebarPanel";
import { MemoryPanel } from "./components/ui/MemoryPanel";
import type { PowerUp } from "./components/ui/PowerUpMentions";
import useMemory from "./features/memory/useMemory";

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
  const { settings, setAppearance, setProvider } = useSettings();
  useSettingsPersistence(settings);

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState<"info" | "image" | "web" | "music" | "slides" | "code">("info");
  const [drawerTitle, setDrawerTitle] = useState("");
  const [drawerContent, setDrawerContent] = useState<React.ReactNode>(null);
  const [input, setInput] = useState("");
  const [searching, setSearching] = useState(false);
  const [attachedImage, setAttachedImage] = useState<string | null>(null);

  const [navSection, setNavSection] = useState<NavSection>("chat");
  const [sidebarExpanded, setSidebarExpanded] = useState<NavSection | null>(null);
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [contextMode, setContextMode] = useState<ContextMode>("hidden");
  const [agentSteps, setAgentSteps] = useState<AgentStep[]>([]);
  const [actionChips, setActionChips] = useState<ActionChip[]>([]);
  const [contextSources] = useState<any[]>([]);
  const [avatarMode, setAvatarMode] = useState<PresenceMode>("portrait");

  const prevMessageCount = useRef(0);
  const routing = useProviderRouting(settings.provider, providers);
  const controller = useCompanionController({ routing });
  useMemory();

  const live = useLiveConversation({ controller, playback, calibration: "natural", outputMode: "headphones", languageMode: "auto" });

  /* ─── Avatar mode — stays stable, no zoom changes ────── */
  useEffect(() => {
    setAvatarMode("portrait");
  }, [live.active, controller.state]);

  /* ─── Submit ─────────────────────────────────────────── */
  const submit = useCallback((event?: any) => {
    if (event && "preventDefault" in event) event.preventDefault();
    if ((!input.trim() && !attachedImage) || live.active) return;
    const text = input || (attachedImage ? "Look at this image" : "");
    const imageData = attachedImage;
    setInput("");
    setAttachedImage(null);
    void (async () => {
      const result = await controller.sendText(text + (imageData ? " [image attached]" : ""));
      const spoken = result?.plan?.spokenText ?? result?.plan?.displayText;
      if (!spoken || (controller.routing.activeMode ?? "mock") === "mock") return;
      try { const s = await synthesizeSpeech(spoken, controller.companionId, controller.routing.activeMode ?? "mock", new AbortController().signal); await playback.play(s.blob); } catch {}
    })();
  }, [input, live.active, controller, playback, attachedImage]);

  const handlePowerUp = useCallback((p: PowerUp) => {
    const map: Record<string, () => void> = {
      "search-web": () => { setContextMode("research"); setSearching(true); },
      "image-search": () => setContextMode("images"),
      "browser-navigate": () => setContextMode("browser"),
      "play-music": () => window.open("https://www.youtube.com/results?search_query=hindi+songs", "_blank"),
      "remember-this": () => setMemoryOpen(true),
    };
    map[p.action]?.();
  }, []);

  const handleNav = useCallback((s: NavSection) => {
    if (s === "memory") { setMemoryOpen(v => !v); return; }
    setNavSection(s); setSidebarExpanded(prev => prev === s ? null : s);
  }, []);

  const handleWelcome = (action: string) => {
    if (action === "voice") live.start();
    else if (action === "research") setInput("Search for: ");
    else if (action === "create") setInput("Help me create: ");
  };

  /* ─── YouTube auto-open ──────────────────────────────── */
  useEffect(() => {
    const msgs = controller.messages; if (msgs.length <= prevMessageCount.current) return;
    prevMessageCount.current = msgs.length;
    const last = msgs[msgs.length - 1]; if (last?.role !== "assistant") return;
    const yt = extractYouTubeIntent(last.text); if (yt) window.open(yt, "_blank", "noopener,noreferrer");
  }, [controller.messages]);

  /* ─── Agent steps ────────────────────────────────────── */
  useEffect(() => {
    if (controller.state === "thinking") {
      const lu = [...controller.messages].reverse().find(m => m.role === "user")?.text?.toLowerCase() ?? "";
      if (/search|find|research|look up/i.test(lu)) {
        setContextMode("research"); setSearching(true);
        setAgentSteps([{ id: "u", label: "Understanding", status: "done" }, { id: "s", label: "Searching", status: "active" }, { id: "a", label: "Preparing answer", status: "pending" }]);
        setTimeout(() => setSearching(false), 3000);
      } else setAgentSteps([{ id: "u", label: "Understanding", status: "done" }, { id: "p", label: "Processing", status: "active" }]);
    } else if (controller.state === "speaking" || controller.state === "idle") {
      setAgentSteps(prev => prev.map(s => ({ ...s, status: "done" as const })));
      const t = setTimeout(() => setAgentSteps([]), 3000); return () => clearTimeout(t);
    }
  }, [controller.state, controller.messages]);

  /* ─── Action chips ───────────────────────────────────── */
  useEffect(() => {
    if (controller.state !== "idle") return;
    const msgs = controller.messages; if (msgs.length === 0) return;
    const last = msgs[msgs.length - 1]; if (last?.role !== "assistant") return;
    const txt = last.text.toLowerCase(); const chips: ActionChip[] = [];
    if (/search|source|found/i.test(txt)) chips.push({ id: "src", label: "Sources", icon: "search" });
    if (/image|photo/i.test(txt)) chips.push({ id: "img", label: "Images", icon: "image" });
    if (/code|```/i.test(txt)) chips.push({ id: "code", label: "Explain", icon: "book" });
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
          <NavRail active={navSection} onNavigate={handleNav} onNewChat={() => window.location.reload()} onSettings={() => setSettingsOpen(true)} />
          <SidebarPanel section={sidebarExpanded} onClose={() => setSidebarExpanded(null)} />

          {/* Center: Avatar LEFT, Chat RIGHT */}
          <div className="layout-body">
            {/* Left: Avatar */}
            <div className="avatar-pane">
              <AvatarPresence
                mode={avatarMode}
                state={controller.state}
                jawEnergy={playback.jawEnergy}
                modelUrl="/models/hinaa.vrm"
                onModeChange={setAvatarMode}
              />
            </div>

            {/* Right: Chat */}
            <div className="chat-pane">
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
                  <SearchingLoader visible={searching} />
                  <SettingsTrigger onClick={() => setSettingsOpen(true)} isOpen={settingsOpen} />
                </div>
              </header>

              {/* Conversation */}
              <div className="chat-scroll">
                {agentSteps.length > 0 && <ActivityPanel steps={agentSteps} title="Working on it" />}

                {showWelcome ? (
                  <div className="welcome-center">
                    <motion.h1 className="welcome-greeting" initial={{ opacity: 0, y: 16, filter: "blur(4px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0)" }} transition={{ duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94] }}>Hello, Unesh</motion.h1>
                    <motion.p className="welcome-subtitle" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3, duration: 0.5 }}>Main tumhare liye ready hoon. What would you like to do?</motion.p>
                    <motion.div className="welcome-cards" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }}>
                      {[
                        { icon: "🔍", title: "Research", desc: "Search with sources", action: "research" },
                        { icon: "✨", title: "Create", desc: "Images, documents, ideas", action: "create" },
                        { icon: "💼", title: "Continue work", desc: "Projects & tasks", action: "work" },
                        { icon: "🎤", title: "Talk to HINAA", desc: "Voice conversation", action: "voice" },
                      ].map((c, i) => (
                        <motion.div key={c.action} className="welcome-card" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6 + i * 0.08 }} onClick={() => handleWelcome(c.action)} whileHover={{ y: -2 }} whileTap={{ scale: 0.98 }}>
                          <div className="welcome-card-icon">{c.icon}</div>
                          <div className="welcome-card-title">{c.title}</div>
                          <div className="welcome-card-desc">{c.desc}</div>
                        </motion.div>
                      ))}
                    </motion.div>
                  </div>
                ) : (
                  <TranscriptView messages={controller.messages} streamingText={controller.streamingText}
                    partialTranscript={controller.partialTranscript} companionName={companionProfiles[controller.companionId].name}
                    isThinking={controller.state === "thinking" && !controller.streamingText && !controller.partialTranscript}
                    onWelcomeAction={handleWelcome} />
                )}

                {actionChips.length > 0 && controller.state === "idle" && (
                  <ActionChips chips={actionChips} onChip={c => {
                    if (c.id === "src") setContextMode("research"); else if (c.id === "img") setContextMode("images"); else setInput((c.label || "") + ": ");
                  }} />
                )}
              </div>

              {/* Composer */}
              <div className="premium-composer-wrapper">
                <PremiumComposer value={input} onChange={setInput} onSend={() => submit()} onVoiceStart={() => live.start()}
                  onVoiceStop={() => live.stop()} onPowerUp={handlePowerUp} onImageAttach={setAttachedImage}
                  imagePreview={attachedImage}
                  isVoiceActive={live.active}
                  isGenerating={controller.state === "thinking"} disabled={controller.state !== "idle" && controller.state !== "thinking"}
                  companionName={companionProfiles[controller.companionId].name} />
              </div>
            </div>
          </div>

          {/* Context workspace */}
          <ContextWorkspace mode={contextMode} onClose={() => setContextMode("hidden")} sources={contextSources} isSearching={searching} />
        </div>

        {/* Overlays */}
        <MemoryPanel isOpen={memoryOpen} onClose={() => setMemoryOpen(false)} />
        <SettingsDialog isOpen={settingsOpen} onClose={() => setSettingsOpen(false)}>
          <CompanionSwitch value={controller.companionId} onChange={id => { if (id === controller.companionId) return; if (live.active) live.stop(); controller.switchCompanion(id); }} />
          <AppearanceSettings appearance={settings.appearance} onChange={setAppearance} />
          <ProviderSettings provider={settings.provider} providers={providers} onChange={setProvider} activeMode={routing.activeMode as any} />
          <DiagnosticsSettings providers={providers} />
        </SettingsDialog>
        <HinaDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} mode={drawerMode} title={drawerTitle} side="bottom">{drawerContent}</HinaDrawer>
      </div>
    </SidebarProvider>
  );
}
