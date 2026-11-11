import React, { Suspense, useEffect, useState } from "react";
import { HinaDrawer } from "../lightswind/Drawer";
import type { useLiveVision } from "../../features/vision/useLiveVision";

const SettingsV6 = React.lazy(() => import("../../features/settings/SettingsV6").then(m => ({ default: m.SettingsV6 })));
const VoiceDiagnosticsDrawer = React.lazy(() => import("../../features/voice/VoiceDiagnosticsDrawer").then(m => ({ default: m.VoiceDiagnosticsDrawer })));
const TerminalHandsDrawer = React.lazy(() => import("../../features/terminal/TerminalHandsDrawer").then(m => ({ default: m.TerminalHandsDrawer })));
const DesktopWalkingPet = React.lazy(() => import("../../features/desktop/DesktopWalkingPet").then(m => ({ default: m.DesktopWalkingPet })));

// Do not import or mount panels until needed. Keep visited panels mounted so
// closing a drawer preserves drafts, terminal history and exit animations.
function DeferredPanel({ open, children }: { open: boolean; children: React.ReactNode }) {
  const [visited, setVisited] = useState(open);
  useEffect(() => { if (open) setVisited(true); }, [open]);
  if (!open && !visited) return null;
  return <Suspense fallback={open ? <div role="status" className="overlay-loading">Loading panel…</div> : null}>{children}</Suspense>;
}

// Lazy-loaded heavy modal overlays
const MemoryPanel = React.lazy(() =>
  import("../ui/MemoryPanel").then((m) => ({ default: m.MemoryPanel }))
);
const MusicMiniPlayer = React.lazy(() =>
  import("../ui/MusicMiniPlayer").then((m) => ({ default: m.MusicMiniPlayer }))
);
const VisualDocumentExplainer = React.lazy(() =>
  import("../../features/explainer/VisualDocumentExplainer").then((m) => ({
    default: m.VisualDocumentExplainer,
  }))
);

export interface AppOverlaysProps {
  memoryOpen: boolean;
  setMemoryOpen: (open: boolean) => void;

  settingsOpen: boolean;
  setSettingsOpen: (open: boolean) => void;
  settings: any;
  setAppearance: (appearance: any) => void;
  setLanguage: (lang: any) => void;
  setProvider: (prov: any) => void;
  setAutomation: (auto: any) => void;
  providers: any;
  activeMode: any;
  isMuted: boolean;
  onToggleMute: () => void;

  drawerOpen: boolean;
  setDrawerOpen: (open: boolean) => void;
  drawerMode: any;
  drawerTitle: string;
  drawerContent: React.ReactNode;

  diagnosticsOpen: boolean;
  setDiagnosticsOpen: (open: boolean) => void;
  diagnosticsData: any;
  onManualCommit?: () => void;
  isListening: boolean;

  musicPlayerOpen: boolean;
  setMusicPlayerOpen: (open: boolean) => void;
  contextMode: string;
  setContextMode: (mode: any) => void;

  terminalOpen: boolean;
  setTerminalOpen: (open: boolean) => void;
  terminalInitialCmd: string;

  showDesktopPet: boolean;
  setShowDesktopPet: (show: boolean) => void;
  isMobile: boolean;
  setIsWalking: (walking: boolean) => void;
  isSpeaking: boolean;
  isThinking: boolean;
  jawEnergy: number;
  onStopSpeaking: () => void;
  isLiveVoiceActive: boolean;
  onToggleLiveVoice: () => void;
  streamingText: string | null;
  lastAssistantText: string | null;
  liveVision: Pick<ReturnType<typeof useLiveVision>, "observeScreen">;

  explainerOpen: boolean;
  setExplainerOpen: (open: boolean) => void;
}

export function AppOverlays({
  memoryOpen,
  setMemoryOpen,
  settingsOpen,
  setSettingsOpen,
  settings,
  setAppearance,
  setLanguage,
  setProvider,
  setAutomation,
  providers,
  activeMode,
  isMuted,
  onToggleMute,
  drawerOpen,
  setDrawerOpen,
  drawerMode,
  drawerTitle,
  drawerContent,
  diagnosticsOpen,
  setDiagnosticsOpen,
  diagnosticsData,
  onManualCommit,
  isListening,
  musicPlayerOpen,
  setMusicPlayerOpen,
  contextMode,
  setContextMode,
  terminalOpen,
  setTerminalOpen,
  terminalInitialCmd,
  showDesktopPet,
  setShowDesktopPet,
  isMobile,
  setIsWalking,
  isSpeaking,
  isThinking,
  jawEnergy,
  onStopSpeaking,
  isLiveVoiceActive,
  onToggleLiveVoice,
  streamingText,
  lastAssistantText,
  liveVision,
  explainerOpen,
  setExplainerOpen,
}: AppOverlaysProps) {
  return (
    <>
      <DeferredPanel open={memoryOpen}>
        <MemoryPanel isOpen={memoryOpen} onClose={() => setMemoryOpen(false)} />
      </DeferredPanel>

      <DeferredPanel open={settingsOpen}>
      <SettingsV6
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        settings={settings}
        setAppearance={setAppearance}
        setLanguage={setLanguage}
        setProvider={setProvider}
        setAutomation={setAutomation}
        providers={providers}
        activeMode={activeMode}
        isMuted={isMuted}
        onToggleMute={onToggleMute}
      />
      </DeferredPanel>

      <HinaDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        mode={drawerMode}
        title={drawerTitle}
        side="bottom"
      >
        {drawerContent}
      </HinaDrawer>

      <DeferredPanel open={diagnosticsOpen}>
      <VoiceDiagnosticsDrawer
        isOpen={diagnosticsOpen}
        onClose={() => setDiagnosticsOpen(false)}
        data={diagnosticsData}
        onManualCommit={onManualCommit}
        isListening={isListening}
      />
      </DeferredPanel>

      <DeferredPanel open={musicPlayerOpen || contextMode === "music"}>
        <MusicMiniPlayer
          isOpen={musicPlayerOpen || contextMode === "music"}
          onClose={() => {
            setMusicPlayerOpen(false);
            if (contextMode === "music") setContextMode("hidden");
          }}
        />
      </DeferredPanel>

      <DeferredPanel open={terminalOpen}>
      <TerminalHandsDrawer
        isOpen={terminalOpen}
        onClose={() => setTerminalOpen(false)}
        initialCommand={terminalInitialCmd}
      />
      </DeferredPanel>

      {showDesktopPet && !isMobile && (
        <Suspense fallback={null}>
        <DesktopWalkingPet
          isSpeaking={isSpeaking}
          isThinking={isThinking}
          jawEnergy={jawEnergy}
          onStopSpeaking={onStopSpeaking}
          isLiveVoiceActive={isLiveVoiceActive}
          onToggleLiveVoice={onToggleLiveVoice}
          streamingText={streamingText}
          lastAssistantText={lastAssistantText}
          onObserveScreen={async () => {
            try {
              const res = await liveVision.observeScreen(
                "Observe active windows and check my focus status"
              );
              return res.ok && res.observation?.trim()
                ? res.observation
                : "I couldn't observe your screen. Check screen sharing and try again.";
            } catch {
              return "Screen observation failed. Please try again.";
            }
          }}
          onOpenTasks={() => {
            window.dispatchEvent(new CustomEvent("hinaa:open-dev-tasks"));
          }}
          onOpenExplainer={() => setExplainerOpen(true)}
          onClose={() => {
            setShowDesktopPet(false);
            setIsWalking(false);
            try {
              localStorage.setItem("hinaa-desktop-pet-active", "false");
            } catch {}
          }}
        />
        </Suspense>
      )}

      <DeferredPanel open={explainerOpen}>
        <VisualDocumentExplainer
          isOpen={explainerOpen}
          onClose={() => setExplainerOpen(false)}
          onSpeakExplanation={(text) => {
            if (typeof window !== "undefined" && "speechSynthesis" in window) {
              try {
                window.speechSynthesis.cancel();
                const utter = new SpeechSynthesisUtterance(text);
                utter.rate = 1.05;
                window.speechSynthesis.speak(utter);
              } catch {}
            }
          }}
          isSpeaking={isSpeaking}
        />
      </DeferredPanel>
    </>
  );
}
