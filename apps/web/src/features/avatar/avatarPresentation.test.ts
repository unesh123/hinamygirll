import { describe, expect, it } from "vitest";
import {
  defaultAvatarPresentation,
  flipAvatarFacing,
  getPersistedAvatarPresentation,
  normalizeAvatarPresentation,
  persistAvatarPresentation,
} from "./avatarPresentation";

describe("avatar presentation", () => {
  it("starts imported models in a browser-only front-facing relaxed preset", () => {
    const presentation = defaultAvatarPresentation("/api/v1/avatar-assets/avatar-123/file");
    expect(presentation.rotationY).toBe(Math.PI);
    expect(presentation.poseMode).toBe("relaxed");
    expect(presentation.scale).toBe(1);
  });

  it("keeps authored-pose recovery and safe numerical bounds available", () => {
    const repaired = normalizeAvatarPresentation({ poseMode: "original", scale: 99, offsetY: -99 }, "/managed/avatar.vrm");
    expect(repaired.poseMode).toBe("original");
    expect(repaired.scale).toBe(2.5);
    expect(repaired.offsetY).toBe(-1.5);
  });

  it("flips a model facing by a half turn without changing its pose", () => {
    const base = defaultAvatarPresentation("/managed/avatar.vrm");
    const corrected = flipAvatarFacing(base);
    expect(corrected.rotationY).toBe(0);
    expect(corrected.poseMode).toBe("relaxed");
  });

  it("persists presentation independently for each local model URL", () => {
    const url = "/api/v1/avatar-assets/avatar-123/file";
    persistAvatarPresentation(url, { rotationY: 0, offsetY: 0.12, scale: 1.08, poseMode: "original" });
    expect(getPersistedAvatarPresentation(url)).toEqual({ rotationY: 0, offsetY: 0.12, scale: 1.08, poseMode: "original" });
  });
});
