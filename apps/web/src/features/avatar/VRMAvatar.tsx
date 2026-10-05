import {
  Component,
  memo,
  useCallback,
  useContext,
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
import { SpeechPlaybackContext, sampleSpeechPlayback } from "../audio/speechPlaybackBridge";
import { PerformanceDirector, type PerformanceState } from "./performanceSubstrate";
import {
  buildVrmExpressionWeights,
  VRM_EXPRESSION_KEYS,
  type VrmExpressionInput,
} from "./vrmExpressionMap";
import { optimizeVrm, DEFAULT_KEEP_EXPRESSIONS } from "./vrmOptimizer";
import { normalizeVrmAvatar } from "./normalization";
import { getDefaultAvatarForCompanion } from "./avatarRegistry";
import { disposeVrmModel } from "./avatarDisposal";
import { getActiveViseme } from "../audio/textToViseme";
import { playFootstepSound } from "../../lib/uiSound";
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
  speechBridge?: React.MutableRefObject<any>;
  theme?: AvatarThemeId;
  lowPerformance?: boolean;
  /** Code-explanation mode: camera pulls wider and she steps to the left. */
  codeMode?: boolean;
  /** Explicit model URL to load — overrides the default auto-detection. */
  modelUrl?: string | null;
  /** Close-up portrait framing (face, cat ears, and upper bust) for companion panel. Default: true */
  closeUp?: boolean;
  /** Walk mode: activates natural procedural walking gait, leg swing, knee flexion, hip sway, and stage roaming. */
  walkMode?: boolean;
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

// In production (Vercel), VRM files are served from GitHub raw CDN via
// VITE_VRM_CDN_BASE env var to stay under Vercel's 100 MB file size limit.
// Set this in Vercel dashboard: VITE_VRM_CDN_BASE=https://raw.githubusercontent.com/unesh123/hinamygirll/feat/hinaa-ui-polish/apps/web/public/models
const CDN_BASE = import.meta.env.VITE_VRM_CDN_BASE as string | undefined;
const CDN_VRM_URL = CDN_BASE ? `${CDN_BASE.replace(/\/$/, "")}/hinaa.vrm` : null;

async function resolveVrmModelUrl(): Promise<string | null> {
  const candidates = [
    ...(CDN_VRM_URL ? [CDN_VRM_URL] : []),
    LOCAL_VRM_URL,
    SAMPLE_VRM_URL,
  ];
  for (const url of candidates) {
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

// Reusable scratch vectors to prevent 240+ GC allocations per second in useFrame
const _scratchHeadPos = new THREE.Vector3();
const _scratchEyePos = new THREE.Vector3();
const _scratchLPos = new THREE.Vector3();
const _scratchRPos = new THREE.Vector3();

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
  const safeUrl = url.includes("%") ? url : encodeURI(url);
  const gltf = await getGltfLoader().loadAsync(safeUrl);
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
    optimizeVrm(vrm, { keepExpressionNames: DEFAULT_KEEP_EXPRESSIONS });
  } catch {
    // Non-fatal: model keeps its original resources.
  }
  try {
    if ((vrm.meta?.metaVersion?.startsWith("0") || !vrm.meta?.metaVersion) && !(vrm as any).__hinaa_rotated) {
      VRMUtils.rotateVRM0(vrm);
      (vrm as any).__hinaa_rotated = true;
    }
  } catch {
    // Non-fatal.
  }
  try {
    vrm.scene.traverse((obj) => {
      if ((obj as THREE.Mesh).isMesh || (obj as any).isSkinnedMesh) {
        obj.visible = true;
        obj.layers.enable(0);
        obj.frustumCulled = false;
      }
    });
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
    case "thinking":
      return { x: -0.06 * intensity, y: Math.sin(t * 1.3) * 0.07 * intensity, z: -0.09 * intensity };
    case "agree":
      return { x: Math.sin(t * 4.8) * 0.15 * intensity, y: 0, z: 0.02 * intensity };
    case "point":
      return { x: -0.04 * intensity, y: 0.05 * intensity, z: 0 };
    case "shy":
      return { x: 0.07 * intensity, y: -0.04 * intensity, z: -0.11 * intensity };
    case "curious":
      return { x: 0.04 * intensity, y: 0.06 * intensity, z: 0.13 * intensity };
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
  speechBridgeRef,
}: {
  vrm: VRM;
  input: VrmExpressionInput & { gesture: string; state: string; codeMode: boolean; closeUp?: boolean; walkMode?: boolean };
  jawEnergyRef?: number | React.MutableRefObject<number>;
  speakingRef?: React.MutableRefObject<boolean>;
  visemeEventsRef?: React.MutableRefObject<any[]>;
  audioStartTimeRef?: React.MutableRefObject<number>;
  speechBridgeRef?: React.MutableRefObject<any>;
}) {
  const speechBridgeContext = useContext(SpeechPlaybackContext);
  const speechBridge = speechBridgeRef ?? speechBridgeContext;
  const camera = useThree((state) => state.camera);
  const lookTarget = useMemo(() => new THREE.Object3D(), []);
  const camLookAtRef = useRef<THREE.Vector3>(new THREE.Vector3(0, 1.45, 0));
  const lastFovRef = useRef(0);
  const walkPhaseRef = useRef(0);
  const walkRoamXRef = useRef(0);
  const walkDirectionRef = useRef(1);
  const walkTurnYawRef = useRef(0);
  const lastFootstepSideRef = useRef<"left" | "right">("left");
  const avatarGroupRef = useRef<THREE.Group>(null);
  const shadowMeshRef = useRef<THREE.Mesh>(null);
  const shadowTexture = useMemo(() => {
    if (typeof document === "undefined") return null;
    try {
      const canvas = document.createElement("canvas");
      canvas.width = 128;
      canvas.height = 128;
      const ctx = canvas.getContext("2d");
      if (ctx) {
        const gradient = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
        gradient.addColorStop(0, "rgba(0, 0, 0, 0.55)");
        gradient.addColorStop(0.35, "rgba(0, 0, 0, 0.30)");
        gradient.addColorStop(0.7, "rgba(0, 0, 0, 0.08)");
        gradient.addColorStop(1, "rgba(0, 0, 0, 0)");
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, 128, 128);
      }
      const tex = new THREE.CanvasTexture(canvas);
      tex.needsUpdate = true;
      return tex;
    } catch {
      return null;
    }
  }, []);
  const metrics = useMemo(() => normalizeVrmAvatar(vrm), [vrm]);
  const performanceDirector = useMemo(() => new PerformanceDirector(), []);
  const availableExpressions = useMemo(() => {
    const set = new Set<string>();
    const mgr = vrm.expressionManager;
    if (mgr) {
      const candidates = [
        ...VRM_EXPRESSION_KEYS,
        "jawOpen", "a", "i", "u", "e", "o", "A", "I", "U", "E", "O",
        "mouthOpen", "mouthSmile", "mouthFunnel", "mouthPucker",
        "Joy", "Fun", "Angry", "Sorrow", "Surprised", "Blink", "Blink_L", "Blink_R"
      ];
      for (const name of candidates) {
        try {
          if (mgr.getExpression(name)) set.add(name);
        } catch {}
      }
    }
    return set;
  }, [vrm]);
  if (typeof window !== "undefined") {
    (window as any).__HINAA_DEBUG_VRM = { vrm, metrics, camera };
  }

  useEffect(() => {
    try {
      camera.layers.enableAll();
    } catch {}
  }, [camera]);

  const frameCountRef = useRef(0);
  const lastParamsRef = useRef({ closeUp: input.closeUp, codeMode: input.codeMode, vrm });

  useFrame((threeState, rawDelta) => {
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
    const speechSample = speechBridge?.current ? sampleSpeechPlayback(speechBridge) : null;
    const speechSpeaking = Boolean(speechSample?.speaking);
    const isSpeaking =
      speechSpeaking ||
      (speakingRef && "current" in speakingRef ? Boolean(speakingRef.current) : false) ||
      Boolean(input.speaking) ||
      input.state === "speaking" ||
      liveJaw > 0.025;

    if (!isSpeaking) {
      liveJaw = 0;
    }
    // NOTE: no synthetic flapping. Real lip sync comes from the audio
    // analyser (jawEnergyRef) and the viseme timeline. Fake syllable
    // oscillation made the mouth move during natural pauses between words,
    // which read as broken lip-sync. When jaw energy is low the mouth should
    // simply be more closed — that is what real speech looks like.

    let perfState: PerformanceState = "IDLE";
    if (isSpeaking) {
      perfState = "SPEAKING";
    } else if (input.state === "listening") {
      perfState = "LISTENING";
    } else if (input.state === "thinking") {
      perfState = "THINKING";
    } else if (input.state === "working") {
      perfState = "WORKING";
    } else if (input.state === "interrupted") {
      perfState = "INTERRUPTED";
    }
    performanceDirector.setState(perfState);
    performanceDirector.emotionRuntime.setEmotion(input.emotion, input.intensity);

    const isVrm1 = Boolean(vrm.meta?.metaVersion?.startsWith("1"));
    const perf = performanceDirector.update(delta, time, {
      gesture: input.gesture,
      codeMode: input.codeMode,
      timingSource: speechBridge?.current?.timing,
      fallbackVisemes: speechSample?.events,
      jawEnergy: liveJaw,
      isVrm1,
    });

    let activeVisemeName: string | undefined;
    let activeVisemeWeight: number | undefined;

    if (isSpeaking && speechSpeaking && speechSample) {
      const active = speechSample.viseme;
      if (active && active.mouth !== "closed") {
        activeVisemeName = active.mouth;
        activeVisemeWeight = active.weight;
      }
    } else if (isSpeaking && visemeEventsRef?.current && visemeEventsRef.current.length > 0) {
      const audioCtx = (window as any).__hinaaAudioCtx;
      const startTime = audioStartTimeRef?.current ?? (window as any).__hinaaAudioStartTime ?? 0;
      const playTimeMs = audioCtx && startTime > 0 ? Math.max(0, (audioCtx.currentTime - startTime) * 1000) : 0;
      if (playTimeMs > 0) {
        const active = getActiveViseme(playTimeMs, visemeEventsRef.current);
        if (active && active.mouth !== "closed") {
          activeVisemeName = active.mouth;
          activeVisemeWeight = active.weight;
        }
      }
    }

    // Last-resort fallback ONLY when the model produced no viseme timeline at
    // all (no spoken text, no provider visemes). When a timeline exists and
    // says "closed" — a natural pause between words — the mouth must stay
    // closed. The old unconditional fallback flapped lips during silence,
    // which read as broken lip-sync.
    const hasVisemeTimeline =
      (speechSpeaking && (speechSample?.events?.length ?? 0) > 0) ||
      (visemeEventsRef?.current?.length ?? 0) > 0 ||
      (speechSpeaking && Boolean(speechBridge?.current?.timing));
    if (isSpeaking && !hasVisemeTimeline && (!activeVisemeName || activeVisemeName === "closed")) {
      const visemes = ["aa", "oh", "aa", "ih", "ou", "ee"] as const;
      const idx = Math.floor((time * 7.5) % visemes.length);
      activeVisemeName = visemes[idx];
      activeVisemeWeight = Math.max(0.45, Math.min(0.9, liveJaw * 1.6));
    }

    const frameInput: VrmExpressionInput = {
      ...input,
      jawEnergy: liveJaw,
      speaking: isSpeaking,
      viseme: activeVisemeName,
      visemeWeight: activeVisemeWeight,
      blinkWeight: perf.blinkWeight,
    };

    // Expressions — face presets + jaw lip-sync + blink.
    const weights = buildVrmExpressionWeights(frameInput);
    
    // Lip-sync: prioritize sophisticated LipSyncRuntime blendshapes, with clean syllable fallback
    const hasLipSyncVowels =
      perf.lipSync.aa > 0 || perf.lipSync.ih > 0 || perf.lipSync.ou > 0 || perf.lipSync.ee > 0 || perf.lipSync.oh > 0;

    if (hasLipSyncVowels) {
      weights.aa = perf.lipSync.aa;
      weights.ih = perf.lipSync.ih;
      weights.ou = perf.lipSync.ou;
      weights.ee = perf.lipSync.ee;
      weights.oh = perf.lipSync.oh;
    } else if (isSpeaking && liveJaw > 0.025) {
      // Dynamic syllable-based vowel cycle synced to speech energy (avoiding all-vowel mesh distortion)
      const jawVowel = Math.min(0.85, liveJaw * 1.6);
      const vowelCycle = Math.floor((time * 8.5) % 5);
      weights.aa = vowelCycle === 0 ? jawVowel : 0;
      weights.oh = vowelCycle === 1 ? jawVowel * 0.85 : 0;
      weights.ih = vowelCycle === 2 ? jawVowel * 0.75 : 0;
      weights.ee = vowelCycle === 3 ? jawVowel * 0.7 : 0;
      weights.ou = vowelCycle === 4 ? jawVowel * 0.8 : 0;
    } else {
      weights.aa = 0;
      weights.ih = 0;
      weights.ou = 0;
      weights.ee = 0;
      weights.oh = 0;
    }

    const manager = vrm.expressionManager;
    if (manager) {
      try {
        // VRM 1.0 standard keys (and mapped VRM 0.0 equivalents inside @pixiv/three-vrm)
        for (const key of VRM_EXPRESSION_KEYS) {
          if (availableExpressions.has(key)) {
            manager.setValue(key, weights[key]);
          }
        }
        const effectiveJawOpen = Math.max(perf.lipSync.jawOpen, liveJaw > 0.025 ? Math.min(0.85, liveJaw * 1.5) : 0);
        if (availableExpressions.has("jawOpen")) manager.setValue("jawOpen", effectiveJawOpen);

        // Map to VRM 0.0 & ARKit presets without per-frame try/catch allocations
        if (availableExpressions.has("a")) manager.setValue("a" as any, weights.aa);
        if (availableExpressions.has("i")) manager.setValue("i" as any, weights.ih);
        if (availableExpressions.has("u")) manager.setValue("u" as any, weights.ou);
        if (availableExpressions.has("e")) manager.setValue("e" as any, weights.ee);
        if (availableExpressions.has("o")) manager.setValue("o" as any, weights.oh);
        if (availableExpressions.has("A")) manager.setValue("A" as any, weights.aa);
        if (availableExpressions.has("I")) manager.setValue("I" as any, weights.ih);
        if (availableExpressions.has("U")) manager.setValue("U" as any, weights.ou);
        if (availableExpressions.has("E")) manager.setValue("E" as any, weights.ee);
        if (availableExpressions.has("O")) manager.setValue("O" as any, weights.oh);
        if (availableExpressions.has("mouthOpen")) manager.setValue("mouthOpen" as any, effectiveJawOpen);
        if (availableExpressions.has("mouthSmile")) manager.setValue("mouthSmile" as any, weights.happy);
        if (availableExpressions.has("mouthFunnel")) manager.setValue("mouthFunnel" as any, (weights.oh + weights.ou) * 0.5);
        if (availableExpressions.has("mouthPucker")) manager.setValue("mouthPucker" as any, weights.ou * 0.8);
        if (availableExpressions.has("Joy")) manager.setValue("Joy" as any, weights.happy);
        if (availableExpressions.has("Fun")) manager.setValue("Fun" as any, weights.happy);
        if (availableExpressions.has("Angry")) manager.setValue("Angry" as any, weights.angry);
        if (availableExpressions.has("Sorrow")) manager.setValue("Sorrow" as any, weights.sad);
        if (availableExpressions.has("Surprised")) manager.setValue("Surprised" as any, weights.surprised);
        if (availableExpressions.has("Blink")) manager.setValue("Blink" as any, weights.blink);
        if (availableExpressions.has("Blink_L")) manager.setValue("Blink_L" as any, weights.blinkLeft);
        if (availableExpressions.has("Blink_R")) manager.setValue("Blink_R" as any, weights.blinkRight);
        manager.update();
      } catch {
        // Expression API drift — never let it break the frame.
      }
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
      const spine = humanoid.getNormalizedBoneNode(VRMHumanBoneName.Spine);
      const leftUpperLeg = humanoid.getNormalizedBoneNode(
        VRMHumanBoneName.LeftUpperLeg,
      );
      const rightUpperLeg = humanoid.getNormalizedBoneNode(
        VRMHumanBoneName.RightUpperLeg,
      );
      const leftLowerLeg = humanoid.getNormalizedBoneNode(
        VRMHumanBoneName.LeftLowerLeg,
      );
      const rightLowerLeg = humanoid.getNormalizedBoneNode(
        VRMHumanBoneName.RightLowerLeg,
      );
      const leftFoot = humanoid.getNormalizedBoneNode(
        VRMHumanBoneName.LeftFoot,
      );
      const rightFoot = humanoid.getNormalizedBoneNode(
        VRMHumanBoneName.RightFoot,
      );

      const headTarget = gestureHeadTarget(input.gesture, time, input.intensity);
      // Listening: shoulders settle — idle sway nearly stops, head gives a
      // soft attentive tilt toward you instead of random wander.
      const quiet = input.state === "listening";
      const isThinking = input.state === "thinking" || input.gesture === "thinking";
      const idleY = quiet
        ? Math.sin(time * 0.8) * 0.005
        : Math.sin(time * 0.5) * 0.02;
      const idleSway = quiet ? 0 : Math.sin(time * 0.9) * 0.015;
      // Micro-saccades: two incommensurate slow sines multiply into rare,
      // short-lived drifts — living stillness rather than a metronome.
      const saccade = quiet
        ? 0
        : Math.sin(time * 1.7) * Math.max(0, Math.sin(time * 0.23 + 1.1)) * 0.006;
      const microRoll = Math.sin(time * 0.37 + 2) * 0.0028;
      const settled = quiet
        ? { x: 0.08 + perf.head.x, y: perf.head.y, z: 0.06 + perf.head.z }
        : isThinking
          ? { x: -0.05 + perf.head.x, y: Math.sin(time * 1.2) * 0.06 + perf.head.y, z: -0.08 + perf.head.z }
          : { x: headTarget.x + perf.head.x, y: headTarget.y + perf.head.y, z: headTarget.z + perf.head.z };
      // Interactive Gaze & Head Tracking: follow cursor / touch pointer smoothly
      const pointer = threeState.pointer;
      const cursorHeadY = pointer ? THREE.MathUtils.clamp(pointer.x * 0.16, -0.14, 0.14) : 0;
      const cursorHeadX = pointer ? THREE.MathUtils.clamp(-pointer.y * 0.12, -0.10, 0.10) : 0;

      if (head) {
        head.rotation.x = THREE.MathUtils.damp(
          head.rotation.x,
          settled.x + cursorHeadX,
          5,
          delta,
        );
        head.rotation.y = THREE.MathUtils.damp(
          head.rotation.y,
          settled.y + idleY + saccade + cursorHeadY,
          5,
          delta,
        );
        head.rotation.z = THREE.MathUtils.damp(
          head.rotation.z,
          settled.z + microRoll,
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
      } else if ((input.state === "thinking" || input.gesture === "thinking") && rightArm) {
        // Anime thinking pose: right hand resting near chin/cheek, thoughtful contemplative posture
        rightArm.rotation.x = THREE.MathUtils.damp(rightArm.rotation.x, -0.68 + Math.sin(time * 1.2) * 0.04, 7, delta);
        rightArm.rotation.y = THREE.MathUtils.damp(rightArm.rotation.y, 0.45 * armZSign, 7, delta);
        rightArm.rotation.z = THREE.MathUtils.damp(rightArm.rotation.z, -0.62 * armZSign, 7, delta);
        if (rightLowerArm) {
          rightLowerArm.rotation.x = THREE.MathUtils.damp(rightLowerArm.rotation.x, 0.35, 7, delta);
          rightLowerArm.rotation.y = THREE.MathUtils.damp(rightLowerArm.rotation.y, -1.35 + Math.sin(time * 1.4) * 0.05, 7, delta);
          rightLowerArm.rotation.z = THREE.MathUtils.damp(rightLowerArm.rotation.z, -0.2 * armZSign, 7, delta);
        }
        if (rightHand) {
          rightHand.rotation.z = THREE.MathUtils.damp(rightHand.rotation.z, 0.35, 7, delta);
        }
        if (leftArm) {
          leftArm.rotation.x = THREE.MathUtils.damp(leftArm.rotation.x, 0.12, 6, delta);
          leftArm.rotation.z = THREE.MathUtils.damp(leftArm.rotation.z, 1.05 * armZSign, 6, delta);
        }
        if (leftLowerArm) {
          leftLowerArm.rotation.y = THREE.MathUtils.damp(leftLowerArm.rotation.y, 0.35 * -armZSign, 6, delta);
        }
      } else if (input.gesture === "reassure" && rightArm) {
        // Hand over heart pose: gentle comfort and emotional connection
        rightArm.rotation.x = THREE.MathUtils.damp(rightArm.rotation.x, -0.55, 7, delta);
        rightArm.rotation.y = THREE.MathUtils.damp(rightArm.rotation.y, 0.35 * armZSign, 7, delta);
        rightArm.rotation.z = THREE.MathUtils.damp(rightArm.rotation.z, -0.42 * armZSign, 7, delta);
        if (rightLowerArm) {
          rightLowerArm.rotation.y = THREE.MathUtils.damp(rightLowerArm.rotation.y, -1.15, 7, delta);
        }
        if (rightHand) {
          rightHand.rotation.z = THREE.MathUtils.damp(rightHand.rotation.z, 0.25, 7, delta);
        }
        if (leftArm) {
          leftArm.rotation.x = THREE.MathUtils.damp(leftArm.rotation.x, 0.08, 6, delta);
          leftArm.rotation.z = THREE.MathUtils.damp(leftArm.rotation.z, 1.2 * armZSign, 6, delta);
        }
      } else if (input.gesture === "explain") {
        if (rightArm) {
          rightArm.rotation.x = THREE.MathUtils.damp(
            rightArm.rotation.x,
            -0.5 + Math.sin(time * 2.4) * 0.15,
            8,
            delta,
          );
          rightArm.rotation.z = THREE.MathUtils.damp(rightArm.rotation.z, -0.45 * armZSign, 8, delta);
        }
        if (rightLowerArm) {
          rightLowerArm.rotation.y = THREE.MathUtils.damp(
            rightLowerArm.rotation.y,
            -0.65 + Math.sin(time * 2.6) * 0.12,
            8,
            delta,
          );
        }
        if (rightHand) {
          rightHand.rotation.z = THREE.MathUtils.damp(
            rightHand.rotation.z,
            Math.sin(time * 2.4) * 0.15,
            8,
            delta,
          );
        }
        if (leftArm) {
          leftArm.rotation.x = THREE.MathUtils.damp(
            leftArm.rotation.x,
            -0.35 + Math.cos(time * 2.0) * 0.12,
            8,
            delta,
          );
          leftArm.rotation.z = THREE.MathUtils.damp(leftArm.rotation.z, 0.5 * armZSign, 8, delta);
        }
        if (leftLowerArm) {
          leftLowerArm.rotation.y = THREE.MathUtils.damp(
            leftLowerArm.rotation.y,
            0.55 * -armZSign + Math.cos(time * 2.2) * 0.1,
            8,
            delta,
          );
        }
      } else if (input.gesture === "point" && rightArm) {
        // Pointing gesture: right arm smoothly extended toward screen/viewer
        rightArm.rotation.x = THREE.MathUtils.damp(rightArm.rotation.x, -0.85, 8, delta);
        rightArm.rotation.y = THREE.MathUtils.damp(rightArm.rotation.y, -0.15 * armZSign, 8, delta);
        rightArm.rotation.z = THREE.MathUtils.damp(rightArm.rotation.z, -0.25 * armZSign, 8, delta);
        if (rightLowerArm) {
          rightLowerArm.rotation.y = THREE.MathUtils.damp(rightLowerArm.rotation.y, -0.2, 8, delta);
        }
        if (rightHand) {
          rightHand.rotation.z = THREE.MathUtils.damp(rightHand.rotation.z, 0.1, 8, delta);
        }
        if (leftArm) {
          leftArm.rotation.x = THREE.MathUtils.damp(leftArm.rotation.x, 0.05, 6, delta);
          leftArm.rotation.z = THREE.MathUtils.damp(leftArm.rotation.z, 1.15 * armZSign, 6, delta);
        }
      } else if (input.gesture === "shy" && rightArm) {
        // Anime shy / bashful pose: hand near cheek, soft posture
        rightArm.rotation.x = THREE.MathUtils.damp(rightArm.rotation.x, -0.45, 7, delta);
        rightArm.rotation.y = THREE.MathUtils.damp(rightArm.rotation.y, 0.45 * armZSign, 7, delta);
        rightArm.rotation.z = THREE.MathUtils.damp(rightArm.rotation.z, -0.45 * armZSign, 7, delta);
        if (rightLowerArm) {
          rightLowerArm.rotation.y = THREE.MathUtils.damp(rightLowerArm.rotation.y, -1.2, 7, delta);
        }
        if (leftArm) {
          leftArm.rotation.x = THREE.MathUtils.damp(leftArm.rotation.x, 0.1, 6, delta);
          leftArm.rotation.z = THREE.MathUtils.damp(leftArm.rotation.z, 1.1 * armZSign, 6, delta);
        }
      } else if (input.gesture === "agree" && rightArm) {
        // Affirmative acknowledgement gesture
        rightArm.rotation.x = THREE.MathUtils.damp(rightArm.rotation.x, -0.4, 8, delta);
        rightArm.rotation.y = THREE.MathUtils.damp(rightArm.rotation.y, 0.2 * armZSign, 8, delta);
        rightArm.rotation.z = THREE.MathUtils.damp(rightArm.rotation.z, -0.4 * armZSign, 8, delta);
        if (rightLowerArm) {
          rightLowerArm.rotation.y = THREE.MathUtils.damp(rightLowerArm.rotation.y, -0.65, 8, delta);
        }
        if (leftArm) {
          leftArm.rotation.x = THREE.MathUtils.damp(leftArm.rotation.x, 0.08, 6, delta);
          leftArm.rotation.z = THREE.MathUtils.damp(leftArm.rotation.z, 1.2 * armZSign, 6, delta);
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
      // Breathing — subtle chest/hips rise whose depth and pace drift on slow
      // incommensurate cycles, so the rest state breathes like a person rather
      // than a loop. Quieter while listening; clamped to prevent Y-drift.
      const drift = 0.78 + 0.22 * Math.sin(time * 0.11) + 0.08 * Math.sin(time * 0.047 + 2.1);
      const rate = 1.4 + Math.sin(time * 0.07) * 0.13;
      const inhale = Math.sin(time * rate);
      const breath = inhale * (quiet ? 0.0018 : 0.0042) * drift;
      if (chest) {
        chest.rotation.x = Math.max(0, inhale) * (quiet ? 0.0012 : 0.0032) * drift;
      }
      const isWalking = Boolean(input.walkMode || input.gesture === "walk" || input.state === "walking");

      if (isWalking) {
        // Natural human walking cadence ~3.6 rad/s
        const walkSpeed = 3.6;
        walkPhaseRef.current = (walkPhaseRef.current + delta * walkSpeed) % (Math.PI * 2);
        const phase = walkPhaseRef.current;

        // Roam laterally across floor / runway
        const roamStep = 0.12 * walkDirectionRef.current * delta;
        walkRoamXRef.current += roamStep;
        const maxRoam = 0.28;
        if (walkRoamXRef.current > maxRoam) {
          walkRoamXRef.current = maxRoam;
          walkDirectionRef.current = -1;
        } else if (walkRoamXRef.current < -maxRoam) {
          walkRoamXRef.current = -maxRoam;
          walkDirectionRef.current = 1;
        }
        const targetYaw = walkDirectionRef.current > 0 ? 0.22 : -0.22;
        walkTurnYawRef.current = THREE.MathUtils.damp(walkTurnYawRef.current, targetYaw, 5, delta);

        // Pelvis / Hips dynamics
        const hipBob = Math.abs(Math.sin(phase)) * 0.024;
        const hipRoll = Math.sin(phase) * 0.045; // lateral weight shift
        const hipYaw = Math.sin(phase) * 0.06; // pelvis twists forward with stride
        if (hips) {
          hips.position.y = THREE.MathUtils.damp(hips.position.y, -hipBob, 12, delta);
          hips.rotation.z = THREE.MathUtils.damp(hips.rotation.z, hipRoll, 10, delta);
          hips.rotation.y = THREE.MathUtils.damp(hips.rotation.y, hipYaw, 10, delta);
          hips.rotation.x = THREE.MathUtils.damp(hips.rotation.x, 0.035, 8, delta);
        }

        if (spine) {
          spine.rotation.z = THREE.MathUtils.damp(spine.rotation.z, -hipRoll * 0.5, 10, delta);
          spine.rotation.y = THREE.MathUtils.damp(spine.rotation.y, -hipYaw * 0.5, 10, delta);
          spine.rotation.x = THREE.MathUtils.damp(spine.rotation.x, 0.015, 8, delta);
        }

        // Upper legs (Stride)
        const legSwing = Math.sin(phase) * 0.44;
        if (leftUpperLeg) {
          leftUpperLeg.rotation.x = THREE.MathUtils.damp(leftUpperLeg.rotation.x, legSwing, 16, delta);
          leftUpperLeg.rotation.z = THREE.MathUtils.damp(leftUpperLeg.rotation.z, -0.035, 10, delta);
        }
        if (rightUpperLeg) {
          rightUpperLeg.rotation.x = THREE.MathUtils.damp(rightUpperLeg.rotation.x, -legSwing, 16, delta);
          rightUpperLeg.rotation.z = THREE.MathUtils.damp(rightUpperLeg.rotation.z, 0.035, 10, delta);
        }

        // Lower legs (Knee flexion on recovery/swing phase only)
        const leftKnee = Math.max(0, -Math.sin(phase)) * 0.82;
        const rightKnee = Math.max(0, Math.sin(phase)) * 0.82;
        if (leftLowerLeg) {
          leftLowerLeg.rotation.x = THREE.MathUtils.damp(leftLowerLeg.rotation.x, leftKnee, 16, delta);
        }
        if (rightLowerLeg) {
          rightLowerLeg.rotation.x = THREE.MathUtils.damp(rightLowerLeg.rotation.x, rightKnee, 16, delta);
        }

        // Feet articulation
        if (leftFoot) {
          leftFoot.rotation.x = THREE.MathUtils.damp(leftFoot.rotation.x, -legSwing * 0.32, 12, delta);
        }
        if (rightFoot) {
          rightFoot.rotation.x = THREE.MathUtils.damp(rightFoot.rotation.x, legSwing * 0.32, 12, delta);
        }

        // Synchronized footstep audio on step contact
        const stepSin = Math.sin(phase);
        if (stepSin > 0.38 && lastFootstepSideRef.current !== "left") {
          lastFootstepSideRef.current = "left";
          playFootstepSound();
        } else if (stepSin < -0.38 && lastFootstepSideRef.current !== "right") {
          lastFootstepSideRef.current = "right";
          playFootstepSound();
        }

        // Arms natural counter-swing when not executing an expressive gesture
        if (input.gesture === "none" || !input.gesture || input.gesture === "walk") {
          const armSwing = Math.sin(phase) * 0.35;
          if (leftArm) {
            leftArm.rotation.x = THREE.MathUtils.damp(leftArm.rotation.x, -armSwing, 12, delta);
            leftArm.rotation.z = THREE.MathUtils.damp(leftArm.rotation.z, 1.15 * armZSign, 8, delta);
          }
          if (rightArm) {
            rightArm.rotation.x = THREE.MathUtils.damp(rightArm.rotation.x, armSwing, 12, delta);
            rightArm.rotation.z = THREE.MathUtils.damp(rightArm.rotation.z, -1.15 * armZSign, 8, delta);
          }
          if (leftLowerArm) {
            leftLowerArm.rotation.x = THREE.MathUtils.damp(leftLowerArm.rotation.x, 0.15 + Math.max(0, -armSwing) * 0.25, 10, delta);
          }
          if (rightLowerArm) {
            rightLowerArm.rotation.x = THREE.MathUtils.damp(rightLowerArm.rotation.x, 0.15 + Math.max(0, armSwing) * 0.25, 10, delta);
          }
        }
      } else {
        walkRoamXRef.current = THREE.MathUtils.damp(walkRoamXRef.current, 0, 4, delta);
        walkTurnYawRef.current = THREE.MathUtils.damp(walkTurnYawRef.current, 0, 4, delta);

        // Stable standing posture: legs firmly grounded, poised balance, organic breathing
        if (hips) {
          hips.position.y = THREE.MathUtils.damp(hips.position.y, 0, 6, delta);
          hips.rotation.z = THREE.MathUtils.damp(hips.rotation.z, 0, 6, delta);
          hips.rotation.y = THREE.MathUtils.damp(hips.rotation.y, 0, 6, delta);
          hips.rotation.x = THREE.MathUtils.damp(hips.rotation.x, 0.005, 6, delta);
        }

        if (spine) {
          spine.rotation.z = THREE.MathUtils.damp(spine.rotation.z, 0, 6, delta);
          if (hips) {
            spine.rotation.y = THREE.MathUtils.damp(spine.rotation.y, 0, 6, delta);
          }
          spine.rotation.x = THREE.MathUtils.damp(spine.rotation.x, Math.max(0, -inhale) * 0.002, 6, delta);
        }

        // Stable grounded legs: zero wobbling or unnatural knee bending
        if (leftLowerLeg) {
          leftLowerLeg.rotation.x = THREE.MathUtils.damp(leftLowerLeg.rotation.x, 0, 6, delta);
        }
        if (rightLowerLeg) {
          rightLowerLeg.rotation.x = THREE.MathUtils.damp(rightLowerLeg.rotation.x, 0, 6, delta);
        }
        if (leftUpperLeg) {
          leftUpperLeg.rotation.x = THREE.MathUtils.damp(leftUpperLeg.rotation.x, 0, 6, delta);
          leftUpperLeg.rotation.z = THREE.MathUtils.damp(leftUpperLeg.rotation.z, 0, 6, delta);
        }
        if (rightUpperLeg) {
          rightUpperLeg.rotation.x = THREE.MathUtils.damp(rightUpperLeg.rotation.x, 0, 6, delta);
          rightUpperLeg.rotation.z = THREE.MathUtils.damp(rightUpperLeg.rotation.z, 0, 6, delta);
        }
        if (leftFoot) {
          leftFoot.rotation.x = THREE.MathUtils.damp(leftFoot.rotation.x, 0, 6, delta);
        }
        if (rightFoot) {
          rightFoot.rotation.x = THREE.MathUtils.damp(rightFoot.rotation.x, 0, 6, delta);
        }
      }
    }

    vrm.update(delta);

    if (avatarGroupRef.current) {
      avatarGroupRef.current.position.x = baseX + walkRoamXRef.current;
      avatarGroupRef.current.rotation.y = walkTurnYawRef.current;
    }

    // Dynamic Landmark Camera & Gaze: Frame camera directly to the character's true face position
    // AFTER vrm.update has fully resolved humanoid bone solvers, inverse kinematics, and matrix transforms.
    if (humanoid) {
      const head = humanoid.getRawBoneNode(VRMHumanBoneName.Head) || humanoid.getNormalizedBoneNode(VRMHumanBoneName.Head);
      const leftEye = humanoid.getRawBoneNode(VRMHumanBoneName.LeftEye) || humanoid.getNormalizedBoneNode(VRMHumanBoneName.LeftEye) || head;
      const rightEye = humanoid.getRawBoneNode(VRMHumanBoneName.RightEye) || humanoid.getNormalizedBoneNode(VRMHumanBoneName.RightEye) || head;

      if (head) {
        head.updateWorldMatrix(true, false);
        head.getWorldPosition(_scratchHeadPos);

        if (leftEye && rightEye) {
          leftEye.updateWorldMatrix(true, false);
          rightEye.updateWorldMatrix(true, false);
          leftEye.getWorldPosition(_scratchLPos);
          rightEye.getWorldPosition(_scratchRPos);
          _scratchEyePos.addVectors(_scratchLPos, _scratchRPos).multiplyScalar(0.5);
        } else {
          _scratchEyePos.copy(_scratchHeadPos);
        }

        const faceCenterX = (_scratchHeadPos.x + _scratchEyePos.x) / 2;
        const faceCenterY = (_scratchHeadPos.y + _scratchEyePos.y) / 2;
        const faceCenterZ = (_scratchHeadPos.z + _scratchEyePos.z) / 2;

        // Gaze — emotion-aware look target at true eye level with gentle drift + cursor tracking
        if (vrm.lookAt) {
          const isThinking = input.state === "thinking";
          const pointer = threeState.pointer;
          const cursorEyeX = pointer ? THREE.MathUtils.clamp(pointer.x * 0.45, -0.4, 0.4) : 0;
          const cursorEyeY = pointer ? THREE.MathUtils.clamp(pointer.y * 0.35, -0.3, 0.3) : 0;

          const gazeTargetX = faceCenterX + perf.gaze.x + cursorEyeX + (isThinking ? 0.10 : 0);
          const gazeTargetY = faceCenterY + perf.gaze.y + cursorEyeY + (isThinking ? 0.14 : 0);
          const gazeTargetZ = faceCenterZ + 1.2 + (isThinking ? -0.2 : 0);
          lookTarget.position.set(gazeTargetX, gazeTargetY, gazeTargetZ);
          lookTarget.updateMatrixWorld();
          vrm.lookAt.target = lookTarget;
        }

        const isCloseUp = input.walkMode ? false : (input.closeUp ?? true);
        const camDistance = isCloseUp ? 0.98 : (input.walkMode ? 3.35 : 1.50);
        const targetCamX = faceCenterX + (input.codeMode ? -0.28 : 0);
        const targetCamY = input.walkMode ? (faceCenterY - 0.70) : (faceCenterY - 0.01);
        const targetCamZ = faceCenterZ + camDistance;

        const dampSpeed = frameCountRef.current < 3 ? 30 : 6;
        frameCountRef.current += 1;

        camera.position.x = THREE.MathUtils.damp(camera.position.x, targetCamX, dampSpeed, delta);
        camera.position.y = THREE.MathUtils.damp(camera.position.y, targetCamY, dampSpeed, delta);
        camera.position.z = THREE.MathUtils.damp(camera.position.z, targetCamZ, dampSpeed, delta);

        const targetLookY = input.walkMode ? (faceCenterY - 0.75) : (faceCenterY - 0.02);
        camLookAtRef.current.x = THREE.MathUtils.damp(camLookAtRef.current.x, faceCenterX, dampSpeed, delta);
        camLookAtRef.current.y = THREE.MathUtils.damp(camLookAtRef.current.y, targetLookY, dampSpeed, delta);
        camLookAtRef.current.z = THREE.MathUtils.damp(camLookAtRef.current.z, faceCenterZ, dampSpeed, delta);

        camera.lookAt(camLookAtRef.current);
        const expectedFov = (input.walkMode && !input.closeUp) ? 42 : ((input.closeUp ?? true) ? 32 : 38);
        if (Math.abs(lastFovRef.current - expectedFov) > 0.1) {
          lastFovRef.current = expectedFov;
          (camera as THREE.PerspectiveCamera).fov = expectedFov;
          camera.updateProjectionMatrix();
        }

        if (shadowMeshRef.current) {
          const lFoot = humanoid.getRawBoneNode(VRMHumanBoneName.LeftFoot) || humanoid.getNormalizedBoneNode(VRMHumanBoneName.LeftFoot);
          const rFoot = humanoid.getRawBoneNode(VRMHumanBoneName.RightFoot) || humanoid.getNormalizedBoneNode(VRMHumanBoneName.RightFoot);
          let groundY = 0;
          if (lFoot && rFoot) {
            lFoot.getWorldPosition(_scratchLPos);
            rFoot.getWorldPosition(_scratchRPos);
            groundY = Math.min(_scratchLPos.y, _scratchRPos.y);
          } else {
            groundY = faceCenterY - 1.45;
          }
          const shadowX = avatarGroupRef.current ? avatarGroupRef.current.position.x : baseX + walkRoamXRef.current;
          const shadowZ = avatarGroupRef.current ? avatarGroupRef.current.position.z : baseZ;
          shadowMeshRef.current.position.set(shadowX, groundY + 0.003, shadowZ);
          const isWalking = Boolean(input.walkMode || input.gesture === "walk" || input.state === "walking");
          const strideBob = isWalking ? 1.0 + Math.abs(Math.sin(walkPhaseRef.current)) * 0.12 : 1.0;
          shadowMeshRef.current.scale.set(strideBob, strideBob, 1);
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
    <>
      <primitive object={lookTarget} />
      {shadowTexture && (
        <mesh
          ref={shadowMeshRef}
          rotation={[-Math.PI / 2, 0, 0]}
          position={[baseX, 0.003, baseZ]}
          renderOrder={-1}
        >
          <planeGeometry args={[0.72, 0.44]} />
          <meshBasicMaterial
            map={shadowTexture}
            transparent
            opacity={input.walkMode ? 0.75 : 0.6}
            depthWrite={false}
          />
        </mesh>
      )}
      <group
        ref={avatarGroupRef}
        position={[baseX, baseY, baseZ]}
        scale={finalScale}
      >
        <primitive object={vrm.scene} />
      </group>
    </>
  );
}

function VrmModel({
  url,
  input,
  jawEnergyRef,
  speakingRef,
  visemeEventsRef,
  audioStartTimeRef,
  speechBridgeRef,
  onReady,
  onError,
}: {
  url: string;
  input: VrmExpressionInput & { gesture: string; state: string; codeMode: boolean; closeUp?: boolean; walkMode?: boolean };
  jawEnergyRef?: number | React.MutableRefObject<number>;
  speakingRef?: React.MutableRefObject<boolean>;
  visemeEventsRef?: React.MutableRefObject<any[]>;
  audioStartTimeRef?: React.MutableRefObject<number>;
  speechBridgeRef?: React.MutableRefObject<any>;
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
      speechBridgeRef={speechBridgeRef}
    />
  );
}

export const VRMAvatar = memo(function VRMAvatar(props: VRMAvatarProps) {
  const [modelUrl, setModelUrl] = useState<string | null | undefined>(undefined);
  const [failed, setFailed] = useState(false);
  const [glContextLost, setGlContextLost] = useState(false);
  const [modelLoading, setModelLoading] = useState(true);
  const previousReadyModel = useRef<string | null>(null);
  const [modelNotice, setModelNotice] = useState("");
  const [webglAvailable] = useState<boolean>(() => isWebGLAvailable());
  const handleModelReady = useCallback(() => {
    previousReadyModel.current = modelUrl ?? null;
    setModelLoading(false);
  }, [modelUrl]);
  const handleModelError = useCallback(() => {
    setModelLoading(false);
    if (previousReadyModel.current && previousReadyModel.current !== modelUrl) {
      setModelNotice("Model could not load. Showing the previous avatar; choose another model to retry.");
      setModelUrl(previousReadyModel.current);
    } else {
      setFailed(true);
    }
  }, [modelUrl]);
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
      setModelNotice("");
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

  const emotion = props.plan?.emotion.primary ?? "neutral";
  const gesture = props.plan?.performance.gesture ?? "none";

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
    walkMode?: boolean;
  } = useMemo(() => ({
    emotion,
    facePreset: props.plan?.performance.facePreset,
    intensity: props.plan?.emotion.intensity ?? 0.5,
    jawEnergy: resolvedJawEnergy,
    blinkWeight: 0,
    speaking: props.state === "speaking",
    reducedMotion: props.reducedMotion || Boolean(props.lowPerformance),
    gesture,
    state: props.state,
    codeMode: Boolean(props.codeMode),
    closeUp: Boolean(props.closeUp ?? true),
    walkMode: Boolean(props.walkMode),
  }), [
    emotion,
    props.plan?.performance.facePreset,
    props.plan?.emotion.intensity,
    resolvedJawEnergy,
    props.state,
    props.reducedMotion,
    props.lowPerformance,
    gesture,
    props.codeMode,
    props.closeUp,
    props.walkMode,
  ]);

  return (
    <div
      className="vrm-stage"
      data-engine="vrm-avatar-v1"
      data-state={props.state}
      data-emotion={emotion}
      data-gesture={gesture}
      aria-label="HINAA companion avatar"
    >
      {modelNotice && <small role="status">{modelNotice}</small>}
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
            dpr={glContextLost || props.lowPerformance ? 1 : [1, Math.min(typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1, 1.35)]}
            gl={{
              antialias: !glContextLost,
              alpha: true,
              powerPreference: glContextLost ? "low-power" : "high-performance",
              stencil: false,
              depth: true,
            }}
            camera={{
              position: [0, 1.45, 0.88],
              fov: (props.walkMode && !props.closeUp) ? 42 : ((props.closeUp ?? true) ? 32 : 38),
            }}
          >
            <ambientLight intensity={0.75} />
            <directionalLight position={[1.5, 2.5, 2]} intensity={1.1} />
            <directionalLight position={[-2, 1, -1]} intensity={0.25} />
            <ContextLossGuard onLost={handleContextLost} />
            <ModelErrorBoundary key={modelUrl} onError={handleModelError}>
              <VrmModel
                url={modelUrl}
                input={input}
                jawEnergyRef={props.jawEnergy}
                speakingRef={props.speakingRef}
                visemeEventsRef={props.visemeEvents}
                audioStartTimeRef={props.audioStartTimeRef}
                speechBridgeRef={props.speechBridge}
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
});

