import { describe, expect, it } from "vitest";
import { ProceduralAvatarEngine } from "./avatarEngine";

describe("ProceduralAvatarEngine", () => {
  it("preserves safe state and accessibility degradation flags", () => {
    const engine = new ProceduralAvatarEngine();
    const frame = engine.getFrame({
      companionId: "hinaa",
      state: "listening",
      reducedMotion: true,
      textOnly: true,
    });
    expect(engine.kind).toBe("procedural-placeholder");
    expect(frame).toMatchObject({
      state: "listening",
      reducedMotion: true,
      textOnly: true,
    });
  });
});
