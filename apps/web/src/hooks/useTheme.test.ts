import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { HINA_THEME_STORAGE_KEY, useTheme } from "./useTheme";

describe("useTheme", () => {
  beforeEach(() => {
    window.localStorage.clear();
    delete document.documentElement.dataset.theme;
  });

  it("reads and persists theme preference in localStorage and document dataset", () => {
    const { result } = renderHook(() => useTheme("light"));
    expect(result.current.resolvedTheme).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");

    act(() => {
      result.current.toggle();
    });
    expect(result.current.resolvedTheme).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(window.localStorage.getItem(HINA_THEME_STORAGE_KEY)).toBe("dark");
  });

  it("restores saved preference on mount", () => {
    window.localStorage.setItem(HINA_THEME_STORAGE_KEY, "dark");
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("dark");
    expect(result.current.isDark).toBe(true);
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
});
