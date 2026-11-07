import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useCompanionVision, VISION_CONSENT_KEY } from "./useCompanionVision";

const reactionBody = {
  emotion: "smug",
  remark: "Chips again?",
  should_speak: true,
  salient_event: "snack",
  wellbeing_flag: "none",
};
const frame = () => "data:image/jpeg;base64,AAA";

function setup() {
  const stop = vi.fn();
  const mediaStream = { getTracks: () => [{ stop }] } as unknown as MediaStream;
  const getUserMedia = vi.fn().mockResolvedValue(mediaStream);
  Object.defineProperty(navigator, "mediaDevices", { value: { getUserMedia }, configurable: true });
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => reactionBody });
  global.fetch = fetchMock as unknown as typeof fetch;
  return { stop, getUserMedia, fetchMock };
}

function setHidden(hidden: boolean) {
  Object.defineProperty(document, "hidden", { value: hidden, configurable: true });
  document.dispatchEvent(new Event("visibilitychange"));
}

describe("useCompanionVision", () => {
  beforeEach(() => {
    localStorage.removeItem(VISION_CONSENT_KEY);
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });
  afterEach(() => {
    setHidden(false);
    vi.useRealTimers();
  });

  it("does not touch the camera without consent", async () => {
    const { getUserMedia, fetchMock } = setup();
    renderHook(() => useCompanionVision({ captureFrame: frame }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(getUserMedia).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("persists consent, samples frames and reports spoken reactions", async () => {
    const { getUserMedia, fetchMock } = setup();
    const onReaction = vi.fn();
    const { result } = renderHook(() =>
      useCompanionVision({ onReaction, intervalSeconds: 10, captureFrame: frame }),
    );
    act(() => result.current.setConsent(true));
    expect(localStorage.getItem(VISION_CONSENT_KEY)).toBe("granted");
    await waitFor(() => expect(getUserMedia).toHaveBeenCalled());
    await waitFor(() => expect(result.current.active).toBe(true));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    await waitFor(() => expect(onReaction).toHaveBeenCalled());
    expect(onReaction.mock.calls[0][0]).toMatchObject({
      emotion: "smug",
      remark: "Chips again?",
      shouldSpeak: true,
    });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).consent).toBe(true);
  });

  it("pauses sampling while the tab is hidden", async () => {
    const { fetchMock } = setup();
    const { result } = renderHook(() => useCompanionVision({ intervalSeconds: 10, captureFrame: frame }));
    act(() => result.current.setConsent(true));
    await waitFor(() => expect(result.current.active).toBe(true));
    act(() => setHidden(true));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(fetchMock).not.toHaveBeenCalled();
    act(() => setHidden(false));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("stops camera tracks when consent is revoked and on unmount", async () => {
    const { stop } = setup();
    const { result, unmount } = renderHook(() => useCompanionVision());
    act(() => result.current.setConsent(true));
    await waitFor(() => expect(result.current.active).toBe(true));
    act(() => result.current.setConsent(false));
    expect(stop).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem(VISION_CONSENT_KEY)).toBeNull();
    act(() => result.current.setConsent(true));
    await waitFor(() => expect(result.current.active).toBe(true));
    unmount();
    expect(stop).toHaveBeenCalledTimes(2);
  });

  it("revokes consent when permission is denied", async () => {
    setup();
    Object.defineProperty(navigator, "mediaDevices", {
      value: { getUserMedia: vi.fn().mockRejectedValue(new Error("denied")) },
      configurable: true,
    });
    const { result } = renderHook(() => useCompanionVision());
    act(() => result.current.setConsent(true));
    await waitFor(() => expect(result.current.consent).toBe(false));
    expect(result.current.error).toMatch(/denied/);
  });
});
