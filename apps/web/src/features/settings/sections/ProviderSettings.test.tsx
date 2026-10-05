import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProviderSettings } from "./ProviderSettings";
import type { ProvidersState } from "../../providers/types/provider";

const providers: ProvidersState = {
  statuses: [{ id: "experiential", state: "untested", capabilities: [], userMessage: "Configured; no live call yet." }],
  loaded: true, error: null, providerOptions: [], getModelOptions: () => [],
  getDefaultModel: () => null, getHealth: () => "untested", refresh: vi.fn(),
};

describe("provider settings recovery", () => {
  it("does not show cached cloud voice availability after losing the backend", () => {
    render(<ProviderSettings provider={{ preferredMode: "auto", preferredModelByProvider: {} }}
      providers={{ ...providers, error: "Backend offline", statuses: [{ id: "elevenlabs", state: "healthy", capabilities: ["tts"] }] }}
      onChange={vi.fn()} />);
    expect(screen.getByText("Device voice fallback")).toBeInTheDocument();
    expect(screen.queryByText("ElevenLabs voice ready")).not.toBeInTheDocument();
  });

  it("explains provider health and lets the user refresh", () => {
    render(<ProviderSettings provider={{ preferredMode: "experiential", preferredModelByProvider: {} }}
      providers={providers} onChange={vi.fn()} />);
    expect(screen.getByText("Configured; no live call yet.")).toBeInTheDocument();
    expect(screen.getByLabelText("AI provider")).toHaveValue("experiential");
    fireEvent.click(screen.getByRole("button", { name: "Refresh provider status" }));
    expect(providers.refresh).toHaveBeenCalled();
  });

  it("does not claim Automatic is healthy without a resolved provider", () => {
    render(<ProviderSettings provider={{ preferredMode: "auto", preferredModelByProvider: {} }}
      providers={providers} onChange={vi.fn()} />);
    expect(screen.getByRole("status")).toHaveTextContent("Unknown");
  });

  it("does not claim a saved model was removed while metadata is unavailable", () => {
    render(<ProviderSettings provider={{ preferredMode: "experiential", preferredModelByProvider: { experiential: "saved-model" } }}
      providers={providers} onChange={vi.fn()} />);
    expect(screen.queryByText(/Previously selected model/)).not.toBeInTheDocument();
  });
});
