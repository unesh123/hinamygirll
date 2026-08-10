import {
  Component,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import * as THREE from "three";
import {
  VRMLoaderPlugin,
  VRM,
  VRMUtils,
  VRMHumanBoneName,
} from "@pixiv/three-vrm";
import { ProceduralAvatar } from "./ProceduralAvatar";
import { usePerformanceClock } from "./usePerformanceClock";
import {
  buildVrmExpressionWeights,
  VRM_EXPRESSION_KEYS,
  type VrmExpressionInput,
} from "./vrmExpressionMap";
import { optimizeVrm } from "./vrmOptimizer";
import type { AvatarThemeId } from "./themes";
import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";
import type { CompanionId, CompanionState } from "../companion/types";

export interface VRMAvatarProps {
  companionId: CompanionId;
  state: CompanionState;
  plan?: AssistantTurnPlan;
  reducedMotion: boolean;
  textOnly: boolean;
  jawEnergy?: number;
  theme?: AvatarThemeId;
  lowPerformance?: boolean;
  /** Code-explanation mode: camera pulls wider and she steps to the left. */
  codeMode?: boolean;
}

/**
 * Model source order:
 *  1. /models/hinaa.vrm — drop your own VRoid Studio export here (see
 *     ASSET_LICENSES.md). Auto-detected at runtime.
 *  2. Official three-vrm example model (VRM 1.0, permissive sample) so the
 *     full pipeline works out of the box.
 */
const LOCAL_VRM_URL = "/models/hinaa.vrm";
const SAMPLE_VRM_URL =
  "https://raw.githubusercontent.com/pixiv/three-vrm/dev/packages/three-vrm/examples/models/VRM1_Constraint_Twist_Sample.vrm";

async function resolveVrmModelUrl(): Promise<string | null> {
  for (const url of [LOCAL_VRM_URL, SAMPLE_VRM_URL]) {
    try {
      const response = await fetch(url, {
        method: "HEAD",
        cache: "no-store",
        signal: AbortSignal.timeout(4000),
      });
      const type = response.headers.get("content-type") ?? "";
      // Dev SPA fallback returns index.html (text/html) for missing files.
      if (response.ok && !type.includes("text/html")) return url;
    } catch {
      // Unreachable, timeout, or wrong content type — try the next source.
    }
  }
  return null;
}

let cachedModelUrl: string | null | undefined;
async function resolveCachedModelUrl(): Promise<string | null> {
  if (cachedModelUrl === undefined) cachedModelUrl = await resolveVrmModelUrl();
  return cachedModelUrl;
}

let sharedGltfLoader: GLTFLoader | null = null;

/** Shared GLTFLoader with the VRM plugin registered exactly once. */
function getGltfLoader(): GLTFLoader {
  if (!sharedGltfLoader) {
    sharedGltfLoader = new GLTFLoader();
    sharedGltfLoader.register((parser) => new VRMLoaderPlugin(parser));
  }
  return sharedGltfLoader;
}

/**
 * Load the VRM and OPTIMIZE IT BEFORE THE FIRST FRAME.
 *
 * This ordering is load-bearing: the Libby_free model ships ~33 textures
 * (several 2048×2048 → ~176 MB VRAM) and 456 morph targets. If those are
 * uploaded to the GPU at full size, weak/integrated GPUs drop the WebGL
 * context and the whole 3D stage silently falls back to the 2D avatar.
 * Downscaling textures + pruning morphs here — before the model ever enters
 * the render loop — keeps the first frame small enough to survive.
 */
async function loadAndOptimizeVrm(url: string): Promise<VRM> {
  const gltf = await getGltfLoader().loadAsync(url);
  const vrm = (gltf as unknown as { userData: { vrm?: VRM } }).userData.vrm;
  if (!vrm) throw new Error("No VRM data in loaded asset");
  try {
    VRMUtils.removeUnnecessaryVertices(vrm.scene);
  } catch {
    // Non-fatal: keep the model as loaded.
  }
  try {
    VRMUtils.combineSkeletons(vrm.scene);
  } catch {
    // Non-fatal.
  }
  try {
    optimizeVrm(vrm, { keepExpressionNames: VRM_EXPRESSION_KEYS });
  } catch {
    // Non-fatal: model keeps its original resources.
  }
  return vrm;
}

/** One-shot gesture oscillators keyed by semantic gesture name. */
function gestureHeadTarget(
  gesture: string,
  time: number,
  intensity: number,
): { x: number; y: number; z: number } {
  const t = time;
  switch (gesture) {
    case "small_nod":
      return { x: Math.sin(t * 4.2) * 0.12 * intensity, y: 0, z: 0 };
    case "head_shake":
      return { x: 0, y: Math.sin(t * 5) * 0.28 * intensity, z: 0 };
    case "gentle_head_tilt":
      return { x: 0, y: 0, z: -0.12 * intensity };
    case "reassure":
      return { x: Math.sin(t * 2.4) * 0.1 * intensity, y: 0, z: 0.03 };
    case "listening_lean":
      return { x: 0.09, y: 0, z: 0.07 };
    case "wave":
      return { x: 0, y: 0, z: 0 };
    default:
      return { x: 0, y: 0, z: 0 };
  }
}

/**
 * Catches R3F subtree failures (model parse/load errors) and notifies the
 * parent so the procedural girl can take over instead of a blank canvas.
 */
class ModelErrorBoundary extends Component<
  { onError: () => void; children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }

  componentDidCatch(): void {
    this.props.onError();
  }

  render(): ReactNode {
    return this.state.failed ? null : this.props.children;
  }
}

/**
 * Cheap, synchronous WebGL probe — idempotent and safe to call during render.
 * In headless/GPU-less environments context creation can fail outright, which
 * no canvas listener would catch; probing up front routes to the procedural
 * girl before a dead black canvas ever appears.
 */
function isWebGLAvailable(): boolean {
  if (typeof document === "undefined") return false;
  try {
    const canvas = document.createElement("canvas");
    const gl = (canvas.getContext("webgl2") ||
      canvas.getContext("webgl") ||
      canvas.getContext("experimental-webgl")) as
      | WebGLRenderingContext
      | WebGL2RenderingContext
      | null;
    if (!gl) return false;
    // Release the probe context immediately: a second live WebGL context
    // competes for GPU memory / context slots and can itself cause the
    // renderer's context to be lost.
    gl.getExtension("WEBGL_lose_context")?.loseContext();
    return true;
  } catch {
    return false;
  }
}

/**
 * Watches the WebGL canvas for context loss. A 19 MB VRM on an integrated GPU
 * (high DPR + antialias) can drop the GPU context, which leaves a black canvas
 * behind — silently. When that happens we notify the parent so the procedural
 * girl takes over instead of a dead stage.
 */
function ContextLossGuard({ onLost }: { onLost: () => void }) {
  const gl = useThree((state) => state.gl);
  useEffect(() => {
    const canvas = gl.domElement;
    const handleContextLost = (event: Event) => {
      event.preventDefault();
      onLost();
    };
    canvas.addEventListener("webglcontextlost", handleContextLost);
    return () =>
      canvas.removeEventListener("webglcontextlost", handleContextLost);
  }, [gl, onLost]);
  return null;
}

function VrmRig({
  vrm,
  input,
}: {
  vrm: VRM;
  input: VrmExpressionInput & { gesture: string; state: string; codeMode: boolean };
}) {
  const lookTarget = useMemo(() => new THREE.Object3D(), []);

  useEffect(() => {
    // VRM 0.x reports metaVersion "0.0" — rotate it into the +Z-facing pose.
    if (vrm.meta?.metaVersion?.startsWith("0")) VRMUtils.rotateVRM0(vrm);
  }, [vrm]);

  useFrame((_, rawDelta) => {
    const delta = Math.min(rawDelta, 0.05);
    const time = performance.now() / 1000;

    // Expressions — face presets + jaw lip-sync + blink.
    // NOTE: `manager.expressions` is an *array* (VRMExpression[]), so the old
    // `key in manager.expressions` guard was always false and no expression
    // was ever applied. `setValue` resolves the expression by name internally
    // and is a safe no-op for presets the model does not ship.
    const weights = buildVrmExpressionWeights(input);
    const manager = vrm.expressionManager;
    if (manager) {
      try {
        for (const key of VRM_EXPRESSION_KEYS) {
          manager.setValue(key, weights[key]);
        }
        manager.update();
      } catch {
        // Expression API drift — never let it break the frame.
      }
    }

    // Gaze — emotion-aware look target with gentle drift.
    if (vrm.lookAt) {
      let targetX = Math.sin(time * 0.4) * 0.18;
      let targetY = 0.05;
      let targetZ = 1;
      if (input.state === "listening") {
        // Listening: eyes settle and focus on you, only micro-drift.
        targetX = Math.sin(time * 0.9) * 0.06;
        targetY = 0.08;
        targetZ = 1.4;
      } else if (input.codeMode) {
        // Code mode: she looks toward the editor panel on her right.
        targetX = 0.55 + Math.sin(time * 0.6) * 0.12;
        targetY = 0.05;
        targetZ = 1;
      } else if (input.emotion === "shy") {
        targetX = 0;
        targetY = -0.25;
      } else if (input.emotion === "thinking") {
        targetX = Math.sin(time * 0.7) * 0.5;
        targetY = -0.08;
      } else if (input.emotion === "surprised") {
        targetX = 0;
        targetY = 0.12;
      } else if (input.emotion === "sad") {
        targetY = -0.15;
      }
      lookTarget.position.set(targetX, targetY, targetZ);
      vrm.lookAt.target = lookTarget;
    }

    // Head + arms — gestures and idle sway.
    const humanoid = vrm.humanoid;
    if (humanoid) {
      const head = humanoid.getNormalizedBoneNode(VRMHumanBoneName.Head);
      const leftArm = humanoid.getNormalizedBoneNode(
        VRMHumanBoneName.LeftUpperArm,
      );
      const rightArm = humanoid.getNormalizedBoneNode(
        VRMHumanBoneName.RightUpperArm,
      );
      const chest = humanoid.getNormalizedBoneNode(VRMHumanBoneName.Chest);
      const hips = humanoid.getNormalizedBoneNode(VRMHumanBoneName.Hips);

      const headTarget = gestureHeadTarget(input.gesture, time, input.intensity);
      // Listening: shoulders settle — idle sway nearly stops, head gives a
      // soft attentive tilt toward you instead of random wander.
      const quiet = input.state === "listening";
      const idleY = quiet
        ? Math.sin(time * 0.8) * 0.005
        : Math.sin(time * 0.5) * 0.02;
      const settled = quiet
        ? { x: 0.08, y: 0, z: 0.06 }
        : { x: headTarget.x, y: headTarget.y, z: headTarget.z };
      if (head) {
        head.rotation.x = THREE.MathUtils.damp(
          head.rotation.x,
          settled.x,
          6,
          delta,
        );
        head.rotation.y = THREE.MathUtils.damp(
          head.rotation.y,
          settled.y + idleY,
          6,
          delta,
        );
        head.rotation.z = THREE.MathUtils.damp(
          head.rotation.z,
          settled.z,
          6,
          delta,
        );
      }
      if (input.gesture === "wave" && rightArm) {
        rightArm.rotation.x = THREE.MathUtils.damp(rightArm.rotation.x, -1.6, 8, delta);
        rightArm.rotation.z = THREE.MathUtils.damp(
          rightArm.rotation.z,
          Math.sin(time * 6) * 0.45,
          10,
          delta,
        );
      } else if (input.gesture === "celebrate") {
        if (leftArm) {
          leftArm.rotation.x = THREE.MathUtils.damp(leftArm.rotation.x, -1.2, 8, delta);
          leftArm.rotation.z = THREE.MathUtils.damp(leftArm.rotation.z, 0.3 + Math.sin(time * 5) * 0.12, 8, delta);
        }
        if (rightArm) {
          rightArm.rotation.x = THREE.MathUtils.damp(rightArm.rotation.x, -1.2, 8, delta);
          rightArm.rotation.z = THREE.MathUtils.damp(rightArm.rotation.z, -0.3 - Math.sin(time * 5) * 0.12, 8, delta);
        }
      } else if (input.gesture === "explain" && rightArm) {
        rightArm.rotation.x = THREE.MathUtils.damp(
          rightArm.rotation.x,
          -0.8 + Math.sin(time * 2.6) * 0.25,
          8,
          delta,
        );
      }
      // Breathing — subtle chest/hips rise. Quieter while listening.
      const breath = Math.sin(time * 1.4) * (quiet ? 0.0018 : 0.004);
      if (chest) chest.position.y = breath;
      if (hips) hips.position.y = -breath;
    }

    vrm.update(delta);
  });

  return (
    <group
      position={input.codeMode ? [-0.42, -0.25, 0] : [0, -0.25, 0]}
      scale={input.codeMode ? 1.02 : 1.15}
    >
      <primitive object={lookTarget} />
      <primitive object={vrm.scene} />
    </group>
  );
}

function VrmModel({
  url,
  input,
  onReady,
  onError,
}: {
  url: string;
  input: VrmExpressionInput & { gesture: string; state: string; codeMode: boolean };
  onReady: () => void;
  onError: () => void;
}) {
  const [vrm, setVrm] = useState<VRM | null>(null);

  useEffect(() => {
    let alive = true;
    setVrm(null);
    loadAndOptimizeVrm(url)
      .then((loaded) => {
        if (!alive) {
          // Superseded (StrictMode double-run or unmount) — free it now.
          VRMUtils.deepDispose(loaded.scene);
          return;
        }
        setVrm(loaded);
        onReady();
      })
      .catch(() => {
        if (alive) onError();
      });
    return () => {
      alive = false;
    };
  }, [url, onReady, onError]);

  // Free GPU resources when the model leaves the render loop. VrmRig does
  // not dispose — VrmModel is the single owner of the loaded VRM.
  useEffect(() => {
    return () => {
      if (vrm) VRMUtils.deepDispose(vrm.scene);
    };
  }, [vrm]);

  if (!vrm) return null;
  return <VrmRig vrm={vrm} input={input} />;
}

function CameraRig() {
  const camera = useThree((state) => state.camera);
  const look = useMemo(() => new THREE.Vector3(0, 1.25, 0), []);
  useEffect(() => {
    camera.lookAt(look);
  }, [camera, look]);
  return null;
}

export function VRMAvatar(props: VRMAvatarProps) {
  const [modelUrl, setModelUrl] = useState<string | null | undefined>(undefined);
  const [failed, setFailed] = useState(false);
  const [glContextLost, setGlContextLost] = useState(false);
  const [modelLoading, setModelLoading] = useState(true);
  const [webglAvailable] = useState<boolean>(() => isWebGLAvailable());
  const handleModelReady = useCallback(() => setModelLoading(false), []);
  const handleModelError = useCallback(() => setFailed(true), []);
  // First context loss remounts the canvas with conservative GPU settings
  // (dpr 1, no antialias, low-power). A second loss means the GPU truly
  // cannot drive the model, so the procedural girl takes over.
  const contextLossAttempts = useRef(0);
  const handleContextLost = useCallback(() => {
    if (contextLossAttempts.current >= 1) {
      setFailed(true);
      return;
    }
    contextLossAttempts.current += 1;
    setModelLoading(true);
    setGlContextLost(true);
  }, []);

  useEffect(() => {
    let alive = true;
    void resolveCachedModelUrl().then((url) => {
      if (alive) setModelUrl(url);
    });
    return () => {
      alive = false;
    };
  }, []);

  const performance = usePerformanceClock({
    plan: props.plan,
    jawEnergy: props.jawEnergy,
    reducedMotion: props.reducedMotion || Boolean(props.lowPerformance),
    interrupted: props.state === "interrupted",
  });
  const emotion =
    performance.emotion !== "neutral"
      ? performance.emotion
      : (props.plan?.emotion.primary ?? "neutral");
  const gesture =
    performance.gesture !== "none"
      ? performance.gesture
      : (props.plan?.performance.gesture ?? "none");

  // No model at all, a hard load failure, or WebGL unavailable entirely →
  // the procedural girl takes over instead of a blank canvas. (A transient
  // GPU context loss does NOT land here — it remounts the canvas with
  // conservative settings first; only a second loss marks `failed`.)
  if (modelUrl === null || failed || !webglAvailable) {
    return <ProceduralAvatar {...props} />;
  }

  if (props.textOnly) {
    return (
      <div className="avatar-fallback" data-testid="text-only-avatar">
        <span aria-hidden="true">✦</span>
        <strong>Text-only mode</strong>
        <small>Avatar motion is paused. Conversation controls still work.</small>
      </div>
    );
  }

  const input: VrmExpressionInput & {
    gesture: string;
    state: string;
    codeMode: boolean;
  } = {
    emotion,
    facePreset: props.plan?.performance.facePreset,
    intensity: props.plan?.emotion.intensity ?? 0.5,
    jawEnergy: props.jawEnergy ?? 0,
    blinking: performance.blinking,
    speaking: props.state === "speaking",
    reducedMotion: props.reducedMotion || Boolean(props.lowPerformance),
    gesture,
    state: props.state,
    codeMode: Boolean(props.codeMode),
  };

  return (
    <div
      className="vrm-stage"
      data-engine="vrm-avatar-v1"
      data-state={props.state}
      data-emotion={emotion}
      data-gesture={gesture}
      aria-hidden="true"
    >
      {modelUrl === undefined ? (
        <div className="vrm-loading">
          <span className="vrm-loading-spinner" aria-hidden="true" />
          <small>Loading her 3D model…</small>
        </div>
      ) : (
        <>
          <Canvas
            key={glContextLost ? "conservative" : "full"}
            className="vrm-canvas"
            dpr={glContextLost || props.lowPerformance ? 1 : [1, 1.5]}
            gl={{
              antialias: !glContextLost,
              alpha: true,
              powerPreference: glContextLost ? "low-power" : "default",
            }}
            camera={{
              // Code mode: camera pulls slightly wider so she and the editor
              // panel share the frame; she steps left inside the rig.
              position: props.codeMode ? [0, 1.6, 2.15] : [0, 1.55, 1.45],
              fov: props.codeMode ? 44 : 38,
            }}
          >
            <ambientLight intensity={0.75} />
            <directionalLight position={[1.5, 2.5, 2]} intensity={1.1} />
            <directionalLight position={[-2, 1, -1]} intensity={0.25} />
            <ContextLossGuard onLost={handleContextLost} />
            <CameraRig />
            <ModelErrorBoundary onError={handleModelError}>
              <VrmModel
                url={modelUrl}
                input={input}
                onReady={handleModelReady}
                onError={handleModelError}
              />
            </ModelErrorBoundary>
          </Canvas>
          {modelLoading && (
            <div className="vrm-loading vrm-loading-overlay">
              <span className="vrm-loading-spinner" aria-hidden="true" />
              <small>Loading her 3D model…</small>
            </div>
          )}
        </>
      )}
    </div>
  );
}
