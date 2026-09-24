import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useMediaSession } from "./useMediaSession";

describe("useMediaSession hook", () => {
  const setActionHandler = vi.fn();
  let mediaSessionMock: any;

  beforeEach(() => {
    setActionHandler.mockClear();
    mediaSessionMock = {
      metadata: null,
      playbackState: "none",
      setActionHandler,
    };

    vi.stubGlobal("MediaMetadata", class {
      title: string;
      artist: string;
      album: string;
      artwork: any[];
      constructor(data: any) {
        this.title = data.title;
        this.artist = data.artist;
        this.album = data.album;
        this.artwork = data.artwork;
      }
    });

    Object.defineProperty(navigator, "mediaSession", {
      value: mediaSessionMock,
      configurable: true,
      writable: true,
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sets metadata and playbackState when playing", () => {
    const onPlay = vi.fn();
    const onPause = vi.fn();
    const onStop = vi.fn();

    renderHook(() =>
      useMediaSession({
        title: "HINAA Talk",
        companionName: "HINAA",
        isPlaying: true,
        isListening: false,
        onPlay,
        onPause,
        onStop,
      })
    );

    expect(mediaSessionMock.playbackState).toBe("playing");
    expect(mediaSessionMock.metadata?.title).toBe("HINAA Talk");
    expect(mediaSessionMock.metadata?.artist).toBe("HINAA");
    expect(mediaSessionMock.metadata?.album).toContain("Speaking...");
    expect(setActionHandler).toHaveBeenCalledWith("play", onPlay);
    expect(setActionHandler).toHaveBeenCalledWith("pause", onPause);
    expect(setActionHandler).toHaveBeenCalledWith("stop", onStop);
  });

  it("sets paused playbackState when listening", () => {
    renderHook(() =>
      useMediaSession({
        isPlaying: false,
        isListening: true,
      })
    );

    expect(mediaSessionMock.playbackState).toBe("paused");
    expect(mediaSessionMock.metadata?.album).toContain("Listening...");
  });

  it("cleans up handlers on unmount", () => {
    const { unmount } = renderHook(() =>
      useMediaSession({
        isPlaying: true,
        onPlay: vi.fn(),
      })
    );

    unmount();
    expect(setActionHandler).toHaveBeenCalledWith("play", null);
    expect(setActionHandler).toHaveBeenCalledWith("pause", null);
    expect(setActionHandler).toHaveBeenCalledWith("stop", null);
  });
});
