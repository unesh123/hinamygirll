import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LiveCallOverlay } from "./LiveCallOverlay";
import { downsampleFloat32ToInt16 } from "../../live/capture.worklet";

describe("Jarvis Live Call UI", () => {
  it("renders orb, latency HUD, and toggles push-to-talk via Space", () => {
    render(<LiveCallOverlay />);
    expect(screen.getByTestId("live-breathing-orb")).toBeInTheDocument();
    expect(screen.getByTestId("live-latency-hud")).toHaveTextContent("ASR");
    expect(screen.getByRole("button", { name: /Start Live Call/i })).toBeInTheDocument();

    fireEvent.keyDown(window, { code: "Space" });
    expect(screen.getByTestId("live-breathing-orb").style.transform).not.toBe("scale(1)");
    fireEvent.keyUp(window, { code: "Space" });
  });

  it("downsamples 48kHz audio cleanly to 16kHz int16 PCM", () => {
    const buf = new Float32Array(1440).fill(0.5);
    const out = downsampleFloat32ToInt16(buf, 48000, 16000);
    expect(out.length).toBe(480);
    expect(out[0]).toBeGreaterThan(10000);
  });
});
