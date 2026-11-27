import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import AutopilotPage from "./AutopilotPage";
import GoalsPage from "./GoalsPage";
import MemoryPage from "./MemoryPage";
import SecurityPage from "./SecurityPage";

describe("Shell pages smoke suite", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders Autopilot, Goals, Memory, and Security pages cleanly", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        json: async () => ({ items: [], memories: [], schedules: [], goals: [] }),
      }) as Response),
    );

    const { unmount } = render(<MemoryRouter><AutopilotPage /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "Autopilot" })).toBeInTheDocument();
    unmount();

    const g = render(<MemoryRouter><GoalsPage /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "Goals" })).toBeInTheDocument();
    g.unmount();

    const m = render(<MemoryRouter><MemoryPage /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "Real Memory" })).toBeInTheDocument();
    m.unmount();

    const s = render(<MemoryRouter><SecurityPage /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "Security" })).toBeInTheDocument();
    s.unmount();
  });
});
