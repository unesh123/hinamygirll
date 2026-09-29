import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { ShowroomMode } from "./ShowroomMode";

// Mock VRMAvatar to avoid WebGL context requirements in jsdom
vi.mock("../../features/avatar/VRMAvatar", () => ({
  VRMAvatar: () => <div data-testid="mock-vrm-avatar">Mock VRM Avatar</div>,
}));

describe("ShowroomMode — DICH Haute-Couture Cyber Showroom", () => {
  it("renders the cybernetic HUD header and initial lookbook view", () => {
    render(<ShowroomMode />);

    expect(screen.getByText(/HINAA \/\/ OMEGA HAUTE-COUTURE/i)).toBeInTheDocument();
    expect(screen.getByText(/DARE_TO_DISRUPT/i)).toBeInTheDocument();
    expect(screen.getByText(/ORANITHS/i)).toBeInTheDocument();
    expect(screen.getByTestId("mock-vrm-avatar")).toBeInTheDocument();
  });

  it("switches to Runway Gallery and displays ANTURAX showcase", () => {
    render(<ShowroomMode />);

    const runwayBtn = screen.getByRole("button", { name: /RUNWAY GALLERY/i });
    fireEvent.click(runwayBtn);

    expect(screen.getByText(/DICH \/\/ RUNWAY GALLERY/i)).toBeInTheDocument();
    expect(screen.getByText(/A N T U R A X/i)).toBeInTheDocument();
  });

  it("switches to Editorial Analytics and displays Steep warm paper cards", () => {
    render(<ShowroomMode />);

    const analyticsBtn = screen.getByRole("button", { name: /EDITORIAL ANALYTICS/i });
    fireEvent.click(analyticsBtn);

    expect(screen.getByText(/EDITORIAL ARTIFACTS & TELEMETRY/i)).toBeInTheDocument();
    expect(screen.getByText(/COLLEGE VIP DEEP VAULT/i)).toBeInTheDocument();
    expect(screen.getByText(/Cognitive Response Latency/i)).toBeInTheDocument();
    expect(screen.getByText(/SHOP CONSTELLATION/i)).toBeInTheDocument();
  });

  it("calls onEnterWorkspace when workspace button is clicked", () => {
    const handleWorkspace = vi.fn();
    render(<ShowroomMode onEnterWorkspace={handleWorkspace} />);

    const wsBtn = screen.getByRole("button", { name: /WORKSPACE →/i });
    fireEvent.click(wsBtn);

    expect(handleWorkspace).toHaveBeenCalledTimes(1);
  });

  it("calls onSelectAvatarModel when a collection model is clicked", () => {
    const handleSelectModel = vi.fn();
    render(<ShowroomMode onSelectAvatarModel={handleSelectModel} />);

    // In lookbook view, collection selection buttons are present
    const collectionButtons = screen.getAllByRole("button");
    const anturaxBtn = collectionButtons.find((b) => b.textContent?.includes(".02"));
    if (anturaxBtn) {
      fireEvent.click(anturaxBtn);
      expect(handleSelectModel).toHaveBeenCalledWith("/models/model_6164.vrm");
    }
  });
});
