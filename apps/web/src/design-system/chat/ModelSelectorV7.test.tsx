import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ModelSelectorV7 } from "./ModelSelectorV7";
import type { DiscoveredModel } from "../../features/providers/hooks/useCapabilities";

const models: DiscoveredModel[] = ["claude", "experiential"].map((provider) => ({
  id: "shared-model", name: `${provider} model`, provider,
  tier: "standard", configured: true, description: "Configured model",
}));

describe("model picker", () => {
  it("recognizes the persisted Gemini request mode in the discovery catalog", () => {
    render(<ModelSelectorV7 models={[{ ...models[0], provider: "gemini", name: "Configured Gemini" }]}
      selectedModelId="shared-model" selectedProviderId="real" isAutoRouter={false}
      onSelectAuto={vi.fn()} onSelectModel={vi.fn()} />);
    expect(screen.getByTestId("composer-model-selector-btn")).toHaveTextContent("Configured Gemini");
    fireEvent.click(screen.getByTestId("composer-model-selector-btn"));
    expect(screen.getByRole("menuitemradio", { name: /Configured Gemini/ })).toHaveAttribute("aria-checked", "true");
  });

  it("pins a model by provider as well as model ID", () => {
    render(<ModelSelectorV7 models={models} selectedModelId="shared-model" selectedProviderId="experiential"
      isAutoRouter={false} onSelectAuto={vi.fn()} onSelectModel={vi.fn()} />);
    fireEvent.click(screen.getByTestId("composer-model-selector-btn"));
    expect(screen.getByRole("menuitemradio", { name: /experiential model/ })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("menuitemradio", { name: /claude model/ })).toHaveAttribute("aria-checked", "false");
  });

  it("supports arrow navigation and restores trigger focus on Escape", () => {
    render(<ModelSelectorV7 models={models} onSelectAuto={vi.fn()} onSelectModel={vi.fn()} />);
    const trigger = screen.getByTestId("composer-model-selector-btn");
    fireEvent.click(trigger);
    const options = screen.getAllByRole("menuitemradio");
    expect(options[0]).toHaveFocus();
    fireEvent.keyDown(options[0], { key: "ArrowDown" });
    expect(options[1]).toHaveFocus();
    fireEvent.keyDown(options[1], { key: "Escape" });
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("disables a provider that failed its last request", () => {
    const select = vi.fn();
    render(<ModelSelectorV7 models={[models[1]]} providers={[{
      id: "experiential", name: "Experiential", configured: true, defaultModel: "shared-model",
      allowedModels: ["shared-model"], protocol: "openai-compatible", health: "unavailable",
    }]} onSelectAuto={vi.fn()} onSelectModel={select} />);
    fireEvent.click(screen.getByTestId("composer-model-selector-btn"));
    const option = screen.getByRole("menuitemradio", { name: /experiential model/ });
    expect(option).toBeDisabled();
    fireEvent.click(option);
    expect(select).not.toHaveBeenCalled();
  });
});
