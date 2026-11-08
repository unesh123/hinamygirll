import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { shell, getShellState } from "./store";
import { useShellBridge } from "./useShellBridge";

const agent = { state: "idle" as const, level: 0, voiceActive: false, streamingText: "", lastText: null, steps: [], model: null };

function mount(initial: string) {
  const setSakuraView = vi.fn();
  const hook = renderHook(
    ({ view }) => useShellBridge({ sakuraView: view, setSakuraView: setSakuraView as never, theme: "dark", setTheme: vi.fn(), agent, commands: {} }),
    { initialProps: { view: initialView(initial) } },
  );
  return { setSakuraView, ...hook };
}
const initialView = (v: string) => v;

describe("useShellBridge mode mapping", () => {
  beforeEach(() => { localStorage.clear(); shell.reset(); shell.setHosted(true); });

  it("maps companion mode to the companion view (not the showroom)", () => {
    shell.setMode("companion");
    const { setSakuraView } = mount("work");
    expect(setSakuraView).toHaveBeenCalledWith("companion");
    expect(setSakuraView).not.toHaveBeenCalledWith("showroom");
  });

  it("returns to the work view when leaving companion mode", () => {
    shell.setMode("companion");
    const { setSakuraView } = mount("companion");
    setSakuraView.mockClear();
    act(() => shell.setMode("workspace"));
    expect(setSakuraView).toHaveBeenCalledWith("work");
  });

  it("leaves the showroom alone when switching to workspace", () => {
    shell.setMode("workspace");
    const { setSakuraView } = mount("showroom");
    expect(setSakuraView).not.toHaveBeenCalled();
  });

  it("opening the showroom from companion drops to workspace mode", () => {
    shell.setMode("companion");
    const { rerender } = mount("companion");
    rerender({ view: "showroom" });
    expect(getShellState().mode).toBe("workspace");
  });
});
