import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppOverlays, type AppOverlaysProps } from "./AppOverlays";

const panels = vi.hoisted(() => ({ memory: vi.fn(), music: vi.fn(), terminal: vi.fn() }));
vi.mock("../lightswind/Drawer", () => ({ HinaDrawer: () => null }));
vi.mock("../../features/settings/SettingsV6", () => ({ SettingsV6: () => null }));
vi.mock("../../features/voice/VoiceDiagnosticsDrawer", () => ({ VoiceDiagnosticsDrawer: () => null }));
vi.mock("../../features/explainer/VisualDocumentExplainer", () => ({ VisualDocumentExplainer: () => null }));
vi.mock("../ui/MemoryPanel", () => ({ MemoryPanel: (props: { isOpen: boolean }) => {
  panels.memory(props);
  return <input aria-label="Memory draft" hidden={!props.isOpen} defaultValue="" />;
} }));
vi.mock("../ui/MusicMiniPlayer", () => ({ MusicMiniPlayer: () => { panels.music(); return null; } }));
vi.mock("../../features/terminal/TerminalHandsDrawer", () => ({ TerminalHandsDrawer: () => { panels.terminal(); return null; } }));
vi.mock("../../features/desktop/DesktopWalkingPet", () => ({ DesktopWalkingPet: ({ onObserveScreen }: { onObserveScreen: () => Promise<string> }) =>
  <button onClick={async (event) => {
    const target = event.currentTarget;
    target.textContent = await onObserveScreen();
  }}>Observe screen</button>,
}));

function props(overrides: Partial<AppOverlaysProps> = {}): AppOverlaysProps {
  // Only closed, mocked panels receive these minimal fixture props.
  return {
    memoryOpen: false, settingsOpen: false, drawerOpen: false,
    diagnosticsOpen: false, musicPlayerOpen: false, terminalOpen: false,
    showDesktopPet: false, isMobile: false, explainerOpen: false,
    contextMode: "hidden", liveVision: { observeScreen: vi.fn() },
    ...overrides,
  } as AppOverlaysProps;
}

beforeEach(() => vi.clearAllMocks());

describe("deferred app overlays", () => {
  it("does not mount closed heavy panels", () => {
    render(<AppOverlays {...props()} />);
    expect(panels.memory).not.toHaveBeenCalled();
    expect(panels.music).not.toHaveBeenCalled();
    expect(panels.terminal).not.toHaveBeenCalled();
  });

  it("loads on demand and preserves a draft across close and reopen", async () => {
    const { rerender } = render(<AppOverlays {...props()} />);
    rerender(<AppOverlays {...props({ memoryOpen: true })} />);
    const draft = await screen.findByRole("textbox", { name: "Memory draft" });
    fireEvent.change(draft, { target: { value: "Unsaved preference" } });
    rerender(<AppOverlays {...props()} />);
    expect(draft).toBeInTheDocument();
    rerender(<AppOverlays {...props({ memoryOpen: true })} />);
    expect(screen.getByRole("textbox", { name: "Memory draft" })).toHaveValue("Unsaved preference");
  });

  it.each([
    { ok: false, observation: "Unverified claim" },
    { ok: true, observation: " " },
  ])("does not invent a successful observation for %j", async result => {
    render(<AppOverlays {...props({ showDesktopPet: true, liveVision: { observeScreen: vi.fn().mockResolvedValue(result) } })} />);
    fireEvent.click(await screen.findByRole("button", { name: "Observe screen" }));
    expect(await screen.findByText(/couldn't observe your screen/)).toBeInTheDocument();
    expect(screen.queryByText(/Chrome and VS Code/)).not.toBeInTheDocument();
  });

  it("reports errors and preserves actual successful observations", async () => {
    const observeScreen = vi.fn().mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({ ok: true, observation: "A study document is visible." });
    render(<AppOverlays {...props({ showDesktopPet: true, liveVision: { observeScreen } })} />);
    fireEvent.click(await screen.findByRole("button", { name: "Observe screen" }));
    const retry = await screen.findByRole("button", { name: /Screen observation failed/ });
    fireEvent.click(retry);
    await waitFor(() => expect(retry).toHaveTextContent("A study document is visible."));
  });
});
