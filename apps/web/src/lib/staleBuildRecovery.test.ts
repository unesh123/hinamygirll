import { describe, expect, it, vi } from "vitest";

import {
  installStaleBuildRecovery,
  isStaleChunkError,
  recoverFromStaleChunk,
} from "./staleBuildRecovery";

function makeGlobals() {
  const store = new Map<string, string>();
  return {
    sessionStorage: {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => void store.set(key, value),
    },
  };
}

describe("stale build recovery", () => {
  it("recognises the chunk failures a redeploy causes", () => {
    expect(
      isStaleChunkError(
        new Error(
          "Failed to fetch dynamically imported module: https://app/assets/ActivityPanel-DfcbB1Rz.js",
        ),
      ),
    ).toBe(true);
    expect(isStaleChunkError("Importing a module script failed.")).toBe(true);
    expect(isStaleChunkError(new Error("unable to preload CSS for /assets/x.css"))).toBe(true);
  });

  it("leaves unrelated rejections alone", () => {
    expect(isStaleChunkError(new Error("Cannot read properties of undefined"))).toBe(false);
    expect(isStaleChunkError(undefined)).toBe(false);
    expect(isStaleChunkError(null)).toBe(false);
  });

  it("drops the cached shell before reloading so the old build cannot return", async () => {
    const reload = vi.fn();
    const purge = vi.fn(async () => undefined);
    const outcome = await recoverFromStaleChunk(
      {
        sessionStorage: makeGlobals().sessionStorage,
        location: { reload },
        unregisterServiceWorkers: purge,
      },
      new Error("Failed to fetch dynamically imported module: /assets/ActivityPanel-x.js"),
    );
    expect(outcome).toBe("reloaded");
    expect(purge.mock.invocationCallOrder[0]).toBeLessThan(reload.mock.invocationCallOrder[0]);
  });

  it("never reloads twice for the same session", async () => {
    const reload = vi.fn();
    const globals = {
      ...makeGlobals(),
      location: { reload },
      unregisterServiceWorkers: async () => undefined,
    };
    const error = new Error("Failed to fetch dynamically imported module: /assets/a.js");
    expect(await recoverFromStaleChunk(globals, error)).toBe("reloaded");
    expect(await recoverFromStaleChunk(globals, error)).toBe("already-recovered");
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("ignores rejections that are not stale chunks", async () => {
    const reload = vi.fn();
    const outcome = await recoverFromStaleChunk(
      {
        sessionStorage: { getItem: () => null, setItem: () => undefined },
        location: { reload },
        unregisterServiceWorkers: async () => undefined,
      },
      new Error("network timeout while posting a turn"),
    );
    expect(outcome).toBe("ignored");
    expect(reload).not.toHaveBeenCalled();
  });

  it("wires the Vite preload signal and the unhandled rejection path", async () => {
    const listener = vi.spyOn(window, "addEventListener");
    const remove = installStaleBuildRecovery();
    const events = listener.mock.calls.map(([type]) => type);
    expect(events).toContain("vite:preloadError");
    expect(events).toContain("unhandledrejection");
    remove();
  });
});
