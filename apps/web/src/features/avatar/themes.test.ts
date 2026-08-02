import { beforeEach, describe, expect, it } from "vitest";
import { AVATAR_THEMES, loadAvatarTheme, saveAvatarTheme } from "./themes";

describe("avatar themes", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("exposes five procedural themes without VRM claims", () => {
    expect(AVATAR_THEMES.map((theme) => theme.id)).toEqual([
      "soft",
      "futuristic",
      "anime-inspired-original",
      "minimal",
      "night",
    ]);
    expect(
      AVATAR_THEMES.every((theme) => !/vrm/i.test(theme.description)),
    ).toBe(true);
  });

  it("persists theme preference", () => {
    saveAvatarTheme("night");
    expect(loadAvatarTheme()).toBe("night");
  });

  it("falls back to soft for unknown storage", () => {
    localStorage.setItem("hinaa.avatarTheme", "copyrighted-character");
    expect(loadAvatarTheme()).toBe("soft");
  });
});
