/**
 * coreState.test.ts — the crystalline core speaks her real state through
 * color: cyan listening / violet reasoning / blue speaking / white idle /
 * amber attention / red failure. These tests pin that contract so the core
 * can never silently drift into a wrong state.
 */
import { describe, expect, it } from "vitest";
import {
  CORE_STATE_META,
  coreStateFor,
  irisRingActiveFor,
} from "./coreState";

describe("coreStateFor", () => {
  it("maps listening-family states to cyan listening", () => {
    expect(coreStateFor("listening")).toBe("listening");
    expect(coreStateFor("possible_speech")).toBe("listening");
    expect(coreStateFor("active_speech")).toBe("listening");
  });

  it("maps reasoning-family states to violet reasoning", () => {
    expect(coreStateFor("thinking")).toBe("reasoning");
    expect(coreStateFor("streaming_text")).toBe("reasoning");
    expect(coreStateFor("committing")).toBe("reasoning");
    expect(coreStateFor("transcribing")).toBe("reasoning");
    expect(coreStateFor("hesitation")).toBe("reasoning");
  });

  it("maps speaking to blue speaking", () => {
    expect(coreStateFor("speaking")).toBe("speaking");
  });

  it("maps idle / booting / intro to white idle", () => {
    expect(coreStateFor("idle")).toBe("idle");
    expect(coreStateFor("booting")).toBe("idle");
    expect(coreStateFor("intro")).toBe("idle");
    // Unknown states must degrade to idle, never crash.
    expect(coreStateFor("made-up-state")).toBe("idle");
  });

  it("maps interrupted and session transitions to amber attention", () => {
    expect(coreStateFor("interrupted")).toBe("attention");
    expect(coreStateFor("paused")).toBe("attention");
    expect(coreStateFor("session_starting")).toBe("attention");
    expect(coreStateFor("session_ending")).toBe("attention");
  });

  it("maps genuine failures to red failure", () => {
    expect(coreStateFor("error")).toBe("failure");
    expect(coreStateFor("provider_unavailable")).toBe("failure");
    expect(coreStateFor("reconnecting")).toBe("failure");
  });
});

describe("irisRingActiveFor", () => {
  it("brightens only while she reasons or recalls", () => {
    expect(irisRingActiveFor("thinking")).toBe(true);
    expect(irisRingActiveFor("streaming_text")).toBe(true);
    expect(irisRingActiveFor("speaking")).toBe(false);
    expect(irisRingActiveFor("listening")).toBe(false);
    expect(irisRingActiveFor("idle")).toBe(false);
    expect(irisRingActiveFor("interrupted")).toBe(false);
  });
});

describe("core palette", () => {
  it("keeps the six owner-specified state colors", () => {
    expect(CORE_STATE_META.listening.color).toBe("#22d3ee"); // cyan
    expect(CORE_STATE_META.reasoning.color).toBe("#8b5cf6"); // violet
    expect(CORE_STATE_META.speaking.color).toBe("#3b82f6"); // blue
    expect(CORE_STATE_META.idle.color).toBe("#f1f5f9"); // white
    expect(CORE_STATE_META.attention.color).toBe("#f59e0b"); // amber
    expect(CORE_STATE_META.failure.color).toBe("#ef4444"); // red
  });
});
