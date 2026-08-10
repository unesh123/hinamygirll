/**
 * VRMAvatar — Perfect cinematic VRM avatar with:
 * - Multi-phoneme lip-sync (Aa, Ih, Ou, Ee, Oh)
 * - Full expression system (happy, sad, surprised, thinking, concerned)
 * - Eye tracking with smooth follow
 * - Head gestures (nod, tilt, shake)
 * - Arm/hand idle animation
 * - Breathing animation
 * - Natural blinking with double-blink
 */

import { useEffect, useState, useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { VRMLoaderPlugin, VRM, VRMExpressionPresetName } from "@pixiv/three-vrm";
import * as THREE from "three";

/* ─── Types ─────────────────────────────────────────────── */
export type AvatarEmotion =
  | "neutral"
  | "happy"
  | "excited"
  | "playful"
  | "shy"
  | "concerned"
  | "sad"
  | "surprised"
  | "thinking";

interface VRMAvatarProps {
  url: string;
  jawEnergy?: React.MutableRefObject<number>;
  isSpeaking?: boolean;
  isListening?: boolean;
  isThinking?: boolean;
  emotion?: AvatarEmotion;
  closeUp?: boolean;
}

/* ─── Emotion → Blend Shape Map ────────────────────────── */
const EMOTION_BLENDS: Record<AvatarEmotion, Partial<Record<VRMExpressionPresetName, number>>> = {
  neutral: { Happy: 0, Sad: 0, Angry: 0, Surprised: 0, Relaxed: 0.15 },
  happy: { Happy: 0.8, Sad: 0, Surprised: 0.1, Relaxed: 0.1 },
  excited: { Happy: 1.0, Surprised: 0.4, Relaxed: 0 },
  playful: { Happy: 0.6, Surprised: 0.2, Relaxed: 0.2 },
  shy: { Happy: 0.3, Sad: 0.1, Relaxed: 0.4 },
  concerned: { Happy: 0, Sad: 0.45, Angry: 0.1, Relaxed: 0.2 },
  sad: { Happy: 0, Sad: 0.8, Relaxed: 0.3 },
  surprised: { Happy: 0.15, Sad: 0, Surprised: 0.9, Relaxed: 0 },
  thinking: { Happy: 0, Sad: 0.1, Surprised: 0, Relaxed: 0.5 },
};

/* ─── Phoneme mouth shapes ──────────────────────────────── */
const MOUTH_PHONEMES: VRMExpressionPresetName[] = [
  VRMExpressionPresetName.Aa,
  VRMExpressionPresetName.Ih,
  VRMExpressionPresetName.Ou,
  VRMExpressionPresetName.Ee,
  VRMExpressionPresetName.Oh,
];

export function VRMAvatar({
  url,
  jawEnergy,
  isSpeaking = false,
  isListening = false,
  isThinking = false,
  emotion = "neutral",
  closeUp = false,
}: VRMAvatarProps) {
  const [vrm, setVrm] = useState<VRM | null>(null);
  const [loadError, setLoadError] = useState(false);

  const timeRef = useRef(0);
  const blinkTimerRef = useRef(2 + Math.random() * 3);
  const doubleBlinkRef = useRef(false);
  const mouthOpenRef = useRef(0);
  const phonemeIndexRef = useRef(0);
  const phonemeTimerRef = useRef(0);
  const expressionWeightsRef = useRef<Record<string, number>>({});
  const targetExpressionRef = useRef<Record<string, number>>({});
  const gazeTargetRef = useRef({ x: 0, y: 0 });
  const gazeCurrentRef = useRef({ x: 0, y: 0 });
  const headNodRef = useRef(0);
  const headTiltRef = useRef(0);
  const headShakeRef = useRef(0);
  const armSwingRef = useRef(0);

  /* ─── Load VRM ───────────────────────────────────────── */
  useEffect(() => {
    let active = true;
    setLoadError(false);

    const loader = new GLTFLoader();
    loader.crossOrigin = "anonymous";
    loader.register((parser) => new VRMLoaderPlugin(parser));

    loader.load(
      url,
      (gltf) => {
        if (!active) return;
        const vrmData = gltf.userData.vrm as VRM;
        if (vrmData) {
          vrmData.scene.traverse((obj) => {
            obj.frustumCulled = false;
            if ((obj as THREE.Mesh).isMesh) {
              ((obj as THREE.Mesh).material as THREE.Material).side = THREE.DoubleSide;
            }
          });
          vrmData.scene.rotation.y = Math.PI;
          setVrm(vrmData);
        }
      },
      undefined,
      () => { if (active) setLoadError(true); },
    );

    return () => { active = false; };
  }, [url]);

  /* ─── Compute target expression ──────────────────────── */
  useEffect(() => {
    targetExpressionRef.current = {};
    const blends = EMOTION_BLENDS[emotion] || EMOTION_BLENDS.neutral;
    for (const [key, val] of Object.entries(blends)) {
      targetExpressionRef.current[key] = val;
    }
  }, [emotion]);

  /* ─── Animation frame ────────────────────────────────── */
  useFrame((_state, delta) => {
    if (!vrm) return;

    const dt = Math.min(delta, 0.1); // Clamp delta
    timeRef.current += dt;
    const t = timeRef.current;

    const em = vrm.expressionManager;
    const hd = vrm.humanoid;
    if (!em || !hd) return;

    /* ── Smooth expression lerp ────────────────────────── */
    for (const key of Object.keys(targetExpressionRef.current)) {
      const current = expressionWeightsRef.current[key] || 0;
      const target = targetExpressionRef.current[key] || 0;
      expressionWeightsRef.current[key] = current + (target - current) * (dt * 4);
    }

    /* ── Lip-sync with multi-phoneme ───────────────────── */
    let targetMouth = 0;
    if (isSpeaking && jawEnergy) {
      targetMouth = Math.min(1.0, jawEnergy.current * 1.35);

      // Cycle through phonemes for natural mouth shapes
      phonemeTimerRef.current -= dt;
      if (phonemeTimerRef.current <= 0) {
        phonemeIndexRef.current = Math.floor(Math.random() * MOUTH_PHONEMES.length);
        phonemeTimerRef.current = 0.06 + Math.random() * 0.14;
      }
    }

    // Smooth mouth lerp
    mouthOpenRef.current += (targetMouth - mouthOpenRef.current) * (dt * 18);

    // Apply primary mouth shape (Aa) for jaw energy
    em.setValue(VRMExpressionPresetName.Aa, mouthOpenRef.current * 0.9);

    // Add secondary mouth shapes for realism
    if (isSpeaking && mouthOpenRef.current > 0.05) {
      const phoneme = MOUTH_PHONEMES[phonemeIndexRef.current];
      const secondaryAmount = mouthOpenRef.current * 0.45;
      em.setValue(phoneme, Math.min(1, (em.getValue(phoneme) || 0) + secondaryAmount * dt * 20));
      // Fade other mouth shapes
      for (const p of MOUTH_PHONEMES) {
        if (p !== phoneme && p !== VRMExpressionPresetName.Aa) {
          const v = em.getValue(p) || 0;
          em.setValue(p, v * (1 - dt * 12));
        }
      }
    } else {
      // Fade all mouth shapes
      for (const p of MOUTH_PHONEMES) {
        const v = em.getValue(p) || 0;
        em.setValue(p, v * (1 - dt * 14));
      }
    }

    /* ── Blinking with double-blink ────────────────────── */
    blinkTimerRef.current -= dt;
    let blinkVal = 0;

    if (blinkTimerRef.current <= 0) {
      if (blinkTimerRef.current < -0.12) {
        // Check for double blink
        if (doubleBlinkRef.current) {
          doubleBlinkRef.current = false;
          blinkTimerRef.current = 1.5 + Math.random() * 4;
        } else if (Math.random() < 0.15) {
          doubleBlinkRef.current = true;
          blinkTimerRef.current = -0.05; // Quick second blink
        } else {
          blinkTimerRef.current = 2 + Math.random() * 5;
        }
      } else {
        const progress = (blinkTimerRef.current + 0.12) / 0.12;
        blinkVal = Math.sin(Math.max(0, Math.min(1, progress)) * Math.PI);
      }
    }

    em.setValue(VRMExpressionPresetName.Blink, blinkVal);

    /* ── Eye tracking ──────────────────────────────────── */
    if (isListening) {
      gazeTargetRef.current = { x: Math.sin(t * 0.4) * 0.25, y: Math.cos(t * 0.6) * 0.1 + 0.05 };
    } else if (isSpeaking) {
      gazeTargetRef.current = { x: Math.sin(t * 1.2) * 0.08, y: 0.1 + Math.sin(t * 0.8) * 0.04 };
    } else if (isThinking) {
      gazeTargetRef.current = {
        x: Math.sin(t * 0.35) * 0.3,
        y: 0.15 + Math.cos(t * 0.45) * 0.1,
      };
    } else {
      gazeTargetRef.current = { x: Math.sin(t * 0.3) * 0.12, y: Math.sin(t * 0.5) * 0.06 };
    }

    gazeCurrentRef.current.x += (gazeTargetRef.current.x - gazeCurrentRef.current.x) * (dt * 5);
    gazeCurrentRef.current.y += (gazeTargetRef.current.y - gazeCurrentRef.current.y) * (dt * 5);

    em.setValue(VRMExpressionPresetName.LookLeft, -gazeCurrentRef.current.x);
    em.setValue(VRMExpressionPresetName.LookRight, gazeCurrentRef.current.x);
    em.setValue(VRMExpressionPresetName.LookUp, gazeCurrentRef.current.y);
    em.setValue(VRMExpressionPresetName.LookDown, -gazeCurrentRef.current.y * 0.5);

    /* ── Apply expression weights ──────────────────────── */
    for (const [key, val] of Object.entries(expressionWeightsRef.current)) {
      if (key in VRMExpressionPresetName && key !== "Blink" && !key.startsWith("Look")) {
        em.setValue(key as VRMExpressionPresetName, val);
      }
    }

    /* ── Breathing ─────────────────────────────────────── */
    const breath = Math.sin(t * 1.6) * 0.012;
    const spine = hd.getNormalizedBoneNode("spine");
    if (spine) spine.rotation.x = breath;

    /* ── Head motion ───────────────────────────────────── */
    const head = hd.getNormalizedBoneNode("head");
    if (head) {
      // Natural idle sway
      head.rotation.y = Math.sin(t * 0.45) * 0.04;
      head.rotation.z = Math.sin(t * 0.55) * 0.015;

      // Nod when speaking
      if (isSpeaking && mouthOpenRef.current > 0.05) {
        headNodRef.current = Math.sin(t * 3.5) * mouthOpenRef.current * 0.06;
        head.rotation.x += headNodRef.current;
      }

      // Tilt when listening
      if (isListening) {
        headTiltRef.current = Math.sin(t * 0.5) * 0.08;
        head.rotation.z += headTiltRef.current;
        head.rotation.y += Math.sin(t * 0.7) * 0.03;
      }

      // Thinking pose
      if (isThinking) {
        head.rotation.z += 0.08;
        head.rotation.x -= 0.03;
      }
    }

    /* ── Arm/hand animations ───────────────────────────── */
    const leftUpperArm = hd.getNormalizedBoneNode("leftUpperArm");
    const rightUpperArm = hd.getNormalizedBoneNode("rightUpperArm");
    const leftHand = hd.getNormalizedBoneNode("leftHand") || hd.getNormalizedBoneNode("leftLowerArm");
    const rightHand = hd.getNormalizedBoneNode("rightHand") || hd.getNormalizedBoneNode("rightLowerArm");

    if (isSpeaking) {
      // Gesture animation while speaking
      armSwingRef.current += dt;
      const gestureAmp = Math.min(1, mouthOpenRef.current * 0.8);
      if (rightUpperArm) {
        rightUpperArm.rotation.z = Math.sin(armSwingRef.current * 2.5) * 0.12 * gestureAmp;
        rightUpperArm.rotation.x = -0.1 * gestureAmp;
      }
      if (rightHand) {
        rightHand.rotation.z = Math.sin(armSwingRef.current * 3) * 0.08 * gestureAmp;
      }
      if (leftUpperArm) {
        leftUpperArm.rotation.z = Math.cos(armSwingRef.current * 2.2) * 0.08 * gestureAmp;
      }
    } else {
      // Subtle idle arm sway
      if (rightUpperArm) rightUpperArm.rotation.z = Math.sin(t * 0.6) * 0.03;
      if (leftUpperArm) leftUpperArm.rotation.z = Math.cos(t * 0.7) * 0.03;
    }

    /* ── Update ────────────────────────────────────────── */
    vrm.update(dt);
  });

  if (loadError) {
    return null; // Silent fail — don't break the UI
  }

  if (!vrm) {
    return null;
  }

  // Close-up: position higher for face framing
  const yPos = closeUp ? -0.4 : -1.2;

  return <primitive object={vrm.scene} position={[0, yPos, 0]} />;
}

export default VRMAvatar;
