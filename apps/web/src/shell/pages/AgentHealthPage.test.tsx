import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import AgentHealthPage from "./AgentHealthPage";

describe("AgentHealthPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders real society metrics and shows em-dash when zero circles recorded", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        json: async () => ({
          status: "ok",
          total_circles: 0,
          first_pass_verified: 0,
          first_pass_rate_pct: null,
          reviewer_catches: 0,
          verifier_failures: 0,
          lessons_stored: 3,
          lessons_applied: 5,
          skills_synthesized: 1,
          marathons_completed: 2,
          marathons_paused: 0,
          recent_events: [
            { kind: "memory.lesson", topic: "Vitest measureElement guard", ts: 1700000000 },
          ],
        }),
      }) as Response),
    );

    render(
      <MemoryRouter>
        <AgentHealthPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("First-pass rate")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("—")).toBeInTheDocument();
      expect(screen.getByText("Vitest measureElement guard")).toBeInTheDocument();
    });
  });
});
