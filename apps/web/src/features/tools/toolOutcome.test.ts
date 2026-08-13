import { describe, expect, it } from "vitest";

import { resolveToolOutcome } from "./toolOutcome";

describe("resolveToolOutcome", () => {
  it("marks YouTube as complete only when playback is verified", () => {
    const outcome = resolveToolOutcome("youtube_playback_request", {
      status: "success",
      data: { verified: true, message: "Playing Lofi mix in HINAA's owned YouTube tab." },
    });

    expect(outcome.status).toBe("complete");
    expect(outcome.label).toContain("Playing verified");
  });

  it("keeps a blocked YouTube player visibly incomplete", () => {
    const outcome = resolveToolOutcome("youtube_playback_request", {
      status: "blocked",
      data: { verified: false, state: "needs-user-play", message: "Press Play in that tab." },
    });

    expect(outcome.status).toBe("blocked");
    expect(outcome.label).toContain("YouTube needs you");
    expect(outcome.label).toContain("Press Play");
  });

  it("does not accept an optimistic YouTube success without verification", () => {
    const outcome = resolveToolOutcome("youtube_playback_request", {
      status: "success",
      data: { message: "Opened a URL." },
    });

    expect(outcome.status).toBe("blocked");
    expect(outcome.label).toContain("not verified");
  });
});
