import { describe, expect, it } from "vitest";
import {
  SyntheticSpeechTimingSource,
  AudioElementSpeechTimingSource,
  BrowserSpeechTimingSource,
  findActiveTimedItem,
} from "./speechTimingSource";

describe("SpeechTimingSource", () => {
  it("binary searches timed items accurately", () => {
    const words = [
      { word: "Hello", startMs: 0, endMs: 250 },
      { word: "world", startMs: 300, endMs: 600 },
      { word: "HINAA", startMs: 650, endMs: 950 },
    ];
    expect(findActiveTimedItem(words, 100)?.word).toBe("Hello");
    expect(findActiveTimedItem(words, 275)).toBeNull(); // in gap
    expect(findActiveTimedItem(words, 450)?.word).toBe("world");
    expect(findActiveTimedItem(words, 900)?.word).toBe("HINAA");
    expect(findActiveTimedItem(words, 1200)).toBeNull(); // past end
  });

  it("SyntheticSpeechTimingSource tracks playback time, pause, resume, and seek", () => {
    let mockTime = 1000;
    const source = new SyntheticSpeechTimingSource({
      durationMs: 1500,
      clock: () => mockTime,
      words: [
        { word: "Good", startMs: 0, endMs: 400 },
        { word: "morning", startMs: 450, endMs: 1200 },
      ],
      visemes: [
        { timeMs: 0, durationMs: 400, mouth: "ou", weight: 0.8 },
        { timeMs: 450, durationMs: 750, mouth: "aa", weight: 0.9 },
      ],
    });

    expect(source.isPlaying()).toBe(false);
    expect(source.getPlaybackTime()).toBe(0);

    source.start();
    expect(source.isPlaying()).toBe(true);

    mockTime += 200;
    expect(source.getPlaybackTime()).toBe(200);
    expect(source.getWordAt(200)?.word).toBe("Good");
    expect(source.getVisemeAt(200)?.mouth).toBe("ou");

    source.pause();
    expect(source.isPlaying()).toBe(false);
    expect(source.getPlaybackTime()).toBe(200);

    // advancing clock while paused should not advance playback
    mockTime += 500;
    expect(source.getPlaybackTime()).toBe(200);

    source.start();
    expect(source.isPlaying()).toBe(true);
    mockTime += 400; // total 600ms
    expect(source.getPlaybackTime()).toBe(600);
    expect(source.getWordAt(600)?.word).toBe("morning");
    expect(source.getVisemeAt(600)?.mouth).toBe("aa");

    source.seek(100);
    expect(source.getPlaybackTime()).toBe(100);
  });

  it("AudioElementSpeechTimingSource delegates to HTMLAudioElement", () => {
    const fakeAudio = {
      currentTime: 0.5,
      duration: 2.0,
      paused: false,
      ended: false,
    };
    const source = new AudioElementSpeechTimingSource({
      audioElement: fakeAudio,
      words: [{ word: "Sakura", startMs: 200, endMs: 800 }],
    });

    expect(source.getPlaybackTime()).toBe(500);
    expect(source.getDuration()).toBe(2000);
    expect(source.isPlaying()).toBe(true);
    expect(source.getWordAt(500)?.word).toBe("Sakura");

    fakeAudio.currentTime = 1.0;
    expect(source.getWordAt(1000)).toBeNull();

    fakeAudio.paused = true;
    expect(source.isPlaying()).toBe(false);
  });

  it("BrowserSpeechTimingSource tracks utterance lifecycle events", () => {
    let mockClock = 5000;
    const source = new BrowserSpeechTimingSource({
      durationMs: 800,
      clock: () => mockClock,
      words: [{ word: "Hello", startMs: 0, endMs: 600 }],
    });

    expect(source.isPlaying()).toBe(false);
    source.onUtteranceStart();
    expect(source.isPlaying()).toBe(true);

    mockClock += 300;
    expect(source.getPlaybackTime()).toBe(300);
    expect(source.getWordAt(300)?.word).toBe("Hello");

    source.onUtteranceEnd();
    expect(source.isPlaying()).toBe(false);
  });
});
