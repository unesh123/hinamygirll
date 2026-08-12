import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { VmcControlPanel } from "./VmcControlPanel";
import type { VSeeFaceState } from "../../features/audio/useVSeeFace";

function tracker(status: VSeeFaceState["status"]): VSeeFaceState {
  const expressions = {
    mouthOpen: 0, mouthA: 0, mouthI: 0, mouthU: 0, mouthE: 0, mouthO: 0, mouthSmile: 0,
    eyeBlinkL: 0, eyeBlinkR: 0, browUpL: 0, browUpR: 0, browDownL: 0, browDownR: 0,
    cheekPuff: 0, angry: 0, sad: 0, relaxed: 0,
  };
  return {
    status,
    expressions,
    expressionsRef: { current: expressions },
    bonesRef: { current: {} },
    diagnostics: {
      state: "listening", listening: true, receiverInstanceId: "vmc-test", host: "127.0.0.1", port: 39539,
      lastPacketTimestamp: null, packetAgeMs: null, packetRate: 0, packetCount: 0, detectedChannels: [],
      source: "none", sender: null, webSocketClients: 1, connectionAttempts: 1, staleAfterMs: 1500, sequence: 0,
    },
    hasFacialSignal: false,
    calibration: null,
    error: null,
    connectionId: "vmc-ws-test",
    connect: vi.fn(), disconnect: vi.fn(), reconnect: vi.fn(), refresh: vi.fn(async () => undefined),
    testSignal: vi.fn(async () => undefined), calibrate: vi.fn(() => false), resetCalibration: vi.fn(),
  };
}

describe("VmcControlPanel", () => {
  it("does not present a listening bridge as live camera tracking", () => {
    const state = tracker("listening");
    render(<VmcControlPanel tracker={state} selectedModelLabel="Hinaa" selectedModelMode="autonomous" onClose={vi.fn()} onOpenAvatarLab={vi.fn()} />);

    expect(screen.getAllByText("Waiting for VSeeFace").length).toBeGreaterThan(0);
    expect(screen.queryByText("VSeeFace Live")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Calibrate neutral" })).not.toBeInTheDocument();
    expect(screen.getByText(/no recent VSeeFace tracking packet/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Reconnect" }));
    expect(state.reconnect).toHaveBeenCalledTimes(1);
  });

  it("does not claim expression mirroring until supported blendshapes are detected", () => {
    const state = tracker("live");
    state.diagnostics = { ...state.diagnostics!, state: "live", packetRate: 30, packetCount: 30, source: "external", lastPacketTimestamp: new Date().toISOString() };
    render(<VmcControlPanel tracker={state} selectedModelLabel="Hinaa" selectedModelMode="autonomous" onClose={vi.fn()} onOpenAvatarLab={vi.fn()} />);

    expect(screen.getByText("VSeeFace Live")).toBeInTheDocument();
    expect(screen.getByText(/no supported VSeeFace blendshape channel/i)).toBeInTheDocument();
    expect(screen.getByText("Waiting for blendshapes")).toBeInTheDocument();
  });
});
