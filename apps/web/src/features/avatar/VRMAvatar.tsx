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
import { normalizeVrmAvatar } from "./normalization";
import { getDefaultAvatarForCompanion } from "./avatarRegistry";
import { disposeVrmModel } from "./avatarDisposal";
import { getActiveViseme } from "../audio/textToViseme";
import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";
import type { CompanionId, CompanionState } from "../companion/types";
import type { AvatarThemeId } from "./themes";

export interface VRMAvatarProps {
  companionId: CompanionId;
  state: CompanionState;
  plan?: AssistantTurnPlan;
  reducedMotion: boolean;
  textOnly: boolean;
  jawEnergy?: number | React.MutableRefObject<number>;
  speakingRef?: React.MutableRefObject<boolean>;
  visemeEvents?: React.MutableRefObject<any[]>;
  audioStartTimeRef?: React.MutableRefObject<number>;
  theme?: AvatarThemeId;
  lowPerformance?: boolean;
  /** Code-explanation mode: camera pulls wider and she steps to the left. */
  codeMode?: boolean;
  /** Explicit model URL to load — overrides the default auto-detection. */
  modelUrl?: string | null;
  /** Close-up portrait framing (face, cat ears, and upper bust) for companion panel. Default: true */
  closeUp?: boolean;
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
  try {
    if (vrm.meta?.metaVersion?.startsWith("0") && !(vrm as any).__hinaa_rotated) {
      VRMUtils.rotateVRM0(vrm);
      (vrm as any).__hinaa_rotated = true;
    }
  } catch {
    // Non-fatal.
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
  jawEnergyRef,
  speakingRef,
  visemeEventsRef,
  audioStartTimeRef,
}: {
  vrm: VRM;
  input: VrmExpressionInput & { gesture: string; state: string; codeMode: boolean; closeUp?: boolean };
  jawEnergyRef?: number | React.MutableRefObject<number>;
  speakingRef?: React.MutableRefObject<boolean>;
  visemeEventsRef?: React.MutableRefObject<any[]>;
  audioStartTimeRef?: React.MutableRefObject<number>;
}) {
  const camera = useThree((state) => state.camera);
  const lookTarget = useMemo(() => new THREE.Object3D(), []);
  const metrics = useMemo(() => normalizeVrmAvatar(vrm), [vrm]);
  if (typeof window !== "undefined") {
    (window as any).__HINAA_DEBUG_VRM = { vrm, metrics, camera };
  }

  const frameCountRef = useRef(0);
  const lastParamsRef = useRef({ closeUp: input.closeUp, codeMode: input.codeMode, vrm });

  useFrame((_, rawDelta) => {
    const delta = Math.min(rawDelta, 0.05);
    const time = performance.now() / 1000;

    // Read live jaw energy and speaking status dynamically on EVERY frame
    let liveJaw = 0;
    if (typeof input.jawEnergy === "number") {
      liveJaw = input.jawEnergy;
    }
    if (jawEnergyRef) {
      if (typeof jawEnergyRef === "number") {
        liveJaw = jawEnergyRef;
      } else if ("current" in jawEnergyRef && typeof jawEnergyRef.current === "number") {
        liveJaw = jawEnergyRef.current;
      }
    }
    const isSpeaking =
      (speakingRef && "current" in speakingRef ? speakingRef.current : false) ||
      input.speaking ||
      input.state === "speaking" ||
      liveJaw > 0.03;

    let activeVisemeName: string | undefined;
    let activeVisemeWeight: number | undefined;

    if (isSpeaking && visemeEventsRef?.current && visemeEventsRef.current.length > 0) {
      const audioCtx = (window as any).__hinaaAudioCtx;
      const startTime = audioStartTimeRef?.current ?? 0;
      const playTimeMs = audioCtx ? Math.max(0, (audioCtx.currentTime - startTime) * 1000) : (time * 1000) % 2000;
      const active = getActiveViseme(playTimeMs, visemeEventsRef.current);
      if (active && active.mouth !== "closed") {
        activeVisemeName = active.mouth;
        activeVisemeWeight = active.weight;
      }
    }

    const frameInput: VrmExpressionInput = {
      ...input,
      jawEnergy: liveJaw,
      speaking: isSpeaking,
      viseme: activeVisemeName,
      visemeWeight: activeVisemeWeight,
    };

    // Expressions — face presets + jaw lip-sync + blink.
    const weights = buildVrmExpressionWeights(frameInput);
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
      const leftLowerArm = humanoid.getNormalizedBoneNode(
        VRMHumanBoneName.LeftLowerArm,
      );
      const rightLowerArm = humanoid.getNormalizedBoneNode(
        VRMHumanBoneName.RightLowerArm,
      );
      const leftHand = humanoid.getNormalizedBoneNode(
        VRMHumanBoneName.LeftHand,
      );
      const rightHand = humanoid.getNormalizedBoneNode(
        VRMHumanBoneName.RightHand,
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
      const idleSway = quiet
        ? Math.sin(time * 0.8) * 0.008
        : Math.sin(time * 1.4) * 0.018;
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

      const isVrm1 = Boolean(vrm.meta?.metaVersion?.startsWith("1"));
      // In VRM 1.0, left arm extends along +X, so negative Z rotates arm down.
      // In VRM 0.x, left arm extends along -X, so positive Z rotates arm down.
      const armZSign = isVrm1 ? -1 : 1;

      if (input.gesture === "wave" && rightArm) {
        rightArm.rotation.x = THREE.MathUtils.damp(rightArm.rotation.x, -0.6, 8, delta);
        rightArm.rotation.z = THREE.MathUtils.damp(rightArm.rotation.z, -0.95 * armZSign, 8, delta);
        if (rightLowerArm) {
          rightLowerArm.rotation.y = THREE.MathUtils.damp(rightLowerArm.rotation.y, -1.25, 8, delta);
        }
        if (rightHand) {
          rightHand.rotation.z = THREE.MathUtils.damp(
            rightHand.rotation.z,
            Math.sin(time * 7) * 0.35,
            12,
            delta,
          );
        }
      } else if (input.gesture === "celebrate") {
        if (leftArm) {
          leftArm.rotation.x = THREE.MathUtils.damp(leftArm.rotation.x, -0.8, 8, delta);
          leftArm.rotation.z = THREE.MathUtils.damp(leftArm.rotation.z, 1.8 * armZSign, 8, delta);
        }
        if (rightArm) {
          rightArm.rotation.x = THREE.MathUtils.damp(rightArm.rotation.x, -0.8, 8, delta);
          rightArm.rotation.z = THREE.MathUtils.damp(rightArm.rotation.z, -1.8 * armZSign, 8, delta);
        }
        if (leftLowerArm) {
          leftLowerArm.rotation.y = THREE.MathUtils.damp(leftLowerArm.rotation.y, 0.6, 8, delta);
        }
        if (rightLowerArm) {
          rightLowerArm.rotation.y = THREE.MathUtils.damp(rightLowerArm.rotation.y, -0.6, 8, delta);
        }
      } else if (input.gesture === "explain" && rightArm) {
        rightArm.rotation.x = THREE.MathUtils.damp(
          rightArm.rotation.x,
          -0.5 + Math.sin(time * 2.6) * 0.15,
          8,
          delta,
        );
        rightArm.rotation.z = THREE.MathUtils.damp(rightArm.rotation.z, -0.45 * armZSign, 8, delta);
        if (rightLowerArm) {
          rightLowerArm.rotation.y = THREE.MathUtils.damp(
            rightLowerArm.rotation.y,
            -0.65 + Math.sin(time * 2.8) * 0.12,
            8,
            delta,
          );
        }
        if (rightHand) {
          rightHand.rotation.z = THREE.MathUtils.damp(
            rightHand.rotation.z,
            Math.sin(time * 2.6) * 0.15,
            8,
            delta,
          );
        }
      } else {
        // Natural resting companion pose: arms relaxed alongside torso, hands resting naturally
        if (leftArm) {
          leftArm.rotation.x = THREE.MathUtils.damp(leftArm.rotation.x, 0.08, 6, delta);
          leftArm.rotation.y = THREE.MathUtils.damp(leftArm.rotation.y, 0, 6, delta);
          leftArm.rotation.z = THREE.MathUtils.damp(leftArm.rotation.z, (1.22 - idleSway) * armZSign, 6, delta);
        }
        if (rightArm) {
          rightArm.rotation.x = THREE.MathUtils.damp(rightArm.rotation.x, 0.08, 6, delta);
          rightArm.rotation.y = THREE.MathUtils.damp(rightArm.rotation.y, 0, 6, delta);
          rightArm.rotation.z = THREE.MathUtils.damp(rightArm.rotation.z, (-1.22 + idleSway) * armZSign, 6, delta);
        }
        if (leftLowerArm) {
          leftLowerArm.rotation.x = THREE.MathUtils.damp(leftLowerArm.rotation.x, 0.15, 6, delta);
          leftLowerArm.rotation.y = THREE.MathUtils.damp(leftLowerArm.rotation.y, 0.15 * -armZSign, 6, delta);
          leftLowerArm.rotation.z = THREE.MathUtils.damp(leftLowerArm.rotation.z, 0.1 * armZSign, 6, delta);
        }
        if (rightLowerArm) {
          rightLowerArm.rotation.x = THREE.MathUtils.damp(rightLowerArm.rotation.x, 0.15, 6, delta);
          rightLowerArm.rotation.y = THREE.MathUtils.damp(rightLowerArm.rotation.y, -0.15 * -armZSign, 6, delta);
          rightLowerArm.rotation.z = THREE.MathUtils.damp(rightLowerArm.rotation.z, -0.1 * armZSign, 6, delta);
        }
        if (leftHand) {
          leftHand.rotation.x = THREE.MathUtils.damp(leftHand.rotation.x, 0, 6, delta);
          leftHand.rotation.y = THREE.MathUtils.damp(leftHand.rotation.y, 0, 6, delta);
          leftHand.rotation.z = THREE.MathUtils.damp(leftHand.rotation.z, 0, 6, delta);
        }
        if (rightHand) {
          rightHand.rotation.x = THREE.MathUtils.damp(rightHand.rotation.x, 0, 6, delta);
          rightHand.rotation.y = THREE.MathUtils.damp(rightHand.rotation.y, 0, 6, delta);
          rightHand.rotation.z = THREE.MathUtils.damp(rightHand.rotation.z, 0, 6, delta);
        }
      }
      // Breathing — subtle chest/hips rise. Quieter while listening.
      const breath = Math.sin(time * 1.4) * (quiet ? 0.0018 : 0.004);
      if (chest) chest.position.y = breath;
      if (hips) {
        hips.position.x = 0;
        hips.position.z = 0;
        hips.position.y = THREE.MathUtils.clamp(-breath, -0.015, 0.015);
      }
    }

    vrm.update(delta);

    // Dynamic Landmark Camera: Frame camera directly to the character's true face position
    // AFTER vrm.update has fully resolved humanoid bone solvers, inverse kinematics, and matrix transforms.
    const paramsChanged =
      lastParamsRef.current.closeUp !== input.closeUp ||
      lastParamsRef.current.codeMode !== input.codeMode ||
      lastParamsRef.current.vrm !== vrm;

    if (frameCountRef.current < 5 || paramsChanged) {
      frameCountRef.current += 1;
      if (paramsChanged) frameCountRef.current = 1;
      lastParamsRef.current = { closeUp: input.closeUp, codeMode: input.codeMode, vrm };
      const humanoid = vrm.humanoid;
      if (humanoid) {
        const head = humanoid.getNormalizedBoneNode(VRMHumanBoneName.Head);
        const leftEye = humanoid.getNormalizedBoneNode(VRMHumanBoneName.LeftEye) || head;
        if (head) {
          head.updateWorldMatrix(true, false);
          const headMat = head.matrixWorld.elements;
          const headX = headMat[12];
          const headY = headMat[13];
          const headZ = headMat[14];

          let eyeX = headX;
          let eyeY = headY;
          let eyeZ = headZ;
          if (leftEye) {
            leftEye.updateWorldMatrix(true, false);
            const eyeMat = leftEye.matrixWorld.elements;
            eyeX = eyeMat[12];
            eyeY = eyeMat[13];
            eyeZ = eyeMat[14];
          }

          const faceCenterX = (headX + eyeX) / 2;
          const faceCenterY = (headY + eyeY) / 2;
          const faceCenterZ = (headZ + eyeZ) / 2;
          const isCloseUp = input.closeUp ?? true;

          const camDistance = isCloseUp ? 1.18 : 1.75;
          const camYOffset = isCloseUp ? 0.04 : 0.10;

          camera.position.set(
            faceCenterX + (input.codeMode ? -0.35 : 0),
            faceCenterY + camYOffset,
            faceCenterZ + camDistance
          );
          camera.lookAt(new THREE.Vector3(
            faceCenterX,
            faceCenterY + (isCloseUp ? 0.01 : -0.04),
            faceCenterZ
          ));
          camera.updateProjectionMatrix();
        }
      }
    }
  });

  const baseX = (input.codeMode ? -0.42 : 0) + metrics.offset[0] * metrics.scale;
  // Use the normalized Y offset so different VRM rigs (different bone pivots)
  // all land correctly in the camera frame instead of floating or sinking.
  const baseY = metrics.offset[1] * metrics.scale;
  const baseZ = metrics.offset[2] * metrics.scale;
  const finalScale = metrics.scale * (input.codeMode ? 1.0 : 1.12);

  return (
    <group
      position={[baseX, baseY, baseZ]}
      scale={finalScale}
    >
      <primitive object={lookTarget} />
      <primitive object={vrm.scene} />
    </group>
  );
}

function VrmModel({
  url,
  input,
  jawEnergyRef,
  speakingRef,
  visemeEventsRef,
  audioStartTimeRef,
  onReady,
  onError,
}: {
  url: string;
  input: VrmExpressionInput & { gesture: string; state: string; codeMode: boolean; closeUp?: boolean };
  jawEnergyRef?: number | React.MutableRefObject<number>;
  speakingRef?: React.MutableRefObject<boolean>;
  visemeEventsRef?: React.MutableRefObject<any[]>;
  audioStartTimeRef?: React.MutableRefObject<number>;
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
          disposeVrmModel(loaded);
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

  // Free GPU resources when the model leaves the render loop.
  useEffect(() => {
    return () => {
      if (vrm) disposeVrmModel(vrm);
    };
  }, [vrm]);

  if (!vrm) return null;
  return (
    <VrmRig
      vrm={vrm}
      input={input}
      jawEnergyRef={jawEnergyRef}
      speakingRef={speakingRef}
      visemeEventsRef={visemeEventsRef}
      audioStartTimeRef={audioStartTimeRef}
    />
  );
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
    // When the parent explicitly passes a modelUrl, use it directly (no HEAD probe needed).
    if (props.modelUrl !== undefined) {
      setModelUrl(props.modelUrl ?? null);
      setFailed(false);
      setModelLoading(true);
      return;
    }
    // Fallback: auto-detect the best available model.
    let alive = true;
    void resolveCachedModelUrl().then((url) => {
      if (alive) setModelUrl(url);
    });
    return () => {
      alive = false;
    };
  }, [props.modelUrl]);

  const resolvedJawEnergy =
    typeof props.jawEnergy === "number"
      ? props.jawEnergy
      : (props.jawEnergy && typeof props.jawEnergy === "object" && "current" in props.jawEnergy)
        ? props.jawEnergy.current
        : 0;

  const performance = usePerformanceClock({
    plan: props.plan,
    jawEnergy: resolvedJawEnergy,
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
    return <ProceduralAvatar {...props} jawEnergy={resolvedJawEnergy} />;
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
    closeUp?: boolean;
  } = {
    emotion,
    facePreset: props.plan?.performance.facePreset,
    intensity: props.plan?.emotion.intensity ?? 0.5,
    jawEnergy: resolvedJawEnergy,
    blinking: performance.blinking,
    speaking: props.state === "speaking",
    reducedMotion: props.reducedMotion || Boolean(props.lowPerformance),
    gesture,
    state: props.state,
    codeMode: Boolean(props.codeMode),
    closeUp: Boolean(props.closeUp ?? true),
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
              position: [0, 0.54, 0.90],
              fov: (props.closeUp ?? true) ? 32 : 38,
            }}
          >
            <ambientLight intensity={0.75} />
            <directionalLight position={[1.5, 2.5, 2]} intensity={1.1} />
            <directionalLight position={[-2, 1, -1]} intensity={0.25} />
            <ContextLossGuard onLost={handleContextLost} />
            <ModelErrorBoundary onError={handleModelError}>
              <VrmModel
                url={modelUrl}
                input={input}
                jawEnergyRef={props.jawEnergy}
                speakingRef={props.speakingRef}
                visemeEventsRef={props.visemeEvents}
                audioStartTimeRef={props.audioStartTimeRef}
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
