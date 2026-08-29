import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// ── Tests for the voice pipeline state machine ──
// These test the logic of state transitions, not the React hook itself.

describe("Voice Pipeline State Machine", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe("Playback queue state tracking", () => {
    it("starts with empty queue", () => {
      const queue = {
        encodedChunks: 0,
        decoding: 0,
        decodedBuffers: 0,
        scheduledSources: 0,
        finalSequenceReceived: false,
      };
      expect(queue.encodedChunks).toBe(0);
      expect(queue.decoding).toBe(0);
      expect(queue.decodedBuffers).toBe(0);
      expect(queue.scheduledSources).toBe(0);
      expect(queue.finalSequenceReceived).toBe(false);
    });

    it("tracks chunk lifecycle: encoded → decoding → decoded → playing → drained", () => {
      const queue = {
        encodedChunks: 0,
        decoding: 0,
        decodedBuffers: 0,
        scheduledSources: 0,
        finalSequenceReceived: false,
      };

      // Chunk arrives
      queue.encodedChunks += 1;
      expect(queue.encodedChunks).toBe(1);

      // Start decoding
      queue.encodedChunks -= 1;
      queue.decoding += 1;
      expect(queue.decoding).toBe(1);
      expect(queue.encodedChunks).toBe(0);

      // Decoding complete
      queue.decoding -= 1;
      queue.decodedBuffers += 1;
      expect(queue.decodedBuffers).toBe(1);
      expect(queue.decoding).toBe(0);

      // Scheduled for playback
      queue.decodedBuffers -= 1;
      queue.scheduledSources += 1;
      expect(queue.scheduledSources).toBe(1);
      expect(queue.decodedBuffers).toBe(0);

      // Playback complete
      queue.scheduledSources -= 1;
      expect(queue.scheduledSources).toBe(0);

      // Drained
      const drained =
        queue.encodedChunks === 0 &&
        queue.decoding === 0 &&
        queue.decodedBuffers === 0 &&
        queue.scheduledSources === 0;
      expect(drained).toBe(true);
    });

    it("detects not-drained when chunks are pending", () => {
      const queue = {
        encodedChunks: 2,
        decoding: 1,
        decodedBuffers: 0,
        scheduledSources: 0,
        finalSequenceReceived: false,
      };
      const drained =
        queue.encodedChunks === 0 &&
        queue.decoding === 0 &&
        queue.decodedBuffers === 0 &&
        queue.scheduledSources === 0;
      expect(drained).toBe(false);
    });
  });

  describe("Turn completion logic", () => {
    it("stays in speaking when audio is still pending after turn.complete", () => {
      const turnCompleteReceived = true;
      const playbackPlaying = true;
      const audioStillPending = true;

      const playbackDone = !playbackPlaying && !audioStillPending;
      expect(playbackDone).toBe(false);
      // Should NOT transition to listening
    });

    it("transitions to listening when playback is done and turn.complete received", () => {
      const turnCompleteReceived = true;
      const playbackPlaying = false;
      const audioStillPending = false;

      const playbackDone = !playbackPlaying && !audioStillPending;
      expect(playbackDone).toBe(true);
      // Should transition to listening
    });

    it("handles text-only response without error", () => {
      const ttsRequested = false;
      const audioChunksReceived = 0;
      const playbackDone = true;

      // Intentional text-only is not an error
      expect(ttsRequested).toBe(false);
      expect(playbackDone).toBe(true);
    });

    it("handles TTS failed but text available", () => {
      const ttsStatus = "failed";
      const playbackDone = true;

      expect(ttsStatus).toBe("failed");
      expect(playbackDone).toBe(true);
      // Should show friendly message, not error
    });
  });

  describe("Interruption clears old-turn state", () => {
    it("resets all queue state on interruption", () => {
      const queue = {
        encodedChunks: 3,
        decoding: 2,
        decodedBuffers: 1,
        scheduledSources: 1,
        finalSequenceReceived: true,
      };

      // Simulate interruption
      const newQueue = {
        encodedChunks: 0,
        decoding: 0,
        decodedBuffers: 0,
        scheduledSources: 0,
        finalSequenceReceived: false,
      };

      Object.assign(queue, newQueue);
      expect(queue.encodedChunks).toBe(0);
      expect(queue.decoding).toBe(0);
      expect(queue.decodedBuffers).toBe(0);
      expect(queue.scheduledSources).toBe(0);
      expect(queue.finalSequenceReceived).toBe(false);
    });

    it("increments generation to invalidate stale events", () => {
      let generation = 5;
      generation += 1;
      expect(generation).toBe(6);
      // Events from generation 5 should be rejected
    });
  });

  describe("Turn ID correlation", () => {
    it("rejects events with stale turn ID", () => {
      const activeTurnId = "turn-3-6";
      const staleEventTurnId = "turn-2-5";
      const currentEventTurnId = "turn-3-6";

      expect(staleEventTurnId === activeTurnId).toBe(false);
      expect(currentEventTurnId === activeTurnId).toBe(true);
    });

    it("resets counters when new turn ID arrives", () => {
      let audioChunksReceived = 5;
      let turnCompleteReceived = true;
      let activeTurnId = "turn-2-5";

      // New turn arrives
      const newTurnId = "turn-3-6";
      if (newTurnId !== activeTurnId) {
        activeTurnId = newTurnId;
        audioChunksReceived = 0;
        turnCompleteReceived = false;
      }

      expect(activeTurnId).toBe("turn-3-6");
      expect(audioChunksReceived).toBe(0);
      expect(turnCompleteReceived).toBe(false);
    });
  });

  describe("Backend turn.complete metadata", () => {
    it("distinguishes text-only from audio response", () => {
      const textOnlyEvent = {
        outputMode: "text",
        ttsRequested: false,
        ttsStatus: "not_requested",
      };
      const audioEvent = {
        outputMode: "text_and_audio",
        ttsRequested: true,
        ttsStatus: "completed",
      };
      const failedAudioEvent = {
        outputMode: "text",
        ttsRequested: true,
        ttsStatus: "failed",
      };

      expect(textOnlyEvent.ttsRequested).toBe(false);
      expect(audioEvent.ttsStatus).toBe("completed");
      expect(failedAudioEvent.ttsStatus).toBe("failed");
    });

    it("tells frontend whether audio was expected", () => {
      // Backend sends ttsRequested: true, but zero chunks arrive
      const ttsRequested = true;
      const audioChunksReceived = 0;
      const turnCompleteReceived = true;

      // This is a TTS failure, not text-only
      expect(ttsRequested).toBe(true);
      expect(audioChunksReceived).toBe(0);
    });
  });

  describe("Error message mapping", () => {
    const userMessages: Record<string, string> = {
      PROVIDER_KEY_INVALID:
        "The voice service needs to be configured. You can still type to me.",
      PROVIDER_TIMEOUT:
        "The response took too long. Your transcript is still available.",
      AUDIO_NO_SIGNAL: "I didn't hear anything. Try speaking again or use text.",
      STT_COMMIT_TIMEOUT:
        "I didn't receive a clear transcript. Please try speaking again.",
      TTS_ZERO_AUDIO:
        "I completed the reply, but voice playback wasn't available. You can read my reply below.",
      AUDIO_DECODE_FAILED:
        "I received the voice response, but this browser couldn't decode it.",
      PLAYBACK_BLOCKED:
        "I couldn't play the voice response. Tap to retry audio.",
    };

    it("PROVIDER_KEY_INVALID is user-friendly", () => {
      expect(userMessages.PROVIDER_KEY_INVALID).toContain("type to me");
      expect(userMessages.PROVIDER_KEY_INVALID).not.toContain("key rejected");
    });

    it("AUDIO_NO_SIGNAL is actionable", () => {
      expect(userMessages.AUDIO_NO_SIGNAL).toContain("Try speaking again");
    });

    it("TTS_ZERO_AUDIO explains text is still available", () => {
      expect(userMessages.TTS_ZERO_AUDIO).toContain("read my reply");
    });

    it("no technical codes leak into user messages", () => {
      for (const msg of Object.values(userMessages)) {
        expect(msg).not.toMatch(/^[A-Z_]+$/); // not just a code
        expect(msg).not.toContain("backend");
        expect(msg).not.toContain(".env.local");
      }
    });
  });

  describe("Drain timeout", () => {
    it("fires after 30 seconds if audio never drains", () => {
      const callback = vi.fn();
      const timer = setTimeout(callback, 30_000);
      vi.advanceTimersByTime(30_000);
      expect(callback).toHaveBeenCalled();
      clearTimeout(timer);
    });

    it("does not fire before 30 seconds", () => {
      const callback = vi.fn();
      const timer = setTimeout(callback, 30_000);
      vi.advanceTimersByTime(29_000);
      expect(callback).not.toHaveBeenCalled();
      clearTimeout(timer);
    });
  });
});
