import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AvatarPresence, resolvePoseOffsets } from "./AvatarPresence";
import { Vector3 } from "three";

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

describe("default model pose", () => {
  it("gives the default Hinaa rig its tuned relaxed pose, not the generic one", () => {
    const tuned = resolvePoseOffsets("/models/hinaa.vrm");
    const generic = resolvePoseOffsets("/models/unknown-rig.vrm");
    const defaults = resolvePoseOffsets("/models/hinaa-original.vrm");
    expect(defaults).not.toBe(tuned);
    expect(defaults).not.toBe(generic);
  });
  it("keeps the default rig's wrists outside the dress rather than folding them into the torso", () => {
    const pose = resolvePoseOffsets("/models/hinaa-original.vrm");
    // Shipped VRM shoulder, upper arm, forearm and wrist rest translations.
    for (const side of ["left", "right"] as const) {
      const sign = side === "left" ? -1 : 1;
      const shoulder = pose[`${side}Shoulder`];
      const upper = shoulder.clone().multiply(pose[`${side}UpperArm`]);
      const lower = upper.clone().multiply(pose[`${side}LowerArm`]);
      const wrist = new Vector3(sign * 0.022395, 0.105686, 0.029969)
        .add(new Vector3(sign * 0.086160, -0.012260, 0).applyQuaternion(shoulder))
        .add(new Vector3(sign * 0.219853, 0, 0).applyQuaternion(upper))
        .add(new Vector3(sign * 0.214685, 0.000002, -0.000376).applyQuaternion(lower));
      expect(wrist.x * sign).toBeGreaterThan(0.28);
      expect(wrist.y).toBeLessThan(0);
      expect(Math.abs(shoulder.z)).toBeLessThan(0.1);
    }
  });
});

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

