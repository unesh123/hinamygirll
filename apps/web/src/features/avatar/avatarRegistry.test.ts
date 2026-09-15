import { describe, expect, it } from "vitest";
import { AVATAR_REGISTRY, AVATAR_SELECTION_KEY, LEGACY_AVATAR_SELECTION_KEY, persistAvatarSelection, readAvatarSelection, isSelectableAvatarUrl } from "./avatarRegistry";

describe("avatar selection migration", () => {
  it.each(["hinaa-original", "hinaa-classic", "hinaa-kimono"])("selects and restores %s by stable ID", (id) => {
    localStorage.clear();
    const model = AVATAR_REGISTRY.find((item) => item.id === id)!;
    expect(isSelectableAvatarUrl(model.fileUrl)).toBe(true);
    localStorage.setItem(LEGACY_AVATAR_SELECTION_KEY, model.fileUrl);
    expect(readAvatarSelection(localStorage)).toBe(model.fileUrl);
    expect(JSON.parse(localStorage.getItem(AVATAR_SELECTION_KEY)!)).toEqual({ id });
    localStorage.removeItem(LEGACY_AVATAR_SELECTION_KEY);
    expect(readAvatarSelection(localStorage)).toBe(model.fileUrl);
  });
  it("keeps transient VRM previews out of saved selection", () => {
    localStorage.clear();
    persistAvatarSelection(localStorage, AVATAR_REGISTRY[0].fileUrl);
    const saved = localStorage.getItem(AVATAR_SELECTION_KEY);
    persistAvatarSelection(localStorage, "blob:temporary-vrm");
    expect(localStorage.getItem(AVATAR_SELECTION_KEY)).toBe(saved);
    expect(isSelectableAvatarUrl("https://untrusted.test/model.vrm")).toBe(false);
  });
});
