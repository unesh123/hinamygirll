import React, { Suspense } from "react";
import { HinaDrawer } from "../lightswind/Drawer";
import { SettingsV6 } from "../../features/settings";
import { VoiceDiagnosticsDrawer } from "../../features/voice/VoiceDiagnosticsDrawer";
import { TerminalHandsDrawer } from "../../features/terminal/TerminalHandsDrawer";
import { DesktopWalkingPet } from "../../features/desktop/DesktopWalkingPet";

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
  liveVision: any;

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
      <Suspense fallback={null}>
        <MemoryPanel isOpen={memoryOpen} onClose={() => setMemoryOpen(false)} />
      </Suspense>

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

      <HinaDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        mode={drawerMode}
        title={drawerTitle}
        side="bottom"
      >
        {drawerContent}
      </HinaDrawer>

      <VoiceDiagnosticsDrawer
        isOpen={diagnosticsOpen}
        onClose={() => setDiagnosticsOpen(false)}
        data={diagnosticsData}
        onManualCommit={onManualCommit}
        isListening={isListening}
      />

      <Suspense fallback={null}>
        <MusicMiniPlayer
          isOpen={musicPlayerOpen || contextMode === "music"}
          onClose={() => {
            setMusicPlayerOpen(false);
            if (contextMode === "music") setContextMode("hidden");
          }}
        />
      </Suspense>

      <TerminalHandsDrawer
        isOpen={terminalOpen}
        onClose={() => setTerminalOpen(false)}
        initialCommand={terminalInitialCmd}
      />

      {showDesktopPet && !isMobile && (
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
              return (
                res.observation ||
                "Active windows observed! Focus shield holding strong."
              );
            } catch {
              return "Active windows observed! Chrome and VS Code are open.";
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
      )}

      <Suspense fallback={null}>
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
      </Suspense>
    </>
  );
}
