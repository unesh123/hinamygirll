import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { VmcControlPanel } from "./VmcControlPanel";
import type { VSeeFaceState } from "../../features/audio/useVSeeFace";

function tracker(status: VSeeFaceState["status"]): VSeeFaceState {
  const expressions = {
    mouthOpen: 0, mouthA: 0, mouthI: 0, mouthU: 0, mouthE: 0, mouthO: 0, mouthSmile: 0,
    eyeBlinkL: 1, eyeBlinkR: 1, browUpL: 0, browUpR: 0, browDownL: 0, browDownR: 0,
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

    expect(screen.getByText("VMC Listening")).toBeInTheDocument();
    expect(screen.queryByText("VSeeFace Live")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Calibrate neutral" })).toBeDisabled();
    expect(screen.getByText(/no recent VSeeFace tracking packet/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Reconnect" }));
    expect(state.reconnect).toHaveBeenCalledTimes(1);
  });
});
