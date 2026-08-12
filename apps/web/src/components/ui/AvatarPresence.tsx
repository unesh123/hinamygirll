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

import { Suspense, useState, useRef, useEffect, useCallback } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { ContactShadows, Environment } from "@react-three/drei";
import { motion } from "framer-motion";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { VRMLoaderPlugin, VRM, VRMExpressionPresetName, VRMUtils } from "@pixiv/three-vrm";
import * as THREE from "three";
import { Maximize2, Radio } from "lucide-react";
import type { CompanionState } from "../../features/companion/types";
import type { AvatarPresentation } from "../../features/avatar/avatarPresentation";
import type { FaceExpressions } from "../../features/audio/useVSeeFace";
import type { VisemeEvent } from "../../features/audio/textToViseme";
import { getActiveViseme } from "../../features/audio/textToViseme";

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

function cameraFromAnatomy(mode: PresenceMode, fallback: CameraPreset, frame?: AnatomyFrame): CameraPreset {
  if (!frame || mode === "hidden") return fallback;
  const torso = Math.max(0.28, frame.headY - frame.chestY);
  const bodyHeight = Math.max(1.1, frame.maxY - frame.minY);
  const x = frame.centerX;
  const portraitFov = 31;
  // Head/chest control composition. Bounds are used only to avoid clipping hair
  // and accessories, never to pull the portrait target down toward a long skirt.
  const portraitTop = Math.max(frame.maxY, frame.headY + torso * 0.44);
  const portraitBottom = frame.chestY - torso * 0.38;
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

/* ─── Emotion blends (always low intensity — never override mouth) */
type EmotionBlend = Partial<Record<VRMExpressionPresetName, number>>;
function emotionFor(state: CompanionState): EmotionBlend {
  switch (state) {
    case "listening":   return { [VRMExpressionPresetName.Relaxed]: 0.10 };
    case "thinking":    return { [VRMExpressionPresetName.Relaxed]: 0.14 };
    case "speaking":    return { [VRMExpressionPresetName.Happy]: 0.12, [VRMExpressionPresetName.Relaxed]: 0.06 };
    case "interrupted": return { [VRMExpressionPresetName.Relaxed]: 0.16 };
    case "error":       return { [VRMExpressionPresetName.Sad]: 0.12 };
    default:            return { [VRMExpressionPresetName.Happy]: 0.06 };
  }
}

/* ─── Conversational neutral pose ───────────────────────── */
// Offsets are always multiplied once against cached immutable normalized-bone
// rest quaternions. No raw J_Bip nodes and no cumulative Euler edits are used.
type PoseBoneName = "leftUpperArm" | "rightUpperArm" | "leftLowerArm" | "rightLowerArm" | "leftHand" | "rightHand";
const POSE_BONES: PoseBoneName[] = ["leftUpperArm", "rightUpperArm", "leftLowerArm", "rightLowerArm", "leftHand", "rightHand"];
const restOffset = () => new THREE.Quaternion();
const q = (x = 0, y = 0, z = 0) => new THREE.Quaternion().setFromEuler(new THREE.Euler(x, y, z, "XYZ"));

// `model_6164` is the screenshot baseline. Its authored normalized rest has
// horizontal upper arms; mirrored Z offsets lower shoulders without touching
// root scale/position or hands. Other known/managed rigs keep authored rest
// until their Avatar Lab calibration produces a reviewed profile.
const MODEL_POSE_OFFSETS: Record<string, Record<PoseBoneName, THREE.Quaternion>> = {
  "/models/model_6164.vrm": {
    leftUpperArm: q(0, 0, 1.10), rightUpperArm: q(0, 0, -1.10),
    leftLowerArm: q(0, 0, 0.20), rightLowerArm: q(0, 0, -0.20),
    leftHand: restOffset(), rightHand: restOffset(),
  },
  "/models/model_5447.vrm": {
    leftUpperArm: q(0, 0, 0.86), rightUpperArm: q(0, 0, -0.86),
    leftLowerArm: q(0, 0, 0.14), rightLowerArm: q(0, 0, -0.14),
    leftHand: restOffset(), rightHand: restOffset(),
  },
};
const DEFAULT_POSE_OFFSETS: Record<PoseBoneName, THREE.Quaternion> = {
  leftUpperArm: restOffset(), rightUpperArm: restOffset(), leftLowerArm: restOffset(),
  rightLowerArm: restOffset(), leftHand: restOffset(), rightHand: restOffset(),
};
// Generic imported VRMs begin in a conservative relaxed pose. Users can use
// the simple “Original pose” action if a non-standard rig needs its author pose.
const GENERIC_RELAXED_POSE_OFFSETS: Record<PoseBoneName, THREE.Quaternion> = {
  leftUpperArm: q(0, 0, 0.62), rightUpperArm: q(0, 0, -0.62),
  leftLowerArm: q(0, 0, 0.10), rightLowerArm: q(0, 0, -0.10),
  leftHand: restOffset(), rightHand: restOffset(),
};

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
  trackingCalibration?: { headBaseline?: [number, number, number, number] } | null;
  onAnatomyFrame?: (frame: AnatomyFrame) => void;
}

function Model({
  state, jawEnergy, speakingRef, visemeEvents, audioStartTimeRef, url, presentation, faceExpressions, faceBones, faceTrackingActive, trackingCalibration, onAnatomyFrame,
}: ModelProps) {
  const vrmRef   = useRef<VRM | null>(null);
  const availRef = useRef<Set<string>>(new Set());
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);

  const normBonesRef = useRef<Partial<Record<PoseBoneName, THREE.Object3D>>>({});
  const curQRef      = useRef<Partial<Record<PoseBoneName, THREE.Quaternion>>>({});
  const restQRef     = useRef<Partial<Record<PoseBoneName, THREE.Quaternion>>>({});
  const poseTargetRef = useRef<Partial<Record<PoseBoneName, THREE.Quaternion>>>({});
  const headBoneRef = useRef<THREE.Object3D | null>(null);
  const headRestQRef = useRef<THREE.Quaternion | null>(null);
  const headCurQRef = useRef<THREE.Quaternion | null>(null);

  // Per-frame refs — no allocations
  const t           = useRef(0);
  const blinkTimer  = useRef(2 + Math.random() * 3);
  const doubleBlink = useRef(false);
  // Current mouth weights (smoothed)
  const mouthW      = useRef<Record<MouthKey, number>>({ aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 });
  const emo         = useRef<Record<string, number>>({});
  // AudioContext ref — populated lazily from global on first frame
  const audioCtxRef = useRef<AudioContext | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoaded(false);
    setFailed(false);
    normBonesRef.current = {};
    curQRef.current = {};
    restQRef.current = {};
    poseTargetRef.current = {};
    headBoneRef.current = null;
    headRestQRef.current = null;
    headCurQRef.current = null;
    availRef.current = new Set();
    t.current = 0;
    mouthW.current = { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 };

    const ldr = new GLTFLoader();
    ldr.crossOrigin = "anonymous";
    ldr.register(p => new VRMLoaderPlugin(p));

    ldr.load(url, gltf => {
      if (!mounted) return;
      const v = gltf.userData.vrm as VRM;
      if (!v) { setFailed(true); return; }

      // Optimizations
      try { VRMUtils.removeUnnecessaryVertices(v.scene); } catch {}
      try { VRMUtils.removeUnnecessaryJoints(v.scene); } catch {}
      v.scene.traverse((o: THREE.Object3D) => {
        o.frustumCulled = false;
        if ((o as THREE.Mesh).isMesh) {
          const mat = (o as THREE.Mesh).material as THREE.Material;
          if (mat) mat.side = THREE.DoubleSide;
        }
      });

      // Orientation
      const specVer: string = (v as any).meta?.specVersion ?? (v as any).meta?.version ?? "1.0";
      const isVrm0 = specVer.startsWith("0");
      if (isVrm0) {
        try { VRMUtils.rotateVRM0(v); } catch {}
      }

      if (v.lookAt) { try { (v.lookAt as any).enabled = false; } catch {} }

      v.scene.rotation.y = presentation.rotationY;
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
        ];
        for (const name of allNames) {
          try { if (em.getExpression(name)) availRef.current.add(name); } catch {}
        }
      }

      // Cache normalized bone nodes and immutable rest quaternions once. The
      // per-frame loop only slerps to the precomputed calibrated targets.
      const hd = v.humanoid;
      if (hd) {
        const offsets = presentation.poseMode === "original"
          ? DEFAULT_POSE_OFFSETS
          : MODEL_POSE_OFFSETS[url] ?? GENERIC_RELAXED_POSE_OFFSETS;
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
      }

      if (import.meta.env.DEV) {
        const bones = POSE_BONES.filter(b => !!normBonesRef.current[b]);
        const exprs = [...availRef.current].slice(0, 12).join(", ");
        console.log(`🎭 VRM ${specVer} | url=${url} | bones: ${bones.join(", ")} | expressions: ${exprs}`);
      }

      vrmRef.current = v;
      setLoaded(true);
    }, undefined, () => { if (mounted) setFailed(true); });

    return () => {
      mounted = false;
      // Ensure mouth expressions are reset on unmount/unload
      if (vrmRef.current) {
        try { VRMUtils.deepDispose(vrmRef.current.scene); } catch {}
        vrmRef.current = null;
      }
    };
  }, [url, presentation.rotationY, presentation.offsetY, presentation.scale, presentation.poseMode]);

  useFrame((_, dtRaw) => {
    const vrm = vrmRef.current;
    if (!vrm) return;
    const dt = Math.min(dtRaw, 0.05);
    t.current += dt;

    const em  = vrm.expressionManager;
    // Safe setter with VRM 1.0 alias fallback
    const set = (n: string, v: number) => {
      if (!em) return;
      try { em.setValue(n, v); } catch {}
      const alias: Record<string, string> = {
        aa: "a", ih: "i", ou: "u", ee: "e", oh: "o",
        happy: "joy", sad: "sorrow", relaxed: "fun",
        blinkLeft: "blink_l", blinkRight: "blink_r",
      };
      if (alias[n]) { try { em.setValue(alias[n], v); } catch {} }
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
      const speaking = speakingRef.current;
      // RMS values vary greatly across local voice engines and browsers. Shape
      // them for visible but natural articulation instead of treating quiet
      // speech as silence.
      const rawEnergy = Math.min(1, Math.max(0, jawEnergy.current * 3.2));
      const energy = speaking ? Math.max(0.16, Math.sqrt(rawEnergy) * 0.82) : rawEnergy;

      if (speaking) {
        // ── Speaking: viseme-based mouth animation ──
        // Lazily populate audioCtxRef from global (avoids prop drilling through Canvas)
        if (!audioCtxRef.current) {
          audioCtxRef.current = (window as any).__hinaaAudioCtx ?? null;
        }
        const events = visemeEvents.current;
        let targetMouth: MouthKey | null = null;
        let targetWeight = 0;

        if (events.length > 0) {
          // Use AudioContext time if available, else fallback to energy cycling
          const ctx = audioCtxRef.current;
          if (ctx) {
            const playTimeMs = (ctx.currentTime - audioStartTimeRef.current) * 1000;
            const active = getActiveViseme(Math.max(0, playTimeMs), events);
            if (active && active.mouth !== "closed") {
              targetMouth = VISEME_TO_VRM[active.mouth] as MouthKey ?? "aa";
              targetWeight = Math.max(0.10, active.weight * energy);
            } else {
              // Preserve a soft open-mouth bridge between phoneme windows.
              // This avoids a distracting open/close flicker on streamed TTS.
              targetMouth = "aa";
              targetWeight = energy * 0.36;
            }
          } else {
            // Fallback: cycle based on energy timing
            const idx = Math.floor(t.current * 7) % ALL_MOUTH_KEYS.length;
            targetMouth = ALL_MOUTH_KEYS[idx];
            targetWeight = energy;
          }
        } else {
          // No viseme events — energy-based jaw-open fallback
          targetMouth = "aa";
          targetWeight = energy;
        }

        // Smooth all mouth shapes
        for (const k of ALL_MOUTH_KEYS) {
          const tgt = k === targetMouth ? targetWeight : 0;
          mouthW.current[k] += (tgt - mouthW.current[k]) * Math.min(1, dt * 14);
          set(VRM_PRESET[k], Math.max(0, mouthW.current[k]));
        }
      } else if (faceExpressions) {
        // ── Fresh external VMC, while not speaking: use observed vowel data
        // when available, otherwise the sender's conservative mouth-open cue.
        const tracked: Record<MouthKey, number> = {
          aa: Math.max(faceExpressions.mouthA, faceExpressions.mouthOpen),
          ih: faceExpressions.mouthI, ou: faceExpressions.mouthU,
          ee: faceExpressions.mouthE, oh: faceExpressions.mouthO,
        };
        for (const k of ALL_MOUTH_KEYS) {
          mouthW.current[k] += (tracked[k] - mouthW.current[k]) * Math.min(1, dt * 12);
          set(VRM_PRESET[k], Math.max(0, mouthW.current[k]));
        }
      } else {
        // ── Idle / silence: fade mouth closed ──
        let allZero = true;
        for (const k of ALL_MOUTH_KEYS) {
          mouthW.current[k] *= Math.max(0, 1 - dt * 25);
          if (mouthW.current[k] < 0.005) mouthW.current[k] = 0;
          else allZero = false;
          set(VRM_PRESET[k], mouthW.current[k]);
        }
        if (allZero) {
          // Ensure all are exactly 0
          for (const k of ALL_MOUTH_KEYS) set(VRM_PRESET[k], 0);
        }
      }

      /* ── LAYER 3: BLINK ─────────────────────────────────────────── */
      if (faceExpressions) {
        const blL = Math.max(0, 1 - faceExpressions.eyeBlinkL);
        const blR = Math.max(0, 1 - faceExpressions.eyeBlinkR);
        set(VRMExpressionPresetName.BlinkLeft,  blL);
        set(VRMExpressionPresetName.BlinkRight, blR);
        set(VRMExpressionPresetName.Blink, (blL + blR) / 2);
      } else {
        // Natural auto-blink
        blinkTimer.current -= dt;
        let bv = 0;
        if (blinkTimer.current <= 0) {
          if (blinkTimer.current < -0.14) {
            if (doubleBlink.current) {
              doubleBlink.current = false;
              blinkTimer.current = 1.5 + Math.random() * 3.5;
            } else if (Math.random() < 0.18) {
              doubleBlink.current = true;
              blinkTimer.current = -0.02;
            } else {
              blinkTimer.current = 2 + Math.random() * 4;
            }
          } else {
            const phase = (blinkTimer.current + 0.14) / 0.14;
            bv = Math.sin(Math.max(0, Math.min(1, phase)) * Math.PI);
          }
        }
        set(VRMExpressionPresetName.Blink, bv);
        set(VRMExpressionPresetName.BlinkLeft, 0);
        set(VRMExpressionPresetName.BlinkRight, 0);
      }

      /* ── LAYER 4: EMOTION (always low weight, never overrides mouth) */
      if (faceExpressions) {
        // Mirror VSeeFace expressions — cap at 0.5 so they don't go extreme
        const capEmo = (v: number) => Math.min(0.5, v);
        set(VRMExpressionPresetName.Happy,     capEmo(faceExpressions.mouthSmile));
        set(VRMExpressionPresetName.Surprised, capEmo((faceExpressions.browUpL + faceExpressions.browUpR) / 2));
        set(VRMExpressionPresetName.Angry,     capEmo(Math.max(faceExpressions.angry, (faceExpressions.browDownL + faceExpressions.browDownR) / 2)));
        set(VRMExpressionPresetName.Sad,       capEmo(faceExpressions.sad));
        set(VRMExpressionPresetName.Relaxed,   capEmo(Math.max(faceExpressions.relaxed, faceExpressions.cheekPuff)));
      } else {
        const tEmo = emotionFor(state);
        const emoKeys = [
          VRMExpressionPresetName.Happy, VRMExpressionPresetName.Sad,
          VRMExpressionPresetName.Relaxed, VRMExpressionPresetName.Angry,
        ] as const;
        for (const key of emoKeys) {
          const tgt = (tEmo as any)[key] ?? 0;
          emo.current[key] = (emo.current[key] ?? 0) + (tgt - (emo.current[key] ?? 0)) * dt * 2.5;
          set(key, emo.current[key]);
        }
      }

      /* ── LAYER 5: GAZE — subtle eye movement ─────────────────────── */
      // Small sine-wave gaze that leads head movement slightly
      const gazX = Math.sin(t.current * 0.22) * 0.06;
      const gazY = Math.sin(t.current * 0.17 + 1.2) * 0.04;
      if (vrm.lookAt) {
        try {
          (vrm.lookAt as any).target = undefined;
          if ((vrm.lookAt as any).lookAt) {
            (vrm.lookAt as any).lookAt(new THREE.Vector3(gazX, gazY, 1));
          }
        } catch {}
      }
    }

    /* ── CALIBRATED HEAD-ONLY VMC ─────────────────────────────────── */
    // VMC body/limb packets are deliberately ignored. Head motion is applied
    // only after a live external neutral calibration, using a bounded delta
    // relative to the captured tracker baseline and the VRM's rest quaternion.
    const head = headBoneRef.current;
    const headRest = headRestQRef.current;
    const headCurrent = headCurQRef.current;
    const rawHead = faceTrackingActive ? faceBones?.Head : undefined;
    const baseline = trackingCalibration?.headBaseline;
    if (head && headRest && headCurrent && rawHead && baseline) {
      const raw = new THREE.Quaternion(rawHead[0], rawHead[1], rawHead[2], rawHead[3]).normalize();
      const neutral = new THREE.Quaternion(baseline[0], baseline[1], baseline[2], baseline[3]).normalize();
      const delta = neutral.invert().multiply(raw);
      // A safety clamp prevents a malformed sender/axis mismatch from rotating
      // the companion out of frame. Further axis calibration belongs in Avatar Lab.
      const maxAngle = THREE.MathUtils.degToRad(22);
      if (2 * Math.acos(THREE.MathUtils.clamp(delta.w, -1, 1)) > maxAngle) {
        delta.slerp(new THREE.Quaternion(), 1 - maxAngle / (2 * Math.acos(THREE.MathUtils.clamp(delta.w, -1, 1))));
      }
      const targetHead = headRest.clone().multiply(delta);
      headCurrent.slerp(targetHead, Math.min(1, dt * 7));
      head.quaternion.copy(headCurrent);
    } else if (head && headRest && headCurrent) {
      headCurrent.slerp(headRest, Math.min(1, dt * 5));
      head.quaternion.copy(headCurrent);
    }

    /* ── RELAXED POSE / FACE TRACKING POSE ────────────────────────── */
    const alpha = t.current < 0.1 ? 1.0 : Math.min(1, dt * 9);
    const nb = normBonesRef.current;
    const cq = curQRef.current;

    for (const boneName of POSE_BONES) {
      const bone = nb[boneName];
      const cur  = cq[boneName];
      if (!bone || !cur) continue;
      
      // Face tracking deliberately never drives limbs. Some VMC senders emit
      // incomplete arm transforms that do not match this VRM's local axes and
      // result in twisted wrists or raised hands. Limb gestures can be added
      // later as per-model animation clips after visual calibration.
      const targetQ = poseTargetRef.current[boneName];
      if (!targetQ) continue;
      cur.slerp(targetQ, alpha);
      
      bone.quaternion.copy(cur);
    }

    /* ── VRM UPDATE ──────────────────────────────────────────────── */
    vrm.update(dt);
  });

  if (failed || !loaded) return null;
  return <primitive object={vrmRef.current!.scene} />;
}

/* ─── Camera controller ───────────────────────────────────── */
function Cam({ mode, modelUrl, anatomy }: { mode: PresenceMode; modelUrl: string; anatomy?: AnatomyFrame }) {
  const fallback = MODEL_CAMERA_PRESETS[modelUrl]?.[mode] ?? CAMERAS[mode] ?? CAMERAS.portrait;
  const cfg = cameraFromAnatomy(mode, fallback, anatomy);
  const camera = useThree(s => s.camera);
  const dirty  = useRef(true);

  useEffect(() => { dirty.current = true; }, [mode, modelUrl, anatomy?.revision]);

  useFrame(() => {
    if (dirty.current) {
      camera.position.set(...cfg.pos);
      (camera as THREE.PerspectiveCamera).fov = cfg.fov;
      camera.updateProjectionMatrix();
      dirty.current = false;
    }
    camera.lookAt(cfg.target[0], cfg.target[1], cfg.target[2]);
  });
  return null;
}

/* ─── Fallback ────────────────────────────────────────────── */
function AvatarFallback({ state }: { state: CompanionState }) {
  return (
    <div style={{ width:"100%", height:"100%", display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", gap:12, color:"#64748b" }}>
      <div style={{ width:72, height:72, borderRadius:"50%", background:"linear-gradient(135deg,rgba(167,243,208,.5),rgba(103,232,249,.5))", display:"flex", alignItems:"center", justifyContent:"center", fontSize:"1.8rem", border:"2px solid rgba(255,255,255,.8)" }}>◇</div>
      <div style={{ fontWeight:700, color:"#1a1f2e", fontSize:"0.85rem" }}>HINAA — {state}</div>
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
  trackingCalibration?: { headBaseline?: [number, number, number, number] } | null;
  presentation?: AvatarPresentation;
}

// Stable fallback refs so we never create new objects in render
const _emptyVisemes: VisemeEvent[] = [];
const _falseRef = { current: false };
const _zeroRef  = { current: 0 };
const _emptyRef = { current: _emptyVisemes };
const _startRef = { current: 0 };

export function AvatarPresence({
  mode, state, jawEnergy, speakingRef, visemeEvents, audioStartTimeRef,
  modelUrl, onModeChange, faceExpressions, faceBones, faceTrackingActive, trackingCalibration, presentation,
}: Props) {
  const [webglFailed, setWebglFailed] = useState(false);
  const [anatomy, setAnatomy] = useState<AnatomyFrame | undefined>();
  const applyAnatomy = useCallback((frame: AnatomyFrame) => setAnatomy(frame), []);

  // Reset on model change
  useEffect(() => { setWebglFailed(false); setAnatomy(undefined); }, [modelUrl]);



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
    <div style={{ position:"relative", width:"100%", height:"100%", minHeight:200 }}>
      {/* Atmospheric glow */}
      <div style={{ position:"absolute", inset:0, background:"radial-gradient(ellipse 70% 55% at 50% 35%, rgba(103,232,249,.06) 0%, transparent 70%)", pointerEvents:"none", zIndex:0 }} />

      {modelUrl && !webglFailed && (
        <Canvas
          style={{ position:"absolute", inset:0, zIndex:1 }}
          // Above 1.5× device pixel ratio, the VRM’s animated face and lip-sync
          // cost rises sharply with little visible benefit at this panel size.
          // Let R3F temporarily reduce quality under load instead of stuttering.
          dpr={[1, Math.min(window.devicePixelRatio, 1.5)]}
          performance={{ min: 0.62, debounce: 220 }}
          gl={{ antialias:true, alpha:true, powerPreference:"high-performance" }}
          onCreated={({ gl }) => {
            gl.domElement.addEventListener("webglcontextlost", e => {
              e.preventDefault();
              setWebglFailed(true);
            }, { once:true });
          }}
        >
          <Suspense fallback={null}>
            <Cam mode={mode} modelUrl={modelUrl} anatomy={anatomy} />

            {/* Cinematic lighting */}
            <ambientLight intensity={0.9}  color="#fffef8" />
            <directionalLight position={[1.5, 3, 2.5]} intensity={1.5} color="#fffcf0" castShadow={false} />
            <spotLight position={[-2.5, 2.5, 2]} intensity={1.3} color="#b7f5d8" angle={0.55} penumbra={0.7} />
            <spotLight position={[ 2.5, 2.0,-1]} intensity={1.0} color="#d4c0fd" angle={0.5}  penumbra={0.7} />
            <pointLight position={[0, 1.6, 2.2]} intensity={0.55} color="#fff5e8" />

              <Model
                state={state}
                jawEnergy={jaw}
                speakingRef={spkRef}
                visemeEvents={vEvts}
                audioStartTimeRef={aStart}
                url={modelUrl}
                presentation={presentation ?? { rotationY: 0, offsetY: 0, scale: 1, poseMode: "relaxed" }}
                faceExpressions={faceExpressions}
                faceBones={faceBones}
                faceTrackingActive={faceTrackingActive}
                trackingCalibration={trackingCalibration}
                onAnatomyFrame={applyAnatomy}
              />

            <ContactShadows
              resolution={256} scale={2.8} blur={2.5}
              opacity={0.20} far={1.5}
              position={[0, -0.02, 0]} color="#1e293b"
            />
            <Environment preset="apartment" environmentIntensity={0.3} />
          </Suspense>
        </Canvas>
      )}

      {(!modelUrl || webglFailed) && <AvatarFallback state={state} />}

      {/* Controls */}
      <div style={{ position:"absolute", bottom:8, right:8, zIndex:5, display:"flex", gap:4 }}>
        {faceTrackingActive && (
          <div style={{ display:"flex", alignItems:"center", gap:3, padding:"3px 7px", borderRadius:8, background:"rgba(34,197,94,.85)", backdropFilter:"blur(8px)", border:"1px solid rgba(255,255,255,.5)" }}>
            <Radio size={9} color="#fff" />
            <span style={{ fontSize:"0.6rem", color:"#fff", fontWeight:700, letterSpacing:"0.04em" }}>LIVE</span>
          </div>
        )}
        <motion.button
          type="button" onClick={cycle}
          whileHover={{ scale:1.1 }} whileTap={{ scale:0.9 }}
          style={{ width:28, height:28, borderRadius:8, border:"1px solid rgba(255,255,255,.65)", background:"rgba(255,255,255,.55)", backdropFilter:"blur(8px)", cursor:"pointer", display:"flex", alignItems:"center", justifyContent:"center", color:"#64748b" }}
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
