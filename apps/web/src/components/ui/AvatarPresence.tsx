import {runtimeMeasurements} from "../../features/telemetry/runtimeMeasurements";
import { sampleConversationMotion } from "../../features/avatar/conversationalMotion";
/**
 * AvatarPresence — HINAA 3D Avatar Director
 * 
 * Architecture:
 *   Layer 1: Viseme lip-sync → driven by AudioContext playback clock + text-to-viseme events
 *   Layer 2: Jaw energy amplitude → scales viseme weight using audio RMS
 *   Layer 3: Blink → natural randomized or VSeeFace tracked
 *   Layer 4: Emotion blend → state-driven at low intensity (never overrides mouth)
 *   Layer 5: Gaze → subtle eye movement
 *   Layer 6: Pose → relaxed idle via normalized rig bones
 */

import { Suspense, useState, useRef, useEffect, useCallback, useContext, useMemo } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { ContactShadows } from "@react-three/drei";
import { AnimatePresence, motion } from "framer-motion";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { VRMLoaderPlugin, VRM, VRMExpressionPresetName, VRMHumanBoneName, VRMUtils } from "@pixiv/three-vrm";
import * as THREE from "three";
import { Expand, Maximize2, Minimize2, Radio, Footprints } from "lucide-react";
import { FullscreenCompanionOverlay, type FullscreenLiveStatus } from "./FullscreenCompanionOverlay";
import type { CompanionState, TranscriptMessage } from "../../features/companion/types";
import { defaultAvatarPresentation, type AvatarPresentation } from "../../features/avatar/avatarPresentation";
import type { FaceExpressions } from "../../features/audio/useVSeeFace";
import {
  expressionIntentFor,
  parseExpressionSegments,
  getTemporalIntent,
  computeAffectiveProfile,
  computeDirectMorphTargets,
  type CompanionExpressionIntent,
  type AffectiveProfile,
} from "../../features/avatar/companionExpression";
import { getActiveViseme, type VisemeEvent } from "../../features/audio/textToViseme";
import { SpeechPlaybackContext, sampleSpeechPlayback } from "../../features/audio/speechPlaybackBridge";
import { optimizeVrm } from "../../features/avatar/vrmOptimizer";
import { playFootstepSound } from "../../lib/uiSound";
import type { AssistantTurnPlan } from "../../contracts/assistantTurnPlan";


export type PresenceMode = "portrait" | "closeup" | "upperbody" | "full" | "hidden";

/* ─── Camera presets ─────────────────────────────────────── */
const CAMERAS: Record<PresenceMode, { pos: [number,number,number]; target: [number,number,number]; fov: number }> = {
  closeup:  { pos: [0, 1.34, 0.72], target: [0, 1.30, 0], fov: 26 },
  portrait: { pos: [0, 1.30, 1.58], target: [0, 1.14, 0], fov: 38 },
  upperbody:{ pos: [0, 1.10, 1.88], target: [0, 1.02, 0], fov: 40 },
  full:     { pos: [0, 0.86, 2.45], target: [0, 0.72, 0], fov: 46 },
  hidden:   { pos: [0, 1.0,  3.0],  target: [0, 1.0,  0], fov: 35 },
};

type CameraPreset = { pos: [number, number, number]; target: [number, number, number]; fov: number };

type AnatomyFrame = {
  centerX: number;
  headY: number;
  neckY: number;
  chestY: number;
  hipsY: number;
  minY: number;
  maxY: number;
  revision: string;
};

function cameraFromAnatomy(mode: PresenceMode, fallback: CameraPreset, frame?: AnatomyFrame, compactViewport = false): CameraPreset {
  if (!frame || mode === "hidden") return fallback;
  const torso = Math.max(0.28, frame.headY - frame.chestY);
  const bodyHeight = Math.max(1.1, frame.maxY - frame.minY);
  const x = frame.centerX;
  // On a compact portrait screen the companion view intentionally frames the
  // face and shoulders more closely. Desktop retains the wider conversational
  // composition, while explicit close-up/full camera choices remain untouched.
  const portraitFov = compactViewport ? 25 : 31;
  // Head/chest control composition. Bounds are used only to avoid clipping hair
  // and accessories, never to pull the portrait target down toward a long skirt.
  const portraitTop = Math.max(frame.maxY, frame.headY + torso * (compactViewport ? 0.34 : 0.44));
  const portraitBottom = frame.chestY - torso * (compactViewport ? 0.16 : 0.38);
  const distanceFor = (top: number, bottom: number, fov: number) => {
    const half = Math.max(0.22, (top - bottom) / 2) * 1.12;
    return Math.max(0.58, half / Math.tan(THREE.MathUtils.degToRad(fov / 2)));
  };
  if (mode === "closeup") {
    const top = Math.max(frame.maxY, frame.headY + torso * 0.36);
    const bottom = frame.neckY - torso * 0.20;
    const targetY = (top + bottom) / 2;
    return { pos: [x, targetY, distanceFor(top, bottom, 24)], target: [x, targetY, 0], fov: 24 };
  }
  if (mode === "full") {
    const targetY = (frame.minY + frame.maxY) / 2;
    const fov = 43;
    const distance = Math.max(2.15, (bodyHeight / 2) / Math.tan(THREE.MathUtils.degToRad(fov / 2)) * 1.12);
    return { pos: [x, targetY, distance], target: [x, targetY, 0], fov };
  }
  if (mode === "upperbody") {
    const top = portraitTop;
    const bottom = Math.min(frame.chestY - torso * 1.05, frame.hipsY + torso * 0.28);
    const targetY = (top + bottom) / 2;
    return { pos: [x, targetY, distanceFor(top, bottom, 38)], target: [x, targetY, 0], fov: 38 };
  }
  const targetY = (portraitTop + portraitBottom) / 2;
  return { pos: [x, targetY, distanceFor(portraitTop, portraitBottom, portraitFov)], target: [x, targetY, 0], fov: portraitFov };
}

// The models have materially different authored proportions. These editorial
// portrait presets keep the focus on face, shoulders, and upper torso while
// preserving the VRM's authored neutral arm pose instead of forcing unsafe
// per-bone rotations just to hide a T-pose-like silhouette.
const MODEL_CAMERA_PRESETS: Record<string, Partial<Record<PresenceMode, CameraPreset>>> = {
  "/models/model_6164.vrm": {
    portrait: { pos: [0, 1.43, 1.28], target: [0, 1.31, 0], fov: 34 },
    upperbody: { pos: [0, 1.20, 1.78], target: [0, 1.10, 0], fov: 39 },
    closeup: { pos: [0, 1.47, 0.77], target: [0, 1.39, 0], fov: 25 },
  },
  "/models/model_5447.vrm": {
    portrait: { pos: [0, 1.54, 1.20], target: [0, 1.41, 0], fov: 31 },
    upperbody: { pos: [0, 1.28, 1.74], target: [0, 1.18, 0], fov: 38 },
    closeup: { pos: [0, 1.58, 0.78], target: [0, 1.49, 0], fov: 25 },
  },
};

/* ─── Mouth expression targets per viseme ───────────────── */
type MouthKey = "aa" | "ih" | "ou" | "ee" | "oh";
const VISEME_TO_VRM: Record<string, MouthKey> = {
  aa: "aa", ih: "ih", ou: "ou", ee: "ee", oh: "oh", closed: "aa",
};
const ALL_MOUTH_KEYS: MouthKey[] = ["aa", "ih", "ou", "ee", "oh"];
const VRM_PRESET: Record<MouthKey, VRMExpressionPresetName> = {
  aa: VRMExpressionPresetName.Aa,
  ih: VRMExpressionPresetName.Ih,
  ou: VRMExpressionPresetName.Ou,
  ee: VRMExpressionPresetName.Ee,
  oh: VRMExpressionPresetName.Oh,
};

// Older rigs spelled the same blend shapes with VRM 0.x authoring names. A
// write only reaches the mesh through whichever spelling the file registered,
// so the setter tries both. Module scope: the frame loop asks on every write.
const PRESET_ALIASES: Record<string, string> = {
  aa: "a", ih: "i", ou: "u", ee: "e", oh: "o",
  happy: "joy", sad: "sorrow", relaxed: "fun",
  blinkLeft: "blink_l", blinkRight: "blink_r",
  surprised: "Surprised", neutral: "Neutral",
};

/* ─── Emotion blends (high-level anime facial acting targets) ─── */
type EmotionBlend = Partial<Record<VRMExpressionPresetName, number>>;
function emotionForIntent(intent: CompanionExpressionIntent): EmotionBlend {
  switch (intent) {
    case "celebratory":
      return { [VRMExpressionPresetName.Happy]: 0.85, [VRMExpressionPresetName.Surprised]: 0.28, [VRMExpressionPresetName.Relaxed]: 0.18 };
    case "joyful":
      return { [VRMExpressionPresetName.Happy]: 0.82, [VRMExpressionPresetName.Relaxed]: 0.22 };
    case "laughing":
      return { [VRMExpressionPresetName.Happy]: 0.95, [VRMExpressionPresetName.Relaxed]: 0.25 };
    case "playful":
      return { [VRMExpressionPresetName.Happy]: 0.70, [VRMExpressionPresetName.Relaxed]: 0.25, [VRMExpressionPresetName.Surprised]: 0.15 };
    case "flirty_warm":
      return { [VRMExpressionPresetName.Happy]: 0.65, [VRMExpressionPresetName.Relaxed]: 0.40 };
    case "curious":
      return { [VRMExpressionPresetName.Relaxed]: 0.35, [VRMExpressionPresetName.Happy]: 0.28, [VRMExpressionPresetName.Surprised]: 0.04 };
    case "thinking":
      return { [VRMExpressionPresetName.Neutral]: 0.45, [VRMExpressionPresetName.Relaxed]: 0.25, [VRMExpressionPresetName.Surprised]: 0.08 };
    case "surprised":
      return { [VRMExpressionPresetName.Surprised]: 0.88, [VRMExpressionPresetName.Happy]: 0.24 };
    case "empathetic":
      return { [VRMExpressionPresetName.Relaxed]: 0.42, [VRMExpressionPresetName.Sad]: 0.28, [VRMExpressionPresetName.Happy]: 0.15 };
    case "concerned":
      return { [VRMExpressionPresetName.Sad]: 0.48, [VRMExpressionPresetName.Relaxed]: 0.18, [VRMExpressionPresetName.Angry]: 0.15 };
    case "pouting":
      return { [VRMExpressionPresetName.Sad]: 0.35, [VRMExpressionPresetName.Angry]: 0.32, [VRMExpressionPresetName.Relaxed]: 0.10 };
    case "confident":
      return { [VRMExpressionPresetName.Happy]: 0.68, [VRMExpressionPresetName.Relaxed]: 0.32 };
    case "warm":
      return { [VRMExpressionPresetName.Happy]: 0.52, [VRMExpressionPresetName.Relaxed]: 0.28 };
    case "excited":
      return { [VRMExpressionPresetName.Happy]: 0.88, [VRMExpressionPresetName.Surprised]: 0.22, [VRMExpressionPresetName.Relaxed]: 0.12 };
    case "shy":
      return { [VRMExpressionPresetName.Happy]: 0.34, [VRMExpressionPresetName.Relaxed]: 0.38, [VRMExpressionPresetName.Sad]: 0.08 };
    case "sad":
      return { [VRMExpressionPresetName.Sad]: 0.72, [VRMExpressionPresetName.Relaxed]: 0.14 };
    case "grateful":
      return { [VRMExpressionPresetName.Happy]: 0.62, [VRMExpressionPresetName.Relaxed]: 0.34 };
    case "determined":
      return { [VRMExpressionPresetName.Happy]: 0.30, [VRMExpressionPresetName.Neutral]: 0.35, [VRMExpressionPresetName.Angry]: 0.10 };
    case "smug":
      return { [VRMExpressionPresetName.Happy]: 0.55, [VRMExpressionPresetName.Relaxed]: 0.30 };
    case "nervous":
      return { [VRMExpressionPresetName.Relaxed]: 0.20, [VRMExpressionPresetName.Sad]: 0.18, [VRMExpressionPresetName.Surprised]: 0.14 };
    case "sleepy":
      return { [VRMExpressionPresetName.Relaxed]: 0.55, [VRMExpressionPresetName.Neutral]: 0.15 };
    case "awe":
      return { [VRMExpressionPresetName.Surprised]: 0.62, [VRMExpressionPresetName.Happy]: 0.40 };
    default:
      return { [VRMExpressionPresetName.Neutral]: 0.20, [VRMExpressionPresetName.Relaxed]: 0.15 };
  }
}

function emotionFor(state: CompanionState): EmotionBlend {
  switch (state) {
    case "listening":   return { [VRMExpressionPresetName.Relaxed]: 0.28, [VRMExpressionPresetName.Happy]: 0.22 };
    case "thinking":    return { [VRMExpressionPresetName.Neutral]: 0.35, [VRMExpressionPresetName.Relaxed]: 0.22 };
    case "speaking":    return { [VRMExpressionPresetName.Happy]: 0.48, [VRMExpressionPresetName.Relaxed]: 0.20 };
    case "interrupted": return { [VRMExpressionPresetName.Surprised]: 0.38, [VRMExpressionPresetName.Relaxed]: 0.18 };
    case "error":       return { [VRMExpressionPresetName.Sad]: 0.42, [VRMExpressionPresetName.Relaxed]: 0.15 };
    default:            return { [VRMExpressionPresetName.Happy]: 0.25, [VRMExpressionPresetName.Relaxed]: 0.18 };
  }
}


/* ─── Conversational neutral pose ───────────────────────── */
// Offsets are always multiplied once against cached immutable normalized-bone
// rest quaternions. No raw J_Bip nodes and no cumulative Euler edits are used.
type PoseBoneName = "leftShoulder" | "rightShoulder" | "leftUpperArm" | "rightUpperArm" | "leftLowerArm" | "rightLowerArm" | "leftHand" | "rightHand";
const POSE_BONES: PoseBoneName[] = ["leftShoulder", "rightShoulder", "leftUpperArm", "rightUpperArm", "leftLowerArm", "rightLowerArm", "leftHand", "rightHand"];
const restOffset = () => new THREE.Quaternion();
const q = (x = 0, y = 0, z = 0) => new THREE.Quaternion().setFromEuler(new THREE.Euler(x, y, z, "XYZ"));

// `model_6164` is the screenshot baseline. Its authored normalized rest has
// horizontal upper arms; mirrored Z offsets lower shoulders without touching
// root scale/position or hands. Other known/managed rigs keep authored rest
// until their Avatar Lab calibration produces a reviewed profile.
const MODEL_POSE_OFFSETS: Record<string, Record<PoseBoneName, THREE.Quaternion>> = {
  "/models/hinaa.vrm": {
    leftShoulder: q(0, 0, 1.12), rightShoulder: q(0, 0, -1.12),
    leftUpperArm: q(-0.06, 0.06, 0.32), rightUpperArm: q(-0.06, -0.06, -0.32),
    leftLowerArm: q(0, 0, 0.36), rightLowerArm: q(0, 0, -0.36),
    leftHand: q(0.08, 0.05, 0.12), rightHand: q(0.08, -0.05, -0.12),
  },
  "/models/model_6164.vrm": {
    // Measured against the shipped VRM's actual horizontal upper-arm hierarchy.
    // Sharing rotation through shoulder → upper arm → forearm avoids a stiff
    // single-joint fold and reliably moves the visible sleeve line downward.
    leftShoulder: q(0, 0, 1.06), rightShoulder: q(0, 0, -1.06),
    leftUpperArm: q(0, 0, 0.34), rightUpperArm: q(0, 0, -0.34),
    leftLowerArm: q(0, 0, 0.24), rightLowerArm: q(0, 0, -0.24),
    leftHand: restOffset(), rightHand: restOffset(),
  },
  "/models/model_5447.vrm": {
    leftShoulder: q(0, 0, 0.72), rightShoulder: q(0, 0, -0.72),
    leftUpperArm: q(0, 0, 0.24), rightUpperArm: q(0, 0, -0.24),
    leftLowerArm: q(0, 0, 0.16), rightLowerArm: q(0, 0, -0.16),
    leftHand: restOffset(), rightHand: restOffset(),
  },
};
const DEFAULT_POSE_OFFSETS: Record<PoseBoneName, THREE.Quaternion> = {
  leftShoulder: restOffset(), rightShoulder: restOffset(), leftUpperArm: restOffset(), rightUpperArm: restOffset(),
  leftLowerArm: restOffset(), rightLowerArm: restOffset(), leftHand: restOffset(), rightHand: restOffset(),
};
// Generic imported VRMs begin in a natural relaxed pose
const GENERIC_RELAXED_POSE_OFFSETS: Record<PoseBoneName, THREE.Quaternion> = {
  leftShoulder: q(0, 0, 1.10), rightShoulder: q(0, 0, -1.10),
  leftUpperArm: q(-0.05, 0.05, 0.30), rightUpperArm: q(-0.05, -0.05, -0.30),
  leftLowerArm: q(0, 0, 0.32), rightLowerArm: q(0, 0, -0.32),
  leftHand: q(0.06, 0.04, 0.10), rightHand: q(0.06, -0.04, -0.10),
};

function resolvePoseOffsets(url: string): Record<PoseBoneName, THREE.Quaternion> {
  const norm = (url || "").toLowerCase();
  for (const [key, offsets] of Object.entries(MODEL_POSE_OFFSETS)) {
    if (norm.includes(key.toLowerCase()) || key.toLowerCase().includes(norm)) {
      return offsets;
    }
  }
  return GENERIC_RELAXED_POSE_OFFSETS;
}

const ALL_FINGER_BONES: VRMHumanBoneName[] = [
  VRMHumanBoneName.LeftThumbMetacarpal, VRMHumanBoneName.LeftThumbProximal, VRMHumanBoneName.LeftThumbDistal,
  VRMHumanBoneName.LeftIndexProximal, VRMHumanBoneName.LeftIndexIntermediate, VRMHumanBoneName.LeftIndexDistal,
  VRMHumanBoneName.LeftMiddleProximal, VRMHumanBoneName.LeftMiddleIntermediate, VRMHumanBoneName.LeftMiddleDistal,
  VRMHumanBoneName.LeftRingProximal, VRMHumanBoneName.LeftRingIntermediate, VRMHumanBoneName.LeftRingDistal,
  VRMHumanBoneName.LeftLittleProximal, VRMHumanBoneName.LeftLittleIntermediate, VRMHumanBoneName.LeftLittleDistal,
  VRMHumanBoneName.RightThumbMetacarpal, VRMHumanBoneName.RightThumbProximal, VRMHumanBoneName.RightThumbDistal,
  VRMHumanBoneName.RightIndexProximal, VRMHumanBoneName.RightIndexIntermediate, VRMHumanBoneName.RightIndexDistal,
  VRMHumanBoneName.RightMiddleProximal, VRMHumanBoneName.RightMiddleIntermediate, VRMHumanBoneName.RightMiddleDistal,
  VRMHumanBoneName.RightRingProximal, VRMHumanBoneName.RightRingIntermediate, VRMHumanBoneName.RightRingDistal,
  VRMHumanBoneName.RightLittleProximal, VRMHumanBoneName.RightLittleIntermediate, VRMHumanBoneName.RightLittleDistal,
];
type FingerBoneName = (typeof ALL_FINGER_BONES)[number];

/* ─── Model component ────────────────────────────────────── */
interface ModelProps {
  state: CompanionState;
  jawEnergy: React.MutableRefObject<number>;
  speakingRef: React.MutableRefObject<boolean>;
  visemeEvents: React.MutableRefObject<VisemeEvent[]>;
  audioStartTimeRef: React.MutableRefObject<number>;
  url: string;
  presentation: AvatarPresentation;
  faceExpressions?: FaceExpressions | null;
  faceBones?: Record<string, [number, number, number, number]> | null;
  faceTrackingActive?: boolean;
  trackingCalibration?: {
    headBaseline?: [number, number, number, number];
    expressionBaseline?: Partial<FaceExpressions>;
  } | null;
  expressionText?: string;
  onAnatomyFrame?: (frame: AnatomyFrame) => void;
  onLoadState?: (state: "loading" | "ready" | "failed") => void;
  isWalking?: boolean;
  plan?: AssistantTurnPlan;
  liveStatus?: FullscreenLiveStatus;
}

function Model({
  state, jawEnergy, speakingRef, visemeEvents, audioStartTimeRef, url, presentation, faceExpressions, faceBones, faceTrackingActive, trackingCalibration, expressionText, onAnatomyFrame, onLoadState, isWalking = false, plan, liveStatus,
}: ModelProps) {
  const vrmRef   = useRef<VRM | null>(null);
  const availRef = useRef<Set<string>>(new Set());
  // What a loaded rig actually registers is whatever its author named the
  // blend shapes, not the spec strings three-vrm's enum exposes. This model
  // registers `VRMExpression_Surprised` with a capital S, so every write to
  // "surprised" landed nowhere and her upper face had nothing but blink.
  const rigNamesRef  = useRef<Map<string, string>>(new Map());
  const writeNameRef = useRef<Map<string, string | null>>(new Map());
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);

  const normBonesRef = useRef<Partial<Record<PoseBoneName, THREE.Object3D>>>({});
  const curQRef      = useRef<Partial<Record<PoseBoneName, THREE.Quaternion>>>({});
  const restQRef     = useRef<Partial<Record<PoseBoneName, THREE.Quaternion>>>({});
  const poseTargetRef = useRef<Partial<Record<PoseBoneName, THREE.Quaternion>>>({});
  const headBoneRef = useRef<THREE.Object3D | null>(null);
  const jawBoneRef = useRef<THREE.Object3D | null>(null);
  const headRestQRef = useRef<THREE.Quaternion | null>(null);
  const headCurQRef = useRef<THREE.Quaternion | null>(null);
  // Idle liveliness: the chest/upperChest bone is NOT in POSE_BONES, so it is
  // safe to drive a gentle breathing motion here without fighting the arm/
  // shoulder pose-lock. Rest quaternion is captured once at load.
  const chestBoneRef = useRef<THREE.Object3D | null>(null);
  const chestRestQRef = useRef<THREE.Quaternion | null>(null);

  // Procedural walking bones & rest transforms
  const hipsBoneRef = useRef<THREE.Object3D | null>(null);
  const hipsRestPosRef = useRef<THREE.Vector3 | null>(null);
  const hipsRestQRef = useRef<THREE.Quaternion | null>(null);
  const spineBoneRef = useRef<THREE.Object3D | null>(null);
  const spineRestQRef = useRef<THREE.Quaternion | null>(null);
  const leftUpperLegRef = useRef<THREE.Object3D | null>(null);
  const leftUpperLegRestQRef = useRef<THREE.Quaternion | null>(null);
  const rightUpperLegRef = useRef<THREE.Object3D | null>(null);
  const rightUpperLegRestQRef = useRef<THREE.Quaternion | null>(null);
  const leftLowerLegRef = useRef<THREE.Object3D | null>(null);
  const leftLowerLegRestQRef = useRef<THREE.Quaternion | null>(null);
  const rightLowerLegRef = useRef<THREE.Object3D | null>(null);
  const rightLowerLegRestQRef = useRef<THREE.Quaternion | null>(null);
  const leftFootRef = useRef<THREE.Object3D | null>(null);
  const leftFootRestQRef = useRef<THREE.Quaternion | null>(null);
  const rightFootRef = useRef<THREE.Object3D | null>(null);
  const rightFootRestQRef = useRef<THREE.Quaternion | null>(null);

  // Procedural walk gait dynamics
  const walkWeightRef = useRef(0);
  const walkPhaseRef = useRef(0);
  const walkRoamXRef = useRef(0);
  const walkDirectionRef = useRef(1);
  const walkTurnYawRef = useRef(0);
  const lastFootstepSideRef = useRef<"left" | "right" | null>(null);

  // Per-frame refs — no allocations
  const t           = useRef(0);
  const blinkTimer  = useRef(2 + Math.random() * 3);
  const doubleBlink = useRef(false);
  // Per-blink shape — rerolled every blink so no two blinks look identical:
  // peak amplitude (partial blinks are common), close/open durations, and a
  // slight left/right lid asymmetry that makes the face read organic.
  const blinkShape = useRef({ peak: 0.78, close: 0.07, open: 0.14, asym: 1.0 });
  // Current combined blink amplitude, exposed so the gaze layer can dip the
  // eyes with the lids (real blink-linked gaze coordination).
  const blinkLevel = useRef(0);
  // How long speech audio has sat in a pause — used to land blink bursts
  // at phrase boundaries instead of mid-syllable.
  const blinkPauseHold = useRef(0);
  // Blink-recovery brow lift: detects the reopening edge of a blink and
  // floats the brows up for a beat, then damps back to neutral.
  const prevBlinkLevel = useRef(0);
  const browLift = useRef(0);
  const saccadeTimer = useRef(3.2 + Math.random() * 2);
  const saccadeTarget = useRef({ x: 0, y: 0 });
  // Current mouth weights (smoothed)
  const mouthW      = useRef<Record<MouthKey, number>>({ aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 });
  const emo         = useRef<Record<string, number>>({});
  // Live samples are mutable refs delivered at VMC packet rate. Smooth their
  // visual application at render rate to remove camera/packet jitter while
  // retaining immediate conversational expression changes.
  const smoothFace  = useRef<FaceExpressions>({ mouthOpen: 0, mouthA: 0, mouthI: 0, mouthU: 0, mouthE: 0, mouthO: 0, mouthSmile: 0, eyeBlinkL: 0, eyeBlinkR: 0, browUpL: 0, browUpR: 0, browDownL: 0, browDownR: 0, cheekPuff: 0, angry: 0, sad: 0, relaxed: 0 });
  const faceMeshRef = useRef<THREE.SkinnedMesh | null>(null);
  const morphDictRef = useRef<Record<string, number>>({});
  const curDirectMorphsRef = useRef<Record<string, number>>({});
  const fingerBonesRef = useRef<Partial<Record<FingerBoneName, THREE.Object3D>>>({});
  const fingerRestQRef = useRef<Partial<Record<FingerBoneName, THREE.Quaternion>>>({});
  const smoothEnergyRef = useRef(0);
  const convoEnergyRef = useRef(0);
  // AudioContext ref — populated lazily from global on first frame
  const speechBridge = useContext(SpeechPlaybackContext);
  const planEmotionStr = typeof plan?.emotion === "string" ? plan.emotion : plan?.emotion?.primary;
  const sentenceSegments = useMemo(() => parseExpressionSegments(expressionText, state, planEmotionStr), [expressionText, state, planEmotionStr]);
  const rawIntent = useMemo(() => expressionIntentFor(expressionText, state, planEmotionStr), [expressionText, state, planEmotionStr]);
  // Per-utterance occurrence nonce: bumps every time a new utterance arrives so
  // repeat deliveries of the same line act differently (see computeAffectiveProfile).
  const deliveryCountRef = useRef(0);
  const lastExpressionRef = useRef<string | undefined>(undefined);
  const deliveryOccurrence = useMemo(() => {
    if (expressionText !== lastExpressionRef.current) {
      lastExpressionRef.current = expressionText;
      deliveryCountRef.current += 1;
    }
    return deliveryCountRef.current;
  }, [expressionText]);


  const stateEmotion = useMemo(() => emotionFor(state), [state]);
  const motionPose = useMemo(() => ({pitch:0,yaw:0,roll:0,arm:0,wrist:0}), []);
  const gestureEnergy = useRef(0);
  const scratch = useMemo(() => ({gaze:new THREE.Vector3(), raw:new THREE.Quaternion(), neutral:new THREE.Quaternion(),
    identity:new THREE.Quaternion(), target:new THREE.Quaternion(), rotation:new THREE.Quaternion(), euler:new THREE.Euler()}), []);

  useEffect(() => {
    let mounted = true;
    setLoaded(false);
    setFailed(false);
    onLoadState?.("loading");
    normBonesRef.current = {};
    curQRef.current = {};
    restQRef.current = {};
    poseTargetRef.current = {};
    headBoneRef.current = null;
    headRestQRef.current = null;
    headCurQRef.current = null;
    chestBoneRef.current = null;
    chestRestQRef.current = null;
    hipsBoneRef.current = null;
    hipsRestPosRef.current = null;
    hipsRestQRef.current = null;
    spineBoneRef.current = null;
    spineRestQRef.current = null;
    leftUpperLegRef.current = null;
    leftUpperLegRestQRef.current = null;
    rightUpperLegRef.current = null;
    rightUpperLegRestQRef.current = null;
    leftLowerLegRef.current = null;
    leftLowerLegRestQRef.current = null;
    rightLowerLegRef.current = null;
    rightLowerLegRestQRef.current = null;
    leftFootRef.current = null;
    leftFootRestQRef.current = null;
    rightFootRef.current = null;
    rightFootRestQRef.current = null;
    availRef.current = new Set();
    rigNamesRef.current = new Map();
    writeNameRef.current = new Map();
    t.current = 0;
    mouthW.current = { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 };
    smoothFace.current = { mouthOpen: 0, mouthA: 0, mouthI: 0, mouthU: 0, mouthE: 0, mouthO: 0, mouthSmile: 0, eyeBlinkL: 0, eyeBlinkR: 0, browUpL: 0, browUpR: 0, browDownL: 0, browDownR: 0, cheekPuff: 0, angry: 0, sad: 0, relaxed: 0 };


    const ldr = new GLTFLoader();
    ldr.crossOrigin = "anonymous";
    ldr.register(p => new VRMLoaderPlugin(p));

    ldr.load(url, gltf => {
      if (!mounted) {
        const staleVrm = gltf.userData.vrm as VRM | undefined;
        if (staleVrm) VRMUtils.deepDispose(staleVrm.scene);
        return;
      }
      const v = gltf.userData.vrm as VRM;
      if (!v) { setFailed(true); onLoadState?.("failed"); return; }

      // Optimizations — live path. This is the (previously missing) GPU-load
      // reduction the avatar exports need: the VRM ships ~2048 textures and
      // hundreds of morph targets; without this the first frame uploads
      // everything at full size and integrated GPUs stutter or lose the
      // context. Downscale to 1024, prune morphs to the expressions HINAA
      // drives (presets + viseme aliases), and re-enable per-mesh culling.
      try { VRMUtils.removeUnnecessaryVertices(v.scene); } catch {}
      try { VRMUtils.removeUnnecessaryJoints(v.scene); } catch {}
      try {
        optimizeVrm(v, {
          maxTextureSize: 1024,
          keepExpressionNames: [
            "happy", "angry", "sad", "relaxed", "surprised", "neutral",
            "blink", "blinkLeft", "blinkRight",
            "aa", "ih", "ou", "ee", "oh",
            "a", "i", "u", "e", "o",
            "joy", "sorrow", "fun", "blink_l", "blink_r",
          ],
        });
      } catch { /* keep the model as loaded */ }
      v.scene.traverse((o: THREE.Object3D) => {
        // Culling: compute real bounding spheres so the renderer can skip
        // off-screen parts (the old hard-coded false disabled culling for the
        // whole model — measurable cost at closeup mode). Kept as a traverse
        // loop because a VRM 0.x model can expose a mix of mesh types.
        if ((o as THREE.Mesh).isMesh) {
          const mesh = o as THREE.Mesh;
          try { mesh.geometry.computeBoundingSphere(); } catch {}
        }
      });

      // Orientation
      const isVrm0 = (v as any).meta?.metaVersion === "0" || ((v as any).meta?.specVersion ?? "").startsWith("0");
      if (isVrm0) {
        try { VRMUtils.rotateVRM0(v); } catch {}
      }

      if (v.lookAt) { try { (v.lookAt as any).enabled = false; } catch {} }

      const defaultPres = defaultAvatarPresentation(url);
      const baseRotationY = (presentation.rotationY === 0 && defaultPres.rotationY === Math.PI)
        ? Math.PI
        : presentation.rotationY;

      v.scene.rotation.y = baseRotationY;
      v.scene.position.y = presentation.offsetY;
      v.scene.scale.setScalar(presentation.scale);

      // Derive a stable frame only after the calibrated transform is applied.
      // This runs on model load, never in the render loop, so it cannot drift.
      v.scene.updateMatrixWorld(true);
      const bounds = new THREE.Box3().setFromObject(v.scene);
      const center = bounds.getCenter(new THREE.Vector3());
      const size = bounds.getSize(new THREE.Vector3());
      const head = v.humanoid?.getNormalizedBoneNode("head" as any);
      const neck = v.humanoid?.getNormalizedBoneNode("neck" as any);
      const chest = v.humanoid?.getNormalizedBoneNode("upperChest" as any)
        ?? v.humanoid?.getNormalizedBoneNode("chest" as any)
        ?? v.humanoid?.getNormalizedBoneNode("spine" as any);
      const hips = v.humanoid?.getNormalizedBoneNode("hips" as any);
      const headY = head?.getWorldPosition(new THREE.Vector3()).y ?? bounds.max.y - Math.max(0.14, size.y * 0.08);
      const chestY = chest?.getWorldPosition(new THREE.Vector3()).y ?? bounds.min.y + size.y * 0.58;
      const safeHeadY = Math.max(chestY + 0.2, headY);
      const neckY = neck?.getWorldPosition(new THREE.Vector3()).y ?? safeHeadY - Math.max(0.10, (safeHeadY - chestY) * 0.28);
      const hipsY = hips?.getWorldPosition(new THREE.Vector3()).y ?? bounds.min.y + size.y * 0.38;
      onAnatomyFrame?.({
        centerX: center.x,
        headY: safeHeadY,
        neckY: Math.max(chestY + 0.08, neckY),
        chestY,
        hipsY: Math.min(chestY - 0.08, hipsY),
        minY: bounds.min.y,
        maxY: bounds.max.y,
        revision: `${url}:${bounds.min.y.toFixed(3)}:${bounds.max.y.toFixed(3)}:${safeHeadY.toFixed(3)}`,
      });

      // Cache available expressions
      const em = v.expressionManager;
      if (em) {
        const allNames = [
          ...Object.values(VRMExpressionPresetName),
          "a", "i", "u", "e", "o", "blink_l", "blink_r", "joy", "sorrow", "fun",
          "happy", "angry", "sad", "relaxed", "surprised", "blinkLeft", "blinkRight",
        ];
        for (const name of allNames) {
          try { if (em.getExpression(name)) availRef.current.add(name); } catch {}
        }
        // The spec probe above only proves the names three-vrm itself knows.
        // Whatever else the file's author called a blend shape is reachable only
        // by the literal name, so index those too for a case-insensitive match.
        try {
          for (const registered of (em as any).expressions ?? []) {
            const literal: unknown = registered?.name;
            if (typeof literal !== "string" || !literal) continue;
            const bare = literal.replace(/^(VRMExpression_|VRM_v1_)/, "");
            for (const form of [literal, bare]) {
              const key = form.toLowerCase();
              if (!rigNamesRef.current.has(key)) rigNamesRef.current.set(key, form);
            }
          }
        } catch {}

        // Cache face skinned mesh and its 57 morph targets for direct micro-acting
        try {
          v.scene.traverse((obj) => {
            const mesh = obj as THREE.SkinnedMesh;
            if (mesh.isSkinnedMesh && mesh.morphTargetDictionary && mesh.morphTargetInfluences) {
              if (mesh.name.toLowerCase().includes("face") || mesh.morphTargetDictionary["Fcl_ALL_Joy"] !== undefined || mesh.morphTargetDictionary["Fcl_EYE_Joy"] !== undefined) {
                faceMeshRef.current = mesh;
                morphDictRef.current = mesh.morphTargetDictionary;
              }
            }
          });
        } catch {}
      }

      // Cache normalized bone nodes and immutable rest quaternions once. The
      // per-frame loop only slerps to the precomputed calibrated targets.
      const hd = v.humanoid;
      if (hd) {
        const offsets = presentation.poseMode === "original"
          ? DEFAULT_POSE_OFFSETS
          : resolvePoseOffsets(url);
        for (const boneName of POSE_BONES) {
          try {
            const node = hd.getNormalizedBoneNode(boneName as any);
            if (node) {
              const rest = node.quaternion.clone();
              normBonesRef.current[boneName] = node;
              restQRef.current[boneName] = rest;
              curQRef.current[boneName] = rest.clone();
              poseTargetRef.current[boneName] = rest.clone().multiply(offsets[boneName]);
            }
          } catch {}
        }
        try {
          const headNode = hd.getNormalizedBoneNode("head" as any);
          if (headNode) {
            headBoneRef.current = headNode;
            headRestQRef.current = headNode.quaternion.clone();
            headCurQRef.current = headNode.quaternion.clone();
          }
        } catch {}
        try {
          const chestNode = hd.getNormalizedBoneNode("upperChest" as any)
            ?? hd.getNormalizedBoneNode("chest" as any)
            ?? hd.getNormalizedBoneNode("spine" as any);
          if (chestNode) {
            chestBoneRef.current = chestNode;
            chestRestQRef.current = chestNode.quaternion.clone();
          }
        } catch {}
        try {
          const hipsNode = hd.getNormalizedBoneNode(VRMHumanBoneName.Hips);
          if (hipsNode) {
            hipsBoneRef.current = hipsNode;
            hipsRestPosRef.current = hipsNode.position.clone();
            hipsRestQRef.current = hipsNode.quaternion.clone();
          }
        } catch {}
        try {
          const spineNode = hd.getNormalizedBoneNode(VRMHumanBoneName.Spine);
          if (spineNode) {
            spineBoneRef.current = spineNode;
            spineRestQRef.current = spineNode.quaternion.clone();
          }
        } catch {}
        try {
          const lul = hd.getNormalizedBoneNode(VRMHumanBoneName.LeftUpperLeg);
          if (lul) { leftUpperLegRef.current = lul; leftUpperLegRestQRef.current = lul.quaternion.clone(); }
          const rul = hd.getNormalizedBoneNode(VRMHumanBoneName.RightUpperLeg);
          if (rul) { rightUpperLegRef.current = rul; rightUpperLegRestQRef.current = rul.quaternion.clone(); }
          const lll = hd.getNormalizedBoneNode(VRMHumanBoneName.LeftLowerLeg);
          if (lll) { leftLowerLegRef.current = lll; leftLowerLegRestQRef.current = lll.quaternion.clone(); }
          const rll = hd.getNormalizedBoneNode(VRMHumanBoneName.RightLowerLeg);
          if (rll) { rightLowerLegRef.current = rll; rightLowerLegRestQRef.current = rll.quaternion.clone(); }
          const lf = hd.getNormalizedBoneNode(VRMHumanBoneName.LeftFoot);
          if (lf) { leftFootRef.current = lf; leftFootRestQRef.current = lf.quaternion.clone(); }
          const rf = hd.getNormalizedBoneNode(VRMHumanBoneName.RightFoot);
          if (rf) { rightFootRef.current = rf; rightFootRestQRef.current = rf.quaternion.clone(); }
        } catch {}

        // Cache all 30 normalized finger bone nodes and immutable rest quaternions
        for (const fName of ALL_FINGER_BONES) {
          try {
            const fNode = hd.getNormalizedBoneNode(fName as any)
              ?? (fName === VRMHumanBoneName.LeftThumbMetacarpal ? hd.getNormalizedBoneNode("leftThumbProximal" as any) : null)
              ?? (fName === VRMHumanBoneName.LeftThumbProximal ? hd.getNormalizedBoneNode("leftThumbIntermediate" as any) : null)
              ?? (fName === VRMHumanBoneName.RightThumbMetacarpal ? hd.getNormalizedBoneNode("rightThumbProximal" as any) : null)
              ?? (fName === VRMHumanBoneName.RightThumbProximal ? hd.getNormalizedBoneNode("rightThumbIntermediate" as any) : null);
            if (fNode) {
              fingerBonesRef.current[fName] = fNode;
              fingerRestQRef.current[fName] = fNode.quaternion.clone();
            }
          } catch {}
        }
      }


      if (import.meta.env.DEV) {
        const bones = POSE_BONES.filter(b => !!normBonesRef.current[b]);
        const exprs = [...availRef.current].slice(0, 12).join(", ");
        console.log(`🎭 VRM ${isVrm0 ? "0.x" : "1.0"} | url=${url} | bones: ${bones.join(", ")} | expressions: ${exprs}`);
      }

      // The normalized Jaw bone is the lipsync safety net below; capture it
      // once per model load (absent on rigs without a jaw mapping).
      try {
        jawBoneRef.current = v.humanoid?.getNormalizedBoneNode(VRMHumanBoneName.Jaw) ?? null;
      } catch {
        jawBoneRef.current = null;
      }

      vrmRef.current = v;
      setLoaded(true);
      onLoadState?.("ready");
    }, undefined, () => { if (mounted) { setFailed(true); onLoadState?.("failed"); } });

    return () => {
      mounted = false;
      // Ensure mouth expressions are reset on unmount/unload
      if (vrmRef.current) {
        try { VRMUtils.deepDispose(vrmRef.current.scene); } catch {}
        vrmRef.current = null;
        faceMeshRef.current = null;
        morphDictRef.current = {};
        curDirectMorphsRef.current = {};
        fingerBonesRef.current = {};
        fingerRestQRef.current = {};
      }
    };
  }, [url, presentation.rotationY, presentation.offsetY, presentation.scale, presentation.poseMode, onLoadState]);

  useFrame((_, dtRaw) => {
    const vrm = vrmRef.current;
    if (!vrm) return;
    if (document.visibilityState !== "hidden") runtimeMeasurements.recordFrame(dtRaw);
    // Easing must survive a frame spike, but a rhythm counted in clamped frames
    // slows to a crawl as soon as the render loop drops below 20 fps — measured
    // at 4.2 fps the blink timer advances five times slower than wall clock and
    // she stops blinking entirely. Cadence therefore runs on real elapsed time.
    const dt = Math.min(dtRaw, 0.05);
    const realDt = Math.min(dtRaw, 0.5);
    t.current += realDt;
    const defaultPres = defaultAvatarPresentation(url);
    const baseRotationY = (presentation.rotationY === 0 && defaultPres.rotationY === Math.PI)
      ? Math.PI
      : presentation.rotationY;
    const isListening = state === "listening" || (liveStatus?.active && liveStatus?.status === "listening");
    const playbackSample = speechBridge ? sampleSpeechPlayback(speechBridge) : null;
    const audioSpeaking = !isListening && (playbackSample ? playbackSample.speaking : speakingRef.current);
    const isSpeakingNow = !isListening && !!(audioSpeaking || state === "speaking");
    let activeIntent = isSpeakingNow ? rawIntent : (isListening ? "warm" : "neutral");
    let speechProgress = 0;
    if (isSpeakingNow && playbackSample && sentenceSegments.length > 1) {
      const events = playbackSample.events ?? visemeEvents.current;
      const totalDuration = events.length > 0 ? (events[events.length - 1].timeMs + events[events.length - 1].durationMs) : 4000;
      speechProgress = totalDuration > 0 ? THREE.MathUtils.clamp(playbackSample.timeMs / totalDuration, 0, 1) : 0;
      activeIntent = getTemporalIntent(sentenceSegments, speechProgress);
    }
    const affectiveProfile = computeAffectiveProfile(expressionText, state, planEmotionStr, speechProgress, isSpeakingNow, deliveryOccurrence);
    const directedEmotion = isSpeakingNow
      ? emotionForIntent(activeIntent)
      : { [VRMExpressionPresetName.Relaxed]: 0.28, [VRMExpressionPresetName.Happy]: 0.18, [VRMExpressionPresetName.Surprised]: 0.0 };

    const targetGesture = audioSpeaking ? Math.min(1, jawEnergy.current * 2) : 0;
    gestureEnergy.current += (targetGesture - gestureEnergy.current) * (1 - Math.exp(-dt * 4));
    sampleConversationMotion(t.current, gestureEnergy.current, state === "thinking" || audioSpeaking, motionPose);

    const em  = vrm.expressionManager;
    // Never let a stale/synthetic transport sample suppress HINAA's own blink,
    // emotion, or relaxed-pose system. Face input becomes visual authority only
    // after the parent has verified fresh external tracking.
    const face = faceTrackingActive && faceExpressions ? smoothFace.current : null;
    if (face && faceExpressions) {
      const trackingAlpha = 1 - Math.exp(-dt * 12);
      for (const key of Object.keys(face) as Array<keyof FaceExpressions>) {
        face[key] += (faceExpressions[key] - face[key]) * trackingAlpha;
      }
    }
    // Writes go through the names this rig actually registers. Every frame the
    // loop asks for spec presets; three-vrm resolves them case-sensitively, so a
    // file that named its blend shape `VRMExpression_Surprised` silently dropped
    // the whole surprised channel. Resolution is memoised per requested name —
    // including the failures — so the hot loop pays a map lookup, not a probe.
    const resolveWrite = (n: string): string | null => {
      const cache = writeNameRef.current;
      if (cache.has(n)) return cache.get(n) ?? null;
      const rigName = availRef.current.has(n)
        ? n
        : rigNamesRef.current.get(n.toLowerCase()) ?? null;
      const alias = PRESET_ALIASES[n];
      const resolved = rigName
        ?? (alias && (availRef.current.has(alias) || rigNamesRef.current.has(alias.toLowerCase())) ? alias : null);
      cache.set(n, resolved);
      return resolved;
    };
    const set = (n: string, v: number) => {
      if (!em) return;
      const name = resolveWrite(n);
      if (!name) return;
      try { em.setValue(name, v); } catch {}
    };

    /* ── LAYER 1 + 2: LIP-SYNC ────────────────────────────────────────
     * When speaking:
     *   - Use viseme events timed against AudioContext clock
     *   - Scale weight by jawEnergy (audio RMS amplitude)
     *   - Fade mouth closed when not speaking
     * When face tracking:
     *   - Mirror VSeeFace mouth open value
     */
    if (em) {
      const speechSample = playbackSample;
      const speaking = !isListening && (speechSample ? speechSample.speaking : speakingRef.current);
      // RMS values vary greatly across local voice engines and browsers. Shape
      // them for visible but natural articulation instead of treating quiet
      // speech as silence. When in listening mode, raw energy is forced to zero so lips stay closed.
      const rawEnergy = (!speaking || isListening) ? 0 : Math.min(1, Math.max(0, jawEnergy.current * 3.2));
      // Low-pass filter raw audio RMS to eliminate frame-to-frame mouth jitter
      smoothEnergyRef.current += (rawEnergy - smoothEnergyRef.current) * (1 - Math.exp(-dt * 24));
      const smoothed = isListening ? 0 : smoothEnergyRef.current;
      // Conversational energy cadence: rides conversational phrasing smoothly
      const targetConvo = speaking ? Math.max(0.35, Math.min(1, smoothed * 1.5)) : (state === "thinking" ? 0.35 : 0);
      convoEnergyRef.current += (targetConvo - convoEnergyRef.current) * (1 - Math.exp(-dt * (targetConvo > convoEnergyRef.current ? 8 : 4)));
      // Amplitude floor while speaking: browser-speech playback produces no
      // analyser signal (the audio never enters our graph), so energy-only
      // scaling pinned the mouth at a barely-visible 0.16 and the lips looked
      // frozen. The viseme timeline itself carries the articulation; a firm
      // floor keeps it legible in every TTS path while loud audio still
      // swings the jaw higher.
      const energy = speaking ? Math.max(0.48, Math.sqrt(smoothed) * 0.95) : 0;

      if (speaking) {
        // ── Speaking: viseme-based mouth animation ──
        const events = speechSample?.events ?? visemeEvents.current;
        let targetMouth: MouthKey | null = null;
        let targetWeight = 0;

        if (events.length > 0) {
          // Use AudioContext time if available, else fallback to energy cycling
          if (speechSample) {
            const active = speechSample.viseme;
            if (active && active.mouth !== "closed") {
              targetMouth = VISEME_TO_VRM[active.mouth] as MouthKey ?? "aa";
              targetWeight = Math.max(0.10, active.weight * energy);
            } else {
              targetMouth = null;
              targetWeight = 0;
            }
          } else {
            // Fallback when the AudioContext clock is unavailable: blend mouth
            // shape from the energy envelope instead of robotic 7Hz cycling.
            // Aa (open) dominates on peaks, Ou/Ih shape the sustained vowels.
            const env = energy;
            if (env > 0.72) { targetMouth = "aa"; targetWeight = Math.min(1, env); }
            else if (env > 0.48) { targetMouth = "ou"; targetWeight = env * 0.85; }
            else if (env > 0.28) { targetMouth = "ih"; targetWeight = env * 0.7; }
            else { targetMouth = "aa"; targetWeight = Math.max(0.05, env * 0.5); }
          }
        } else {
          // No viseme events — energy-based jaw-open fallback
          targetMouth = "aa";
          targetWeight = energy;
        }

        // Smooth all mouth shapes (forward faster than decay: the mouth opens
        // onto the phoneme, then closes gradually into the next window).
        for (const k of ALL_MOUTH_KEYS) {
          const tgt = k === targetMouth ? targetWeight : 0;
          const rate = tgt > mouthW.current[k] ? 28 : 18;
          mouthW.current[k] += (tgt - mouthW.current[k]) * (1 - Math.exp(-dt * rate));
          set(VRM_PRESET[k], Math.max(0, mouthW.current[k]));
        }
      } else if (!isListening && face && trackingCalibration?.expressionBaseline) {
        // ── Calibrated external VMC, while not speaking ──
        // Some VSeeFace senders keep a small mouth-open value at rest. Do not
        // interpret that neutral baseline as an open mouth: facial mouth motion
        // becomes active only after a user-captured neutral baseline and uses a
        // bounded positive delta. HINAA's TTS remains the sole mouth owner while
        // she speaks above.
        const baseline = trackingCalibration.expressionBaseline;
        const neutralMouth = baseline.mouthOpen ?? 0;
        const tracked: Record<MouthKey, number> = {
          aa: Math.max(
            Math.max(0, face.mouthA - (baseline.mouthA ?? 0)),
            Math.max(0, face.mouthOpen - neutralMouth),
          ),
          ih: Math.max(0, face.mouthI - (baseline.mouthI ?? 0)),
          ou: Math.max(0, face.mouthU - (baseline.mouthU ?? 0)),
          ee: Math.max(0, face.mouthE - (baseline.mouthE ?? 0)),
          oh: Math.max(0, face.mouthO - (baseline.mouthO ?? 0)),
        };
        for (const k of ALL_MOUTH_KEYS) {
          mouthW.current[k] += (tracked[k] - mouthW.current[k]) * Math.min(1, dt * 12);
          set(VRM_PRESET[k], Math.max(0, mouthW.current[k]));
        }
      } else {
        // ── Idle / listening / silence: fade mouth closed ──
        let allZero = true;
        for (const k of ALL_MOUTH_KEYS) {
          mouthW.current[k] *= Math.max(0, 1 - dt * 32);
          if (mouthW.current[k] < 0.003) mouthW.current[k] = 0;
          else allZero = false;
          set(VRM_PRESET[k], mouthW.current[k]);
        }
        if (allZero || isListening) {
          // Ensure all are strictly 0 while listening or at silence
          for (const k of ALL_MOUTH_KEYS) {
            mouthW.current[k] = 0;
            set(VRM_PRESET[k], 0);
          }
        }
      }

      /* ── LAYER 3: BLINK ─────────────────────────────────────────── */
      if (face) {
        // VMC `Fcl_EYE_Close_*` is a closure weight: 0 means open and 1
        // means closed. Do not invert it here; inversion made live VSeeFace
        // input hold HINAA's eyes shut. Keep a small eyelid opening visible
        // under noisy tracking rather than rendering a permanently blank face.
        const blL = Math.min(0.88, Math.max(0, face.eyeBlinkL));
        const blR = Math.min(0.88, Math.max(0, face.eyeBlinkR));
        set(VRMExpressionPresetName.BlinkLeft,  blL);
        set(VRMExpressionPresetName.BlinkRight, blR);
        set(VRMExpressionPresetName.Blink, (blL + blR) / 2);
        blinkLevel.current = (blL + blR) / 2;
      } else {
        // Natural auto-blink: variable amplitude (partial blinks are common),
        // fast close / slower open with a soft ease, slight lid asymmetry,
        // quick follow-through on double blinks, slower heavy blinks when
        // drowsy, and a quicker rhythm while she is speaking.
        const rollBlinkShape = () => {
          const drowsyHeavy = affectiveProfile.drowsy;
          blinkShape.current = {
            peak: 0.55 + Math.random() * 0.35 + drowsyHeavy * 0.08,
            close: (0.055 + Math.random() * 0.035) * (1 + drowsyHeavy * 0.9),
            open: (0.115 + Math.random() * 0.065) * (1 + drowsyHeavy * 0.6),
            asym: 0.90 + Math.random() * 0.16,
          };
        };
        // Blink bursts at speech pauses: humans blink at phrase boundaries.
        // When she is speaking but the audio energy dips into a pause, pull
        // the next blink forward so it lands in the gap, not mid-syllable.
        if (isSpeakingNow && blinkTimer.current > 0.9 && smoothEnergyRef.current < 0.07) {
          blinkPauseHold.current += realDt;
          if (blinkPauseHold.current > 0.28) {
            blinkTimer.current = Math.min(blinkTimer.current, 0.10 + Math.random() * 0.18);
          }
        } else {
          blinkPauseHold.current = 0;
        }
        blinkTimer.current -= realDt;
        let bvL = 0, bvR = 0;
        const smooth = (u: number) => u * u * (3 - 2 * u);
        if (blinkTimer.current <= 0) {
          const tBlink = -blinkTimer.current;
          const { peak, close: CLOSE, open: OPEN, asym } = blinkShape.current;
          if (tBlink < CLOSE) {
            const u = smooth(tBlink / CLOSE);
            bvL = peak * u;
            bvR = peak * asym * u;
          } else if (tBlink < CLOSE + OPEN) {
            const u = 1 - smooth((tBlink - CLOSE) / OPEN);
            bvL = peak * u;
            bvR = peak * asym * u;
          } else if (doubleBlink.current) {
            // Second blink of a pair follows quickly (real double-blink
            // cadence is ~120-260 ms, not seconds).
            doubleBlink.current = false;
            blinkTimer.current = 0.12 + Math.random() * 0.14;
            rollBlinkShape();
          } else if (Math.random() < 0.16) {
            doubleBlink.current = true;
            blinkTimer.current = Math.max(0.04, realDt);
          } else {
            const rhythm = isSpeakingNow ? 0.72 : 1 + affectiveProfile.drowsy * 0.35;
            blinkTimer.current = (2.3 + Math.random() * 3.9) * rhythm;
            rollBlinkShape();
          }
        }
        // Playful / flirty subtle asymmetric micro-wink (rare charming anime moment)
        const isPlayful = rawIntent === "playful" || rawIntent === "flirty_warm";
        const winkL = isPlayful && Math.sin(t.current * 0.45) > 0.97 ? 0.65 : 0;
        set(VRMExpressionPresetName.Blink, (bvL + bvR) / 2);
        set(VRMExpressionPresetName.BlinkLeft, Math.max(bvL, winkL));
        set(VRMExpressionPresetName.BlinkRight, bvR);
        blinkLevel.current = (bvL + bvR) / 2;
      }

      /* ── LAYER 4: HIGH-LEVEL EMOTION ACTING & MICRO-EXPRESSIONS ────── */
      if (face) {
        const capEmo = (v: number) => Math.min(0.85, Math.max(0, v));
        const directed = (preset: VRMExpressionPresetName) => directedEmotion[preset] ?? 0;
        set(VRMExpressionPresetName.Happy,     capEmo(Math.max(face.mouthSmile, directed(VRMExpressionPresetName.Happy))));
        set(VRMExpressionPresetName.Surprised, capEmo(Math.max((face.browUpL + face.browUpR) / 2, directed(VRMExpressionPresetName.Surprised))));
        set(VRMExpressionPresetName.Angry,     capEmo(Math.max(face.angry, (face.browDownL + face.browDownR) / 2, directed(VRMExpressionPresetName.Angry))));
        set(VRMExpressionPresetName.Sad,       capEmo(Math.max(face.sad, directed(VRMExpressionPresetName.Sad))));
        set(VRMExpressionPresetName.Relaxed,   capEmo(Math.max(face.relaxed, face.cheekPuff, directed(VRMExpressionPresetName.Relaxed))));
      } else {
        const tEmo = stateEmotion;
        // Syllabic vocal emphasis: audio peaks (rawEnergy > 0.52) trigger an eyebrow flash (surprised)
        // and subtle chin articulation, matching high-level anime character voice acting
        const vocalEmphasis = speaking && rawEnergy > 0.52 ? (rawEnergy - 0.52) * 0.45 : 0;
        const articulation = Math.max(mouthW.current.aa, mouthW.current.oh) * 0.16 + vocalEmphasis;

        // Micro-expression liveliness: subtle non-periodic organic breathing in expression weights
        const organicBreath = Math.sin(t.current * 1.6) * Math.sin(t.current * 0.42 + 0.8) * 0.04;

        const emoKeys = [
          VRMExpressionPresetName.Happy, VRMExpressionPresetName.Sad,
          VRMExpressionPresetName.Relaxed, VRMExpressionPresetName.Angry,
          VRMExpressionPresetName.Surprised,
        ] as const;

        for (const key of emoKeys) {
          let tgt = Math.max(tEmo[key] ?? 0, directedEmotion[key] ?? 0);

          if (key === VRMExpressionPresetName.Happy) {
            // Keep radiant smile active during speech while easing slightly for vowel visemes
            if (speaking) tgt = Math.max(0.35, tgt * 0.75);
            tgt = Math.min(0.95, tgt + organicBreath);
          } else if (key === VRMExpressionPresetName.Surprised) {
            tgt = Math.min(0.92, tgt + articulation);
          } else if (key === VRMExpressionPresetName.Relaxed) {
            tgt = Math.min(0.60, tgt + organicBreath * 0.5);
          }

          emo.current[key] = (emo.current[key] ?? 0) + (tgt - (emo.current[key] ?? 0)) * Math.min(1, realDt * 3.2);
          set(key, emo.current[key]);
        }
      }

      /* ── LAYER 5: GAZE — subtle eye movement ─────────────────────── */
      // Human-like saccadic gaze dynamics (natural micro-fixations)
      saccadeTimer.current -= realDt;
      if (saccadeTimer.current <= 0) {
        if (Math.random() < 0.38) {
          saccadeTarget.current.x = (Math.random() - 0.5) * 0.06;
          saccadeTarget.current.y = (Math.random() - 0.5) * 0.035;
          saccadeTimer.current = 0.8 + Math.random() * 0.9;
        } else {
          saccadeTarget.current.x = 0;
          saccadeTarget.current.y = 0;
          saccadeTimer.current = 2.5 + Math.random() * 3.5;
        }
      }
      let gazX = saccadeTarget.current.x + Math.sin(t.current * 0.18) * 0.02;
      let gazY = saccadeTarget.current.y + Math.sin(t.current * 0.14 + 1.2) * 0.015;
      if (activeIntent === "thinking" || affectiveProfile.scenarioArchetype === "intellectual_focused") {
        gazX = -0.06 + Math.sin(t.current * 0.5) * 0.015;
        gazY = 0.04 + Math.sin(t.current * 0.3) * 0.015;
      } else if (affectiveProfile.scenarioArchetype === "casual_bro") {
        gazX = THREE.MathUtils.clamp(gazX, -0.04, 0.04);
        gazY = THREE.MathUtils.clamp(gazY, -0.03, 0.03);
      } else if (activeIntent === "shy" || affectiveProfile.scenarioArchetype === "shy_flustered") {
        // Bashful: gaze drops and slips sideways, occasionally darting back.
        const dartBack = Math.sin(t.current * 0.35) > 0.75;
        gazX = dartBack ? 0 : -0.055 + Math.sin(t.current * 0.4) * 0.012;
        gazY = dartBack ? 0.01 : -0.045 + Math.sin(t.current * 0.3) * 0.008;
      } else if (affectiveProfile.drowsy > 0.45) {
        // Heavy lids, drifting downward gaze.
        gazX = Math.sin(t.current * 0.22) * 0.02;
        gazY = -0.035 + Math.sin(t.current * 0.16 + 0.5) * 0.012;
      } else if (activeIntent === "determined" || affectiveProfile.scenarioArchetype === "determined_focus") {
        // Determined: eyes locked forward, saccades suppressed.
        gazX *= 0.25;
        gazY *= 0.25;
      }
      // Blink-linked gaze coordination: the eyes dip with the closing lids
      // and recover as they reopen — the micro-motion that sells a blink as
      // alive instead of a texture toggle.
      gazY -= blinkLevel.current * 0.045;
      gazX *= 1 - blinkLevel.current * 0.4;
      if (vrm.lookAt) {
        try {
          (vrm.lookAt as any).target = undefined;
          if ((vrm.lookAt as any).lookAt) {
            (vrm.lookAt as any).lookAt(scratch.gaze.set(gazX, gazY, 1));
          }
        } catch {}
      }
    }

    // Let VRM expression/spring-bone systems update first.
    vrm.update(dt);

    /* ── LAYER 4B: HIGH-LEVEL DIRECT FACE MESH ANIME ACTING ───────── */
    // Blink-recovery brow lift: when the lids reopen after a real blink, the
    // brows float up a touch and settle — the coupled micro-motion that makes
    // a blink read as muscular, not a texture toggle.
    const blinkNow = blinkLevel.current;
    if (prevBlinkLevel.current > 0.45 && blinkNow < 0.18) {
      browLift.current = Math.min(0.10, 0.045 + blinkShape.current.peak * 0.05);
    }
    prevBlinkLevel.current = blinkNow;
    browLift.current = THREE.MathUtils.damp(browLift.current, 0, 5.5, dt);

    const setDirectMorph = (targetName: string, targetWeight: number, rate = 14) => {
      const mesh = faceMeshRef.current;
      if (!mesh || !mesh.morphTargetInfluences) return;
      const idx = morphDictRef.current[targetName];
      if (idx === undefined) return;
      const cur = curDirectMorphsRef.current[targetName] ?? 0;
      const next = cur + (targetWeight - cur) * (1 - Math.exp(-dt * rate));
      curDirectMorphsRef.current[targetName] = next;
      mesh.morphTargetInfluences[idx] = THREE.MathUtils.clamp(next, 0, 1);
    };

    if (faceMeshRef.current) {
      const directTargets = computeDirectMorphTargets(
        affectiveProfile,
        t.current,
        isListening ? 0 : jawEnergy.current,
        isSpeakingNow,
      );
      for (const [targetName, targetWeight] of Object.entries(directTargets)) {
        const lift = (targetName === "Fcl_BRW_Surprised" || targetName === "Fcl_BRW_Joy")
          ? browLift.current * 0.5
          : 0;
        // Fcl_EYE_Close is shared between two owners: the blink layer drives it
        // through the blink presets (verified: the default model binds blink →
        // morph Fcl_EYE_Close), and this layer eases it toward the drowsy-lid
        // pose. A damped drowsy write of ~0 applied after vrm.update() stomped
        // the blink mid-flight every frame — she read as never blinking. Damp
        // the drowsy base only, then lay the live blink on top, instant and
        // undamped, so the lid follows the blink envelope exactly.
        if (targetName === "Fcl_EYE_Close") {
          setDirectMorph(targetName, Math.min(0.9, targetWeight));
          const mesh = faceMeshRef.current;
          const idx = morphDictRef.current[targetName];
          if (mesh && mesh.morphTargetInfluences && idx !== undefined) {
            const drowsyBase = curDirectMorphsRef.current[targetName] ?? 0;
            mesh.morphTargetInfluences[idx] = THREE.MathUtils.clamp(
              Math.max(drowsyBase, blinkLevel.current), 0, 1,
            );
          }
          continue;
        }
        setDirectMorph(targetName, Math.min(0.9, targetWeight + lift));
      }
    }

    /* ── PROCEDURAL GAIT DYNAMICS & CATWALK LOCOMOTION ───────────── */
    const walkWeightTarget = isWalking ? 1.0 : 0.0;
    walkWeightRef.current = THREE.MathUtils.damp(walkWeightRef.current, walkWeightTarget, 5, dt);
    const wWeight = walkWeightRef.current;

    // Advance walk cycle when active
    let armSwing = 0;
    let walkStride = 0;
    if (wWeight > 0.001) {
      walkPhaseRef.current = (walkPhaseRef.current + realDt * 3.6) % (Math.PI * 2);
      const phase = walkPhaseRef.current;
      walkStride = -Math.sin(phase) * wWeight;
      armSwing = walkStride * 0.40;

      // Roam laterally across floor / runway
      const roamStep = 0.12 * walkDirectionRef.current * realDt * wWeight;
      walkRoamXRef.current += roamStep;
      const maxRoam = 0.28;
      if (walkRoamXRef.current > maxRoam) {
        walkRoamXRef.current = maxRoam;
        walkDirectionRef.current = -1;
      } else if (walkRoamXRef.current < -maxRoam) {
        walkRoamXRef.current = -maxRoam;
        walkDirectionRef.current = 1;
      }
      const targetYaw = (walkDirectionRef.current > 0 ? 0.20 : -0.20) * wWeight;
      walkTurnYawRef.current = THREE.MathUtils.damp(walkTurnYawRef.current, targetYaw, 5, dt);

      // Apply root translation & turning yaw
      vrm.scene.position.x = walkRoamXRef.current * wWeight;
      vrm.scene.rotation.y = baseRotationY + (walkTurnYawRef.current * wWeight);

      // Pelvis / Hips dynamics (graceful runway lemniscate sway, vertical bob, forward pitch)
      const hipBob = Math.abs(Math.sin(phase)) * 0.018 * wWeight;
      const hipRoll = -Math.sin(phase) * 0.075 * wWeight;
      const hipYaw = Math.sin(phase) * 0.085 * wWeight;
      const hipPitch = 0.025 * wWeight;

      const hips = hipsBoneRef.current;
      const hipsPos = hipsRestPosRef.current;
      const hipsQ = hipsRestQRef.current;
      if (hips && hipsPos && hipsQ) {
        hips.position.y = THREE.MathUtils.damp(hips.position.y, hipsPos.y - hipBob, 12, dt);
        const targetHipsQ = scratch.target.copy(hipsQ).multiply(
          scratch.rotation.setFromEuler(scratch.euler.set(hipPitch, hipYaw, hipRoll)),
        );
        hips.quaternion.slerp(targetHipsQ, Math.min(1, dt * 14));
      }

      // Spine counter-rotation (stabilizes chest orientation)
      const spine = spineBoneRef.current;
      const spineQ = spineRestQRef.current;
      if (spine && spineQ) {
        const targetSpineQ = scratch.target.copy(spineQ).multiply(
          scratch.rotation.setFromEuler(scratch.euler.set(0.015 * wWeight, -hipYaw * 0.75, -hipRoll * 0.70)),
        );
        spine.quaternion.slerp(targetSpineQ, Math.min(1, dt * 14));
      }

      // Upper legs (Stride swing: negative X tilts thigh forward, positive X tilts thigh backward)
      const lul = leftUpperLegRef.current;
      const lulQ = leftUpperLegRestQRef.current;
      if (lul && lulQ) {
        const targetLulQ = scratch.target.copy(lulQ).multiply(
          scratch.rotation.setFromEuler(scratch.euler.set(-walkStride * 0.44, 0, -0.035 * wWeight)),
        );
        lul.quaternion.slerp(targetLulQ, Math.min(1, dt * 16));
      }
      const rul = rightUpperLegRef.current;
      const rulQ = rightUpperLegRestQRef.current;
      if (rul && rulQ) {
        const targetRulQ = scratch.target.copy(rulQ).multiply(
          scratch.rotation.setFromEuler(scratch.euler.set(walkStride * 0.44, 0, 0.035 * wWeight)),
        );
        rul.quaternion.slerp(targetRulQ, Math.min(1, dt * 16));
      }

      // Lower legs (High recovery swing flexion with smooth power curve to eliminate zero-crossing knee snap)
      const leftStrideFlex = Math.max(0, walkStride);
      const rightStrideFlex = Math.max(0, -walkStride);
      const leftKnee = Math.pow(leftStrideFlex, 1.35) * 1.05 * wWeight;
      const rightKnee = Math.pow(rightStrideFlex, 1.35) * 1.05 * wWeight;
      const lll = leftLowerLegRef.current;
      const lllQ = leftLowerLegRestQRef.current;
      if (lll && lllQ) {
        const targetLllQ = scratch.target.copy(lllQ).multiply(
          scratch.rotation.setFromEuler(scratch.euler.set(leftKnee, 0, 0)),
        );
        lll.quaternion.slerp(targetLllQ, Math.min(1, dt * 16));
      }
      const rll = rightLowerLegRef.current;
      const rllQ = rightLowerLegRestQRef.current;
      if (rll && rllQ) {
        const targetRllQ = scratch.target.copy(rllQ).multiply(
          scratch.rotation.setFromEuler(scratch.euler.set(rightKnee, 0, 0)),
        );
        rll.quaternion.slerp(targetRllQ, Math.min(1, dt * 16));
      }

      // 3-Phase Anatomical Foot Roll (heel strike dorsiflexion -> flat plant -> toe push-off)
      const leftFootPitch = walkStride > 0
        ? -Math.pow(walkStride, 1.3) * 0.22 * wWeight
        : Math.pow(-walkStride, 1.2) * 0.32 * wWeight;

      const rightFootPitch = -walkStride > 0
        ? -Math.pow(-walkStride, 1.3) * 0.22 * wWeight
        : Math.pow(walkStride, 1.2) * 0.32 * wWeight;

      const lf = leftFootRef.current;
      const lfq = leftFootRestQRef.current;
      if (lf && lfq) {
        const targetLfQ = scratch.target.copy(lfq).multiply(
          scratch.rotation.setFromEuler(scratch.euler.set(leftFootPitch, 0, 0)),
        );
        lf.quaternion.slerp(targetLfQ, Math.min(1, dt * 16));
      }
      const rf = rightFootRef.current;
      const rfq = rightFootRestQRef.current;
      if (rf && rfq) {
        const targetRfQ = scratch.target.copy(rfq).multiply(
          scratch.rotation.setFromEuler(scratch.euler.set(rightFootPitch, 0, 0)),
        );
        rf.quaternion.slerp(targetRfQ, Math.min(1, dt * 16));
      }

      // Synchronized footstep audio on floor contact
      if (walkStride > 0.38 && lastFootstepSideRef.current !== "left") {
        lastFootstepSideRef.current = "left";
        playFootstepSound();
      } else if (walkStride < -0.38 && lastFootstepSideRef.current !== "right") {
        lastFootstepSideRef.current = "right";
        playFootstepSound();
      }
    } else {
      // Return gracefully to neutral standing posture
      vrm.scene.position.x = THREE.MathUtils.damp(vrm.scene.position.x, 0, 6, dt);
      vrm.scene.rotation.y = THREE.MathUtils.damp(vrm.scene.rotation.y, baseRotationY, 6, dt);
      walkRoamXRef.current = THREE.MathUtils.damp(walkRoamXRef.current, 0, 6, dt);
      walkTurnYawRef.current = THREE.MathUtils.damp(walkTurnYawRef.current, 0, 6, dt);

      const hips = hipsBoneRef.current;
      const hipsPos = hipsRestPosRef.current;
      const hipsQ = hipsRestQRef.current;
      if (hips && hipsPos && hipsQ) {
        hips.position.y = THREE.MathUtils.damp(hips.position.y, hipsPos.y, 8, dt);
        hips.quaternion.slerp(hipsQ, Math.min(1, dt * 8));
      }
      const spine = spineBoneRef.current;
      const spineQ = spineRestQRef.current;
      if (spine && spineQ) spine.quaternion.slerp(spineQ, Math.min(1, dt * 8));

      // Natural respiration on chest (~17 breaths/min)
      const chest = chestBoneRef.current;
      const chestQ = chestRestQRef.current;
      if (chest && chestQ) {
        const breathPitch = Math.sin(t.current * 1.75) * 0.012;
        const breathRoll = Math.sin(t.current * 0.85) * 0.006;
        const targetChestQ = scratch.target.copy(chestQ).multiply(
          scratch.rotation.setFromEuler(scratch.euler.set(breathPitch, 0, breathRoll)),
        );
        chest.quaternion.slerp(targetChestQ, Math.min(1, dt * 6));
      }

      const lul = leftUpperLegRef.current;
      const lulQ = leftUpperLegRestQRef.current;
      if (lul && lulQ) lul.quaternion.slerp(lulQ, Math.min(1, dt * 10));
      const rul = rightUpperLegRef.current;
      const rulQ = rightUpperLegRestQRef.current;
      if (rul && rulQ) rul.quaternion.slerp(rulQ, Math.min(1, dt * 10));
      const lll = leftLowerLegRef.current;
      const lllQ = leftLowerLegRestQRef.current;
      if (lll && lllQ) lll.quaternion.slerp(lllQ, Math.min(1, dt * 10));
      const rll = rightLowerLegRef.current;
      const rllQ = rightLowerLegRestQRef.current;
      if (rll && rllQ) rll.quaternion.slerp(rllQ, Math.min(1, dt * 10));
      const lf = leftFootRef.current;
      const lfq = leftFootRestQRef.current;
      if (lf && lfq) lf.quaternion.slerp(lfq, Math.min(1, dt * 10));
      const rf = rightFootRef.current;
      const rfq = rightFootRestQRef.current;
      if (rf && rfq) rf.quaternion.slerp(rfq, Math.min(1, dt * 10));
    }

    /* ── CALIBRATED HEAD-ONLY VMC & AUDIO-REACTIVE HEAD LIFE ──────── */
    const head = headBoneRef.current;
    const headRest = headRestQRef.current;
    const headCurrent = headCurQRef.current;
    const rawHead = faceTrackingActive ? faceBones?.Head : undefined;
    const baseline = trackingCalibration?.headBaseline;
    if (head && headRest && headCurrent && rawHead && baseline) {
      const raw = scratch.raw.set(rawHead[0], rawHead[1], rawHead[2], rawHead[3]).normalize();
      const neutral = scratch.neutral.set(baseline[0], baseline[1], baseline[2], baseline[3]).normalize();
      const delta = neutral.invert().multiply(raw);
      const maxAngle = THREE.MathUtils.degToRad(22);
      if (2 * Math.acos(THREE.MathUtils.clamp(delta.w, -1, 1)) > maxAngle) {
        delta.slerp(scratch.identity, 1 - maxAngle / (2 * Math.acos(THREE.MathUtils.clamp(delta.w, -1, 1))));
      }
      const targetHead = scratch.target.copy(headRest).multiply(delta);
      headCurrent.slerp(targetHead, Math.min(1, 1 - Math.exp(-dt * 9)));
      head.quaternion.copy(headCurrent);
    } else if (head && headRest && headCurrent) {
      // Audio-reactive speech nodding + scenario head life + living idle dynamics
      const speechNod = isSpeakingNow
        ? (affectiveProfile.scenarioArchetype === "casual_bro"
            ? (Math.sin(t.current * 3.8) * 0.038 + (jawEnergy.current > 0.38 ? 0.022 : 0))
            : Math.sin(t.current * 4.2) * Math.min(0.06, jawEnergy.current * 0.12))
        : 0;

      // Living idle companion micro-movement (never frozen or rigid)
      const idlePitch = !isSpeakingNow ? Math.sin(t.current * 0.44 + 0.5) * 0.016 : 0;
      const idleYaw = !isSpeakingNow ? (Math.sin(t.current * 0.31) * 0.022 + Math.sin(t.current * 0.13 + 1.2) * 0.012) : 0;
      const idleRoll = !isSpeakingNow ? Math.sin(t.current * 0.27 + 2.1) * 0.018 : 0;

      const affectiveTilt = isSpeakingNow
        ? (affectiveProfile.headTiltBias + (activeIntent === "curious" ? 0.07 : 0))
        : (affectiveProfile.headTiltBias * 0.4);
      const thinkingPitch = (affectiveProfile.thoughtfulness > 0.5 || activeIntent === "thinking") ? 0.045 : 0;
      const laughingPitch = (activeIntent === "laughing") ? -0.05 + Math.sin(t.current * 7.2) * 0.03 : 0;
      const walkGazeStabilizeYaw = -walkTurnYawRef.current * wWeight;
      const swayTarget = scratch.target.copy(headRest).multiply(
        scratch.rotation.setFromEuler(scratch.euler.set(
          motionPose.pitch + speechNod + thinkingPitch + laughingPitch + idlePitch,
          motionPose.yaw + walkGazeStabilizeYaw + idleYaw,
          motionPose.roll + affectiveTilt + idleRoll
        )),
      );
      headCurrent.slerp(swayTarget, Math.min(1, 1 - Math.exp(-dt * 4.8)));
      head.quaternion.copy(headCurrent);
    }

    /* ── RELAXED POSE / FACE TRACKING POSE / ARM LOCOMOTION ───────── */
    const alpha = t.current < 0.1 ? 1.0 : Math.min(1, dt * 9);
    const nb = normBonesRef.current;
    const cq = curQRef.current;

    const convo = convoEnergyRef.current;

    /* ── LAYER 5B: EMOTION-DRIVEN BODY LANGUAGE ────────────────────────
     * The face speaks the intent; the body must agree. Continuous affective
     * dims sculpt the conversational cadence (arousal quickens and enlarges
     * it, drowsiness slows and droops it, sorrow weighs it down), and
     * discrete intents layer signature poses on the arms and hands. */
    const bodyGain = (1 + affectiveProfile.arousal * 0.35) * (1 - affectiveProfile.drowsy * 0.55);
    const bodyConvo = convo * bodyGain;
    const bodyDroop = affectiveProfile.drowsy * 0.09 + Math.max(0, -affectiveProfile.valence) * 0.07;
    const bodyArchetype = affectiveProfile.scenarioArchetype;
    const shyPose = activeIntent === "shy" || bodyArchetype === "shy_flustered";
    const heavyPose = activeIntent === "sad" || activeIntent === "sleepy"
      || bodyArchetype === "melancholy_soft" || bodyArchetype === "serene_cozy";
    const excitedPose = activeIntent === "excited" || activeIntent === "awe";
    const firmPose = activeIntent === "determined" || bodyArchetype === "determined_focus";
    const fidgetPose = activeIntent === "nervous" || bodyArchetype === "nervous_awkward";

    for (const boneName of POSE_BONES) {
      const bone = nb[boneName];
      const cur  = cq[boneName];
      if (!bone || !cur) continue;

      const targetQ = poseTargetRef.current[boneName];
      if (!targetQ) continue;
      const isLeft = boneName.startsWith("left");
      const side = isLeft ? 1 : -1;

      let rotX = 0, rotY = 0, rotZ = 0;

      if (boneName.includes("UpperArm")) {
        if (activeIntent === "thinking" && !isLeft) {
          rotX = 0.18;
          rotY = -0.32;
          rotZ = 0.15;
        } else if ((activeIntent === "celebratory" || activeIntent === "laughing") && convo > 0.2) {
          const bounce = Math.sin(t.current * 5.0) * 0.08;
          rotX = 0.15 + bounce;
          rotY = -side * (0.22 + bounce * 0.5);
          rotZ = -side * 0.12;
        } else if (shyPose) {
          // Self-conscious: arms hugged close, drifting gently inward.
          const sway = Math.sin(t.current * 1.1) * 0.02;
          rotX = 0.05 + sway;
          rotY = -side * (0.26 + sway);
          rotZ = -side * 0.02;
        } else if (heavyPose) {
          // Sad or sleepy: arms hang heavy with a slow, tired drift.
          const heavy = Math.sin(t.current * 0.8) * 0.015;
          rotX = -(0.04 + bodyDroop) + heavy;
          rotY = -side * 0.05;
          rotZ = -side * (0.03 + bodyDroop * 0.4);
        } else if (excitedPose) {
          // Bright, bouncy energy — faster and higher than celebration.
          const bounce = Math.sin(t.current * 6.5) * 0.10;
          rotX = 0.10 + bounce;
          rotY = -side * (0.16 + bounce * 0.4);
          rotZ = -side * (0.10 + Math.abs(bounce) * 0.5);
        } else if (firmPose) {
          // Determined: steady, planted, no cadence wobble.
          rotX = 0.10;
          rotY = -side * 0.08;
          rotZ = -side * 0.05;
        } else if (fidgetPose) {
          // Nervous: small, fast fidgeting under the conversation.
          const fidget = Math.sin(t.current * 9.0) * 0.02;
          rotX = convo * 0.06 + fidget;
          rotY = -side * (convo * 0.12 + fidget);
          rotZ = -side * convo * 0.05;
        } else {
          // Dynamic conversational upper arm gesture with vocal cadence,
          // sculpted by affect: arousal adds flutter, drowsiness droops.
          const cadence = isLeft ? Math.sin(t.current * 1.7) : Math.sin(t.current * 2.1);
          const flutter = Math.sin(t.current * (isLeft ? 5.3 : 6.1)) * affectiveProfile.arousal * 0.35;
          rotX = bodyConvo * 0.08 * (0.8 + 0.3 * cadence + flutter) - bodyDroop;
          rotY = -side * bodyConvo * (isLeft ? 0.14 : 0.22) * (0.8 + 0.3 * cadence);
          rotZ = -side * bodyConvo * (isLeft ? 0.06 : 0.10);
        }

        if (wWeight > 0.001) {
          const walkArmSwing = (isLeft ? walkStride : -walkStride) * 0.38;
          rotY = THREE.MathUtils.lerp(rotY, walkArmSwing, wWeight * 0.88);
        }
      } else if (boneName.includes("LowerArm")) {
        if (activeIntent === "thinking" && !isLeft) {
          rotX = 0.25;
          rotY = -0.12;
          rotZ = -0.72; // strong thoughtful flexion towards chin
        } else if ((activeIntent === "celebratory" || activeIntent === "laughing") && convo > 0.2) {
          const bounce = Math.sin(t.current * 5.0) * 0.10;
          rotX = 0.20 + bounce;
          rotZ = side * (0.48 + bounce);
        } else if (shyPose) {
          // Forearms drawn up in front of the body, hands near the waist.
          const sway = Math.sin(t.current * 1.1 + 0.4) * 0.02;
          rotX = 0.06 + sway;
          rotZ = side * (0.52 + sway);
        } else if (heavyPose) {
          // Limbs go slack; elbows barely hold any bend.
          const heavy = Math.sin(t.current * 0.8 + 0.3) * 0.012;
          rotX = -(bodyDroop * 0.5) + heavy;
          rotZ = side * Math.max(0.06, 0.18 - bodyDroop);
        } else if (excitedPose) {
          const bounce = Math.sin(t.current * 6.5 + 0.3) * 0.12;
          rotX = 0.14 + bounce;
          rotZ = side * (0.40 + Math.abs(bounce));
        } else if (firmPose) {
          rotX = 0.08;
          rotZ = side * 0.30;
        } else if (fidgetPose) {
          const fidget = Math.sin(t.current * 9.0 + 0.5) * 0.03;
          rotX = convo * 0.12 + fidget;
          rotZ = side * (convo * 0.30 + fidget);
        } else {
          const cadence = isLeft ? Math.sin(t.current * 1.7 + 0.5) : Math.sin(t.current * 2.1 + 0.4);
          rotX = bodyConvo * 0.16 * (0.8 + 0.25 * cadence) - bodyDroop * 0.5;
          rotZ = side * bodyConvo * (isLeft ? 0.28 : 0.42) * (0.85 + 0.25 * cadence) * (1 - affectiveProfile.drowsy * 0.4);
        }

        if (wWeight > 0.001) {
          const phaseLagElbow = (walkPhaseRef.current - 0.35) % (Math.PI * 2);
          const elbowSwing = -Math.sin(phaseLagElbow) * wWeight;
          const walkElbowFlex = isLeft
            ? (Math.max(0, elbowSwing) * 0.32 + 0.10 * wWeight)
            : (Math.max(0, -elbowSwing) * 0.32 + 0.10 * wWeight);
          rotY = THREE.MathUtils.lerp(rotY, isLeft ? -walkElbowFlex : walkElbowFlex, wWeight * 0.85);
        }
      } else if (boneName.includes("Hand")) {
        if (activeIntent === "thinking" && !isLeft) {
          rotX = 0.22;
          rotZ = -0.15;
        } else if ((activeIntent === "celebratory" || activeIntent === "laughing") && convo > 0.2) {
          const bounce = Math.sin(t.current * 5.0) * 0.12;
          rotX = bounce;
          rotZ = side * 0.15;
        } else if (shyPose) {
          const sway = Math.sin(t.current * 1.1 + 0.8) * 0.015;
          rotX = 0.10 + sway;
          rotZ = -side * 0.06;
        } else if (heavyPose) {
          rotX = -(0.05 + bodyDroop);
          rotZ = -side * 0.03;
        } else if (excitedPose) {
          const bounce = Math.sin(t.current * 6.5 + 0.6) * 0.12;
          rotX = bounce;
          rotZ = side * 0.18;
        } else if (firmPose) {
          rotX = 0.06;
          rotZ = -side * 0.05;
        } else if (fidgetPose) {
          const fidget = Math.sin(t.current * 9.0 + 0.7) * 0.03;
          rotX = convo * 0.12 + fidget;
          rotZ = -side * fidget * 0.5;
        } else {
          const cadence = isLeft ? Math.sin(t.current * 1.7 + 1.0) : Math.sin(t.current * 2.1 + 0.8);
          rotX = bodyConvo * (isLeft ? 0.10 : 0.18) * cadence;
          rotZ = -side * bodyConvo * (isLeft ? 0.07 : 0.14) * (isLeft ? Math.cos(t.current * 1.7) : Math.cos(t.current * 2.1 + 0.4));
          rotY = side * bodyConvo * (isLeft ? 0.05 : 0.12) * cadence;
        }

        if (wWeight > 0.001) {
          const phaseLagWrist = (walkPhaseRef.current - 0.70) % (Math.PI * 2);
          const wristSwing = -Math.sin(phaseLagWrist) * wWeight * 0.15;
          rotY = THREE.MathUtils.lerp(rotY, isLeft ? wristSwing : -wristSwing, wWeight * 0.85);
        }
      }

      const animatedTarget = scratch.target.copy(targetQ).multiply(
        scratch.rotation.setFromEuler(scratch.euler.set(rotX, rotY, rotZ)),
      );
      cur.slerp(animatedTarget, alpha);

      bone.quaternion.copy(cur);
    }

    /* ── LAYER 6B: FULL ANATOMICAL FINGER KINEMATICS (30 PHALANGES) ─── */
    const fb = fingerBonesRef.current;
    const fr = fingerRestQRef.current;
    for (const fName of ALL_FINGER_BONES) {
      const fNode = fb[fName];
      const fRest = fr[fName];
      if (!fNode || !fRest) continue;

      const isLeft = fName.startsWith("left");
      const sign = isLeft ? 1 : -1;
      const isThumb = fName.includes("Thumb");
      const isIndex = fName.includes("Index");
      const isMiddle = fName.includes("Middle");
      const isRing = fName.includes("Ring");
      const isLittle = fName.includes("Little");

      const isProximal = fName.endsWith("Proximal") || fName.endsWith("Metacarpal");
      const isIntermediate = fName.endsWith("Intermediate");
      const isDistal = fName.endsWith("Distal");

      const jointMult = isProximal ? 0.38 : isIntermediate ? 0.42 : 0.20;
      const baseCurl = isIndex ? 0.22 : isMiddle ? 0.28 : isRing ? 0.34 : isLittle ? 0.40 : 0.18;

      const openModifier = convo * (isLeft ? 0.08 : 0.14) * Math.max(0, Math.sin(t.current * 2.0));
      const phase = isIndex ? 0.3 : isMiddle ? 0.7 : isRing ? 1.1 : isLittle ? 1.5 : 0.1;
      const microFlutter = Math.sin(t.current * 2.1 + phase) * 0.022 + Math.sin(t.current * 0.8 + phase * 2) * 0.015;

      let fRotX = 0, fRotY = 0, fRotZ = 0;
      if (isThumb) {
        const thumbCurl = Math.max(0.05, Math.min(0.8, (baseCurl - openModifier * 0.5 + microFlutter) * jointMult));
        fRotX = -thumbCurl * 0.6;
        fRotY = -sign * thumbCurl * 0.8;
        fRotZ = sign * thumbCurl * 0.3;
      } else {
        let intentCurlDelta = 0;
        if (activeIntent === "thinking" && !isLeft) {
          intentCurlDelta = 0.12;
        } else if (activeIntent === "celebratory" || activeIntent === "laughing") {
          intentCurlDelta = -0.15;
        } else if (shyPose || fidgetPose) {
          // Fingers softly curl inward when bashful or uneasy.
          intentCurlDelta = 0.10;
        } else if (heavyPose) {
          // Sleepy/sorrowful hands go loose and open.
          intentCurlDelta = -0.10;
        } else if (excitedPose) {
          intentCurlDelta = -0.08;
        } else if (firmPose) {
          intentCurlDelta = 0.08;
        }
        const totalCurl = Math.max(0.04, Math.min(1.2, (baseCurl - openModifier + intentCurlDelta + microFlutter) * jointMult));
        fRotZ = sign * totalCurl;
        if (isIndex) fRotY = sign * (0.04 + openModifier * 0.06);
        else if (isLittle) fRotY = -sign * (0.05 + openModifier * 0.08);
      }

      scratch.rotation.setFromEuler(scratch.euler.set(fRotX, fRotY, fRotZ));
      const targetFingerQ = scratch.target.copy(fRest).multiply(scratch.rotation);
      fNode.quaternion.slerp(targetFingerQ, Math.min(1, dt * 20));
    }

    // Physical jaw fallback
    const jawBone = jawBoneRef.current;
    if (jawBone) {
      let mouthDrive = 0;
      if (!isListening) {
        for (const k of ALL_MOUTH_KEYS) mouthDrive = Math.max(mouthDrive, mouthW.current[k]);
      }
      jawBone.rotation.x = THREE.MathUtils.damp(jawBone.rotation.x, -mouthDrive * 0.42, 16, dt);
    }

    /* ── IDLE / ALWAYS-ON BREATHING ─────────────────────────────────
     * Breath follows feeling: arousal quickens and deepens it, drowsiness
     * slows it into long, heavy draws, sorrow adds weight. */
    const chestBone = chestBoneRef.current;
    const chestRest = chestRestQRef.current;
    if (chestBone && chestRest) {
      const breathRate = 1.5 + affectiveProfile.arousal * 0.9 - affectiveProfile.drowsy * 0.7;
      const depth = (speakingRef.current ? 0.030 : 0.024)
        * (1 + affectiveProfile.arousal * 0.4 + Math.max(0, -affectiveProfile.valence) * 0.15);
      const breathe = Math.sin(t.current * breathRate) * depth;
      const drift = Math.sin(t.current * 0.6 + 1.0) * 0.006;
      chestBone.quaternion.copy(
        scratch.target.copy(chestRest).multiply(
          scratch.rotation.setFromEuler(scratch.euler.set(-(breathe + drift), 0, 0)),
        ),
      );
    }
  });


  if (failed || !loaded) return null;
  return <primitive object={vrmRef.current!.scene} />;
}

/* ─── Camera controller (Hexfield AI Dynamic Framing & Handheld Float) ─── */
const camScratchPos = new THREE.Vector3();
const camScratchTarget = new THREE.Vector3();
const camFinalPos = new THREE.Vector3();
const camFinalTarget = new THREE.Vector3();

const CUTE_AFFECTION_RE = /(cute|maya|smile|happy|love|sweet|hug|darling|blush|charming|heart|laugh|joy)/i;

interface CamProps {
  mode: PresenceMode;
  modelUrl: string;
  anatomy?: AnatomyFrame;
  isWalking?: boolean;
  state?: CompanionState;
  speakingRef?: React.MutableRefObject<boolean>;
  expressionText?: string;
  plan?: AssistantTurnPlan;
  liveStatus?: FullscreenLiveStatus;
}

function Cam({
  mode,
  modelUrl,
  anatomy,
  isWalking,
  state,
  speakingRef,
  expressionText,
  plan,
  liveStatus,
}: CamProps) {
  const effectiveMode: PresenceMode = isWalking ? "full" : mode;
  const fallback = MODEL_CAMERA_PRESETS[modelUrl]?.[effectiveMode] ?? CAMERAS[effectiveMode] ?? CAMERAS.portrait;
  const camera = useThree(s => s.camera);
  const viewportWidth = useThree(s => s.size.width);
  const compactViewport = viewportWidth <= 768;
  const cfg = cameraFromAnatomy(effectiveMode, fallback, anatomy, compactViewport);
  const curPos = useRef(new THREE.Vector3(...cfg.pos));
  const curTarget = useRef(new THREE.Vector3(...cfg.target));
  const initialized = useRef(false);
  const camClock = useRef(0);
  const speechDampRef = useRef(0);

  // Detect emotional warmth or cute emphasis for intimate cinematic framing
  const dialogueSample = `${expressionText || ""} ${plan?.spokenText || ""} ${plan?.displayText?.slice(0, 120) || ""}`;
  const isCuteOrAffectionate = CUTE_AFFECTION_RE.test(dialogueSample);

  useFrame((_, dt) => {
    const persCam = camera as THREE.PerspectiveCamera;
    const realDt = Math.min(dt, 0.1);
    camClock.current += realDt;

    const isListening = state === "listening" || (liveStatus?.active && liveStatus?.status === "listening");
    const isSpeakingNow = !isListening && Boolean((speakingRef && speakingRef.current) || state === "speaking");
    const targetSpeechFactor = isSpeakingNow ? 1.0 : 0.0;
    speechDampRef.current = THREE.MathUtils.damp(speechDampRef.current, targetSpeechFactor, 3.2, realDt);
    const speechFactor = speechDampRef.current;

    if (!initialized.current) {
      curPos.current.set(...cfg.pos);
      curTarget.current.set(...cfg.target);
      persCam.position.copy(curPos.current);
      persCam.fov = cfg.fov;
      persCam.updateProjectionMatrix();
      initialized.current = true;
    } else {
      const alpha = Math.min(1, realDt * 4.8);
      curPos.current.lerp(camScratchPos.set(...cfg.pos), alpha);
      curTarget.current.lerp(camScratchTarget.set(...cfg.target), alpha);
    }

    // Hexfield AI Dynamic Camera Framing:
    // 1. Organic handheld breathing float (frequencies 0.72 Hz, 0.54 Hz, 1.18 Hz with 3–6mm amplitude)
    const floatX = Math.sin(camClock.current * 0.72) * 0.0045 + Math.sin(camClock.current * 1.31) * 0.0020;
    const floatY = Math.cos(camClock.current * 0.54) * 0.0055 + Math.sin(camClock.current * 1.18) * 0.0022;
    const floatZ = Math.sin(camClock.current * 0.41) * 0.0035;

    // 2. Subtle multi-angle cinematic orbit pan (±2.5° azimuth shift while speaking)
    const orbitAngle = Math.sin(camClock.current * 0.22) * 0.042 * speechFactor;

    // Relative displacement from target
    const tx = curTarget.current.x;
    const ty = curTarget.current.y;
    const tz = curTarget.current.z;

    const dx = curPos.current.x - tx;
    const dy = curPos.current.y - ty;
    const dz = curPos.current.z - tz;

    // Rotate horizontal azimuth around target
    const cosO = Math.cos(orbitAngle);
    const sinO = Math.sin(orbitAngle);
    const rx = dx * cosO + dz * sinO;
    const rz = -dx * sinO + dz * cosO;

    // 3. Dynamic face push-in dolly for conversational warmth & cute emphasis
    const baseDist = Math.hypot(rx, dy, rz);
    const dollyOffset = (isCuteOrAffectionate ? 0.13 : 0.09) * speechFactor;
    const dollyFactor = baseDist > 0.3 ? Math.max(0.65, (baseDist - dollyOffset) / baseDist) : 1.0;

    camFinalPos.set(
      tx + rx * dollyFactor + floatX,
      ty + dy * dollyFactor + floatY,
      tz + rz * dollyFactor + floatZ,
    );

    camFinalTarget.set(
      tx,
      ty + floatY * 0.4,
      tz,
    );

    persCam.position.copy(camFinalPos);
    persCam.lookAt(camFinalTarget);

    // Dynamic FOV punch during dialogue
    const targetFov = cfg.fov - (isCuteOrAffectionate ? 3.2 : 2.0) * speechFactor;
    if (Math.abs(persCam.fov - targetFov) > 0.02) {
      persCam.fov = THREE.MathUtils.damp(persCam.fov, targetFov, 4.5, realDt);
      persCam.updateProjectionMatrix();
    }
  });
  return null;
}

/* ─── Fallback ────────────────────────────────────────────── */
function AvatarFallback({ state }: { state: CompanionState }) {
  return (
    <div style={{ width:"100%", height:"100%", display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", gap:12, color:"#cdbbc5" }}>
      <div style={{ width:72, height:72, borderRadius:"50%", background:"linear-gradient(135deg,rgba(255,214,225,.72),rgba(238,145,173,.6))", display:"flex", alignItems:"center", justifyContent:"center", fontSize:"1.8rem", color:"#331722", border:"1px solid rgba(255,220,232,.48)" }}>◇</div>
      <div style={{ fontWeight:700, color:"#fff2f6", fontSize:"0.85rem" }}>HINAA — {state}</div>
    </div>
  );
}

/* ─── AvatarPresence (main export) ──────────────────────── */
interface Props {
  mode: PresenceMode;
  state: CompanionState;
  jawEnergy?: React.MutableRefObject<number>;
  speakingRef?: React.MutableRefObject<boolean>;
  visemeEvents?: React.MutableRefObject<VisemeEvent[]>;
  audioStartTimeRef?: React.MutableRefObject<number>;
  modelUrl?: string;
  onModeChange?: (m: PresenceMode) => void;
  faceExpressions?: FaceExpressions | null;
  faceBones?: Record<string, [number, number, number, number]> | null;
  faceTrackingActive?: boolean;
  trackingCalibration?: {
    headBaseline?: [number, number, number, number];
    expressionBaseline?: Partial<FaceExpressions>;
  } | null;
  expressionText?: string;
  presentation?: AvatarPresentation;
  companionName?: string;
  liveStatus?: FullscreenLiveStatus;
  messages?: TranscriptMessage[];
  partialTranscript?: string;
  streamingText?: string;
  onStartLive?: () => void;
  onStopLive?: () => void;
  onPauseLive?: () => void;
  onResumeLive?: () => void;
  isWalking?: boolean;
  onToggleWalk?: () => void;
  plan?: AssistantTurnPlan;
}


/* ─── Live-voice veil: listening feedback + honest reconnect state ─── */
function VoiceVeil({ live, onReconnect, overlayActive = false }: { live: FullscreenLiveStatus; onReconnect: () => void; overlayActive?: boolean }) {
  const status = live.status ?? "idle";
  const faulty = status === "reconnecting" || status === "error";
  // The fullscreen overlay already carries this state and its own level meter,
  // and the two are both bottom-centred, so the pill only stays for the states
  // the overlay cannot act on.
  const show = faulty || (live.active && !overlayActive);
  const level = Math.max(0, Math.min(1, live.microphoneLevel));
  const bars = [0.55, 0.85, 1, 0.8, 0.5];
  const label = status === "reconnecting" ? "Reconnecting — Hinaa keeps listening soon"
    : status === "error" ? "Voice link dropped"
    : live.paused ? "Mic paused"
    : "Listening";
  return (
    <AnimatePresence>
      {show && (
        <motion.div
          className={`hinaa-voice-veil ${status === "error" ? "hinaa-voice-veil--error" : ""}`}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 6 }}
          transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
          aria-live="polite"
        >
          <span className="hinaa-voice-veil__dot" aria-hidden="true" />
          <span className="hinaa-voice-veil__label">{label}</span>
          <span className="hinaa-voice-veil__meter" aria-hidden="true">
            {bars.map((m, i) => (
              <i key={i} style={{ transform: `scaleY(${0.18 + (live.paused || status !== "listening" ? 0.12 : level * m) * 0.9})` }} />
            ))}
          </span>
          {(status === "error" || status === "reconnecting") && (
            <button type="button" className="hinaa-voice-veil__retry" onClick={onReconnect}>
              {status === "error" ? "Reconnect now" : "Retry now"}
            </button>
          )}
          {live.detail && (status === "error" || status === "reconnecting") && (
            <small>{live.detail}</small>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// Stable fallback refs so we never create new objects in render
const _emptyVisemes: VisemeEvent[] = [];
const _falseRef = { current: false };
const _zeroRef  = { current: 0 };
const _emptyRef = { current: _emptyVisemes };
const _startRef = { current: 0 };

function AdaptiveAvatarResolution() {
  const { setDpr } = useThree();
  const samples = useRef({elapsed:0,frames:0,reduced:false});
  useFrame((_, delta) => {
    const budget=samples.current;
    if (budget.reduced || delta > 0.25) return;
    budget.elapsed += delta;
    budget.frames += 1;
    if (budget.frames >= 90) {
      if (budget.elapsed / budget.frames > 1/35) {setDpr(1);budget.reduced=true;}
      budget.elapsed=0;budget.frames=0;
    }
  });
  return null;
}

export function AvatarPresence({
  mode, state, jawEnergy, speakingRef, visemeEvents, audioStartTimeRef,
  modelUrl, onModeChange, faceExpressions, faceBones, faceTrackingActive, trackingCalibration, expressionText, presentation,
  companionName = "HINAA", liveStatus, messages = [], partialTranscript, streamingText,
  onStartLive, onStopLive, onPauseLive, onResumeLive,
  isWalking = false, onToggleWalk, plan,
}: Props) {
  const [webglFailed, setWebglFailed] = useState(false);
  const [modelLoadState, setModelLoadState] = useState<"loading" | "ready" | "failed">("loading");
  const [modelAttempt, setModelAttempt] = useState(0);
  const [anatomy, setAnatomy] = useState<AnatomyFrame | undefined>();
  const [isFullscreen, setIsFullscreen] = useState(false);
  const nativeFullscreenRef = useRef(false);
  const playgroundRef = useRef<HTMLDivElement>(null);
  const [renderVisible, setRenderVisible] = useState(true);
  useEffect(() => {
    let intersecting=true;
    const update=() => setRenderVisible(intersecting && !document.hidden);
    const observer=typeof IntersectionObserver === "undefined" ? null : new IntersectionObserver(entries=>{
      intersecting=entries[0]?.isIntersecting ?? true;update();
    });
    if (playgroundRef.current) observer?.observe(playgroundRef.current);
    document.addEventListener("visibilitychange",update);update();
    return () => {observer?.disconnect();document.removeEventListener("visibilitychange",update);};
  }, [mode]);
  const applyAnatomy = useCallback((frame: AnatomyFrame) => setAnatomy(frame), []);

  useEffect(() => {
    const onFullscreenChange = () => {
      const nativeActive = document.fullscreenElement === playgroundRef.current;
      // Escape exits native fullscreen but must not dismiss the deliberate
      // in-page theater fallback unless that native request was actually active.
      if (nativeFullscreenRef.current && !nativeActive) setIsFullscreen(false);
      nativeFullscreenRef.current = nativeActive;
      if (nativeActive) setIsFullscreen(true);
    };
    document.addEventListener("fullscreenchange", onFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", onFullscreenChange);
  }, []);

  const toggleFullscreen = () => {
    if (!playgroundRef.current) return;
    if (isFullscreen) {
      if (nativeFullscreenRef.current && document.fullscreenElement === playgroundRef.current) {
        void document.exitFullscreen();
      } else {
        setIsFullscreen(false);
      }
      return;
    }

    // Theater mode is immediate and fully usable even if a browser policy,
    // embedding context, or automated shell rejects the native API.
    setIsFullscreen(true);
    const request = playgroundRef.current.requestFullscreen?.();
    if (request) {
      void request.then(
        () => { nativeFullscreenRef.current = document.fullscreenElement === playgroundRef.current; },
        () => { nativeFullscreenRef.current = false; },
      );
    }
  };

  // Reset on model change
  useEffect(() => { setWebglFailed(false); setAnatomy(undefined); setModelLoadState("loading"); }, [modelUrl]);



  if (mode === "hidden") return null;

  const cycle = () => {
    const modes: PresenceMode[] = ["portrait", "closeup", "upperbody", "full"];
    onModeChange?.(modes[(modes.indexOf(mode) + 1) % modes.length]);
  };

  const jaw    = jawEnergy      ?? _zeroRef  as React.MutableRefObject<number>;
  const spkRef = speakingRef    ?? _falseRef as React.MutableRefObject<boolean>;
  const vEvts  = visemeEvents   ?? _emptyRef as React.MutableRefObject<VisemeEvent[]>;
  const aStart = audioStartTimeRef ?? _startRef as React.MutableRefObject<number>;

  return (
    <div ref={playgroundRef} className={`avatar-playground${isFullscreen ? " avatar-playground--fullscreen" : ""}`} style={{ position:"relative", width:"100%", height:"100%", minHeight:200 }}>
      {/* Atmospheric glow */}
      <div style={{ position:"absolute", inset:0, background:"radial-gradient(ellipse 70% 55% at 50% 35%, rgba(238,145,173,.14) 0%, transparent 70%)", pointerEvents:"none", zIndex:0 }} />

      {modelUrl && !webglFailed && (
        <Canvas
          key={`${modelUrl}:${modelAttempt}`}
          fallback={<AvatarFallback state={state} />}
          style={{ position:"absolute", inset:0, zIndex:1 }}
          // Above 1.5× device pixel ratio, the VRM’s animated face and lip-sync
          // cost rises sharply with little visible benefit at this panel size.
          // Let R3F temporarily reduce quality under load instead of stuttering.
          frameloop={renderVisible ? "always" : "demand"}
          dpr={[1, window.innerWidth <= 768 ? 1 : Math.min(window.devicePixelRatio, 1.35)]}
          performance={{ min: 0.62, debounce: 220 }}
          gl={{ antialias:true, alpha:true, powerPreference:"high-performance" }}
          onCreated={({ gl }) => {
            gl.domElement.addEventListener("webglcontextlost", e => {
              e.preventDefault();
              setWebglFailed(true);
            }, { once:true });
          }}
        >
          <AdaptiveAvatarResolution />
          <Suspense fallback={null}>
            <Cam
              mode={mode}
              modelUrl={modelUrl}
              anatomy={anatomy}
              isWalking={isWalking}
              state={state}
              speakingRef={spkRef}
              expressionText={expressionText}
              plan={plan}
              liveStatus={liveStatus}
            />

            {/* Cinematic lighting */}
            <ambientLight intensity={0.9}  color="#fffef8" />
            <directionalLight position={[1.5, 3, 2.5]} intensity={1.5} color="#fffcf0" castShadow={false} />
            <spotLight position={[-2.5, 2.5, 2]} intensity={1.15} color="#ffd4df" angle={0.55} penumbra={0.7} />
            <spotLight position={[ 2.5, 2.0,-1]} intensity={.82} color="#d8b8e4" angle={0.5}  penumbra={0.7} />
            <pointLight position={[0, 1.6, 2.2]} intensity={0.55} color="#fff5e8" />

              <Model
                state={state}
                jawEnergy={jaw}
                speakingRef={spkRef}
                visemeEvents={vEvts}
                audioStartTimeRef={aStart}
                url={modelUrl}
                presentation={presentation ?? defaultAvatarPresentation(modelUrl || "/models/hinaa-original.vrm")}
                faceExpressions={faceExpressions}
                faceBones={faceBones}
                faceTrackingActive={faceTrackingActive}
                trackingCalibration={trackingCalibration}
                expressionText={expressionText}
                onAnatomyFrame={applyAnatomy}
                onLoadState={setModelLoadState}
                isWalking={isWalking}
                plan={plan}
                liveStatus={liveStatus}
              />

            {/* ContactShadows re-renders the scene every frame by default
                (frames=Infinity). Baking once at mount costs a fraction and
                removes a full shadow pass from the frame loop. */}
            <ContactShadows
              resolution={128} scale={2.8} blur={2.5}
              opacity={0.12} far={1.5} frames={1}
              position={[0, -0.02, 0]} color="#8B6080"
            />
            {/* `Environment preset="apartment"` fetched an HDR from the
                network at runtime every session (PMREM + download stall).
                Replaced with a cheap procedural environment baked once; the
                four lights above carry the cinematic look. */}
            <hemisphereLight args={["#fff0e8", "#d8b8e4", 0.3]} />
          </Suspense>
        </Canvas>
      )}

      {(!modelUrl || webglFailed || modelLoadState === "failed") && <AvatarFallback state={state} />}

      {modelUrl && (webglFailed || modelLoadState !== "ready") && (
        <div role={webglFailed || modelLoadState === "failed" ? "alert" : "status"}
          style={{ position: "absolute", inset: 0, zIndex: 2, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12, padding: 24, textAlign: "center", background: "var(--bg-surface, #17121b)", color: "var(--text-primary, #fff2f6)" }}>
          <span>{webglFailed ? "3D rendering was interrupted. Your chat is still available." : modelLoadState === "failed" ? "Hina's 3D model couldn't load. Your chat is still available." : "Loading Hina's 3D model…"}</span>
          {(webglFailed || modelLoadState === "failed") && (
            <button type="button" onClick={() => { setWebglFailed(false); setModelLoadState("loading"); setModelAttempt(attempt => attempt + 1); }}
              style={{ padding: "10px 16px", borderRadius: 12, border: "1px solid var(--border-default, #695260)", background: "var(--bg-surface-raised, #332532)", color: "inherit", cursor: "pointer" }}>
              Retry 3D model
            </button>
          )}
        </div>
      )}

      <VoiceVeil
        live={liveStatus ?? { active: false, paused: false, detail: "", microphoneLevel: 0 }}
        onReconnect={onStartLive ?? (() => undefined)}
        overlayActive={isFullscreen}
      />

      <FullscreenCompanionOverlay
        open={isFullscreen}
        companionName={companionName}
        companionState={state}
        live={liveStatus ?? { active: false, paused: false, detail: "", microphoneLevel: 0 }}
        messages={messages}
        partialTranscript={partialTranscript}
        streamingText={streamingText}
        trackingActive={Boolean(faceTrackingActive)}
        onStartLive={onStartLive ?? (() => undefined)}
        onStopLive={onStopLive ?? (() => undefined)}
        onPauseLive={onPauseLive ?? (() => undefined)}
        onResumeLive={onResumeLive ?? (() => undefined)}
      />

      {/* Controls */}
      <div className="avatar-playground__controls">
        {faceTrackingActive && (
          <div className="avatar-playground__live-badge">
            <Radio size={9} aria-hidden="true" />
            <span>LIVE</span>
          </div>
        )}
        {onToggleWalk && (
          <motion.button
            type="button" onClick={onToggleWalk}
            whileHover={{ scale:1.1 }} whileTap={{ scale:0.9 }}
            className={`avatar-playground__control ${isWalking ? "avatar-playground__control--active" : ""}`}
            title={isWalking ? "Stop walking" : "Start procedural walking"}
            aria-label={isWalking ? "Stop procedural walking" : "Start procedural walking"}
            aria-pressed={isWalking}
            style={isWalking ? { background: "rgba(236, 72, 153, 0.25)", color: "#f472b6", borderColor: "rgba(236, 72, 153, 0.5)" } : undefined}
          >
            <Footprints size={13} aria-hidden="true" />
          </motion.button>
        )}
        <motion.button
          type="button" onClick={toggleFullscreen}
          whileHover={{ scale:1.08 }} whileTap={{ scale:0.92 }}
          className="avatar-playground__control avatar-playground__fullscreen"
          title={isFullscreen ? "Exit Hinaa playground" : "Open Hinaa playground full screen"}
          aria-label={isFullscreen ? "Exit Hinaa playground full screen" : "Open Hinaa playground full screen"}
          aria-pressed={isFullscreen}
        >
          {isFullscreen ? <Minimize2 size={13} aria-hidden="true" /> : <Expand size={13} aria-hidden="true" />}
        </motion.button>
        <motion.button
          type="button" onClick={cycle}
          whileHover={{ scale:1.1 }} whileTap={{ scale:0.9 }}
          className="avatar-playground__control"
          title={`Camera: ${mode === "upperbody" ? "upper body" : mode}`}
          aria-label={`Change avatar camera from ${mode === "upperbody" ? "upper body" : mode}`}
        >
          <Maximize2 size={12} aria-hidden="true" />
        </motion.button>
      </div>

    </div>
  );
}

export default AvatarPresence;
