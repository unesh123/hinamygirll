import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AvatarPresence } from "./AvatarPresence";

const loading = vi.hoisted(() => ({ errors: [] as Array<() => void> }));
vi.mock("three/examples/jsm/loaders/GLTFLoader.js", () => ({
  GLTFLoader: class {
    register() {}
    load(_url: string, _success: unknown, _progress: unknown, failure: () => void) { loading.errors.push(failure); }
  },
}));
vi.mock("@react-three/fiber", () => ({
  Canvas: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  useFrame: () => undefined,
  useThree: (select?: (state: unknown) => unknown) => {
    const state = { camera: {}, size: { width: 393 }, setDpr: vi.fn() };
    return select ? select(state) : state;
  },
}));
vi.mock("@react-three/drei", () => ({ ContactShadows: () => null }));
vi.mock("./FullscreenCompanionOverlay", () => ({ FullscreenCompanionOverlay: () => null }));
beforeEach(() => { loading.errors.length = 0; });

describe("avatar recovery", () => {
  it("shows load failure and retries without affecting the chat state", () => {
    render(<AvatarPresence mode="portrait" state="idle" modelUrl="/model.vrm" />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading Hina");
    act(() => loading.errors[0]());
    expect(screen.getByRole("alert")).toHaveTextContent("Your chat is still available");
    fireEvent.click(screen.getByRole("button", { name: "Retry 3D model" }));
    expect(screen.getByRole("status")).toHaveTextContent("Loading Hina");
    expect(loading.errors).toHaveLength(2);
    act(() => loading.errors[0]());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    act(() => loading.errors[1]());
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("restarts the loading state when the selected model changes", () => {
    const view = render(<AvatarPresence mode="portrait" state="idle" modelUrl="/model.vrm" />);
    act(() => loading.errors[0]());
    view.rerender(<AvatarPresence mode="portrait" state="idle" modelUrl="/different.vrm" />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Loading Hina");
  });

  it("renders the walking toggle button and responds to clicks", () => {
    const onToggleWalk = vi.fn();
    const { rerender } = render(
      <AvatarPresence mode="portrait" state="idle" modelUrl="/model.vrm" isWalking={false} onToggleWalk={onToggleWalk} />,
    );
    const walkBtn = screen.getByRole("button", { name: "Start procedural walking" });
    expect(walkBtn).toBeInTheDocument();
    expect(walkBtn).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(walkBtn);
    expect(onToggleWalk).toHaveBeenCalledTimes(1);

    rerender(
      <AvatarPresence mode="portrait" state="idle" modelUrl="/model.vrm" isWalking={true} onToggleWalk={onToggleWalk} />,
    );
    const activeWalkBtn = screen.getByRole("button", { name: "Stop procedural walking" });
    expect(activeWalkBtn).toBeInTheDocument();
    expect(activeWalkBtn).toHaveAttribute("aria-pressed", "true");
  });
});

