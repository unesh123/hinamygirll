/**
 * AvatarPresence — Avatar Director for HINAA.
 * Auto-detects expressions, natural blink+gaze, emotion blending,
 * multi-vowel lip-sync, breathing, relaxed idle, fixed camera modes.
 * Optimized: refs for frame state, capped DPR, no React re-render per frame.
 */

import { Suspense, useState, useRef, useEffect } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { ContactShadows, Environment } from "@react-three/drei";
import { motion } from "framer-motion";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { VRMLoaderPlugin, VRM, VRMExpressionPresetName, VRMUtils } from "@pixiv/three-vrm";
import * as THREE from "three";
import { Maximize2 } from "lucide-react";
import type { CompanionState } from "../../features/companion/types";

export type PresenceMode = "portrait" | "closeup" | "full" | "hidden";

/* ─── Camera modes — half-body friendly framing ───────── */
const CAMERAS: Record<PresenceMode, { pos: [number, number, number]; target: [number, number, number]; fov: number }> = {
  closeup:  { pos: [0, 1.42, 0.72], target: [0, 1.4, 0], fov: 26 },
  portrait: { pos: [0, 1.28, 1.15], target: [0, 1.22, 0], fov: 30 },
  full:     { pos: [0, 1.0, 1.9], target: [0, 0.95, 0], fov: 33 },
  hidden:   { pos: [0, 1.0, 3.0], target: [0, 1.0, 0], fov: 35 },
};

/* ─── Emotion → expression blend (subtle) ─────────────── */
type EmotionBlend = Partial<Record<VRMExpressionPresetName, number>>;
function emotionFor(state: CompanionState): EmotionBlend {
  switch (state) {
    case "listening":   return { relaxed: 0.12, happy: 0.05 };
    case "thinking":    return { relaxed: 0.18 };
    case "speaking":    return { happy: 0.18, relaxed: 0.06 };
    case "interrupted": return { relaxed: 0.2 };
    case "error":       return { sad: 0.16 };
    default:            return { happy: 0.07, relaxed: 0.05 };
  }
}

/* ─── Relaxed pose constants ────────────────────────────
 * Applied via normalized humanoid bones BEFORE vrm.update().
 * All values are local-space Euler X/Y/Z in radians.
 * Mirror: left Z > 0, right Z < 0 to hang arms naturally.
 */
const POSE = {
  shoulderDrop:         0.04,   // slight lowering of shoulders
  upperArmDownAngle:    0.85,   // Z-axis: arms hang toward body sides
  upperArmForwardAngle: 0.05,   // X-axis: subtle forward lean
  elbowBend:            0.22,   // Z-axis on lower arm
  wristNeutral:         0.10,   // X-axis slight rotation
  poseBlendSpeed:       8,      // blend speed (frames-per-second scaling)
} as const;

/* ─── Bone cache type ──────────────────────────────────── */
interface BoneCache {
  leftUpperArm:  THREE.Object3D | null;
  rightUpperArm: THREE.Object3D | null;
  leftLowerArm:  THREE.Object3D | null;
  rightLowerArm: THREE.Object3D | null;
  leftHand:      THREE.Object3D | null;
  rightHand:     THREE.Object3D | null;
  leftShoulder:  THREE.Object3D | null;
  rightShoulder: THREE.Object3D | null;
}

/* ─── Relaxed quaternion targets ──────────────────────── */
interface PoseTargets {
  leftUpperArm:  THREE.Quaternion;
  rightUpperArm: THREE.Quaternion;
  leftLowerArm:  THREE.Quaternion;
  rightLowerArm: THREE.Quaternion;
  leftHand:      THREE.Quaternion;
  rightHand:     THREE.Quaternion;
}

function buildRelaxedTargets(): PoseTargets {
  const qLUA = new THREE.Quaternion().setFromEuler(
    new THREE.Euler(POSE.upperArmForwardAngle, 0, POSE.upperArmDownAngle)
  );
  const qRUA = new THREE.Quaternion().setFromEuler(
    new THREE.Euler(-POSE.upperArmForwardAngle, 0, -POSE.upperArmDownAngle)
  );
  const qLLA = new THREE.Quaternion().setFromEuler(
    new THREE.Euler(0, 0, POSE.elbowBend)
  );
  const qRLA = new THREE.Quaternion().setFromEuler(
    new THREE.Euler(0, 0, -POSE.elbowBend)
  );
  const qLH = new THREE.Quaternion().setFromEuler(
    new THREE.Euler(-POSE.wristNeutral, 0, 0)
  );
  const qRH = new THREE.Quaternion().setFromEuler(
    new THREE.Euler(POSE.wristNeutral, 0, 0)
  );
  return {
    leftUpperArm:  qLUA,
    rightUpperArm: qRUA,
    leftLowerArm:  qLLA,
    rightLowerArm: qRLA,
    leftHand:      qLH,
    rightHand:     qRH,
  };
}

/* ─── Get raw bone node safely (actual Three.js scene bone) ─
 * getRawBoneNode returns the real THREE.Bone in the scene graph.
 * These survive vrm.update() — normalized nodes do not (they are proxies).
 */
function getRawBone(hd: VRM["humanoid"], name: string): THREE.Object3D | null {
  if (!hd) return null;
  try {
    // @pixiv/three-vrm v3: getRawBoneNode returns the actual scene bone
    const raw = (hd as any).getRawBoneNode?.(name);
    if (raw) return raw as THREE.Object3D;
    // Fallback: getNormalizedBoneNode if raw not available
    return hd.getNormalizedBoneNode(name as any) ?? null;
  } catch { return null; }
}

/* ─── VRM Model + Director ─────────────────────────────── */
function Model({
  state, jawEnergy, speakingRef, url,
}: {
  state: CompanionState;
  jawEnergy?: React.MutableRefObject<number>;
  speakingRef?: React.MutableRefObject<boolean>;
  url: string;
}) {
  const vrmRef = useRef<VRM | null>(null);
  const availRef = useRef<Set<string>>(new Set());
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);

  // Cached normalized bone refs — set once on load, never re-computed per frame
  const bonesRef = useRef<BoneCache>({
    leftUpperArm: null, rightUpperArm: null,
    leftLowerArm: null, rightLowerArm: null,
    leftHand: null,     rightHand: null,
    leftShoulder: null, rightShoulder: null,
  });

  // Relaxed pose quaternion targets — computed once
  const poseTargets = useRef<PoseTargets>(buildRelaxedTargets());

  // Reusable tmp quaternion — avoids per-frame allocation
  const tmpQ = useRef(new THREE.Quaternion());

  const t = useRef(0);
  const blink = useRef(2 + Math.random() * 3);
  const doubleBlink = useRef(false);
  const vowels = useRef({ aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 });
  const vowelPick = useRef(0);
  const vowelTimer = useRef(0);
  const emo = useRef<Record<string, number>>({});

  useEffect(() => {
    let ok = true;
    setFailed(false);
    const ldr = new GLTFLoader();
    ldr.crossOrigin = "anonymous";
    ldr.register(p => new VRMLoaderPlugin(p));
    ldr.load(url, gltf => {
      if (!ok) return;
      const v = gltf.userData.vrm as VRM;
      if (!v) { setFailed(true); return; }

      // Optimize
      try { VRMUtils.removeUnnecessaryVertices(v.scene); VRMUtils.removeUnnecessaryJoints(v.scene); } catch {}
      v.scene.traverse((o: THREE.Object3D) => {
        o.frustumCulled = false;
        const m = o as THREE.Mesh;
        if (m.isMesh) {
          const mat = m.material as THREE.Material;
          if (mat) mat.side = THREE.DoubleSide;
        }
      });

      // ── ORIENTATION: normalize once.
      // @pixiv/three-vrm v3 with VRM 1.0: model already faces +Z (toward camera).
      // VRM 0.x models face -Z and need VRMUtils.rotateVRM0 (Math.PI rotation).
      // DO NOT add Math.PI for VRM 1.0 — it would rotate the correctly-facing model backward.
      const vrmMeta = (v as any).meta;
      const vrmVersion: string = vrmMeta?.specVersion ?? vrmMeta?.version ?? "1.0";
      const isVrm0 = vrmVersion.startsWith("0");
      if (isVrm0) {
        // VRM 0.x: rotate to face +Z
        try { VRMUtils.rotateVRM0(v); } catch {
          v.scene.rotation.y = Math.PI;
        }
      } else {
        // VRM 1.0 in @pixiv/three-vrm v3: already faces +Z, no rotation needed
        v.scene.rotation.y = 0;
      }

      if (import.meta.env.DEV) {
        console.log("🎭 VRM orientation:", {
          vrmVersion,
          isVrm0,
          rootRotationY: v.scene.rotation.y,
          orientationNormalizationApplied: true,
          finalFacingConvention: isVrm0 ? "faces -Z (VRM 0.x default)" : "faces +Z via Math.PI (VRM 1.0)",
        });
      }

      // Auto-detect available expressions
      const em = v.expressionManager;
      if (em) {
        for (const name of Object.values(VRMExpressionPresetName)) {
          try { if (em.getExpression(name)) availRef.current.add(name); } catch {}
        }
        if (import.meta.env.DEV) console.log("🔍 VRM expressions:", [...availRef.current]);
      }

      // Disable VRM's auto look-at
      if (v.lookAt) {
        try { v.lookAt.target = null as any; } catch {}
        try { (v.lookAt as any).enabled = false; } catch {}
      }

      // ── CACHE raw humanoid bones (once, not per frame) ──
      const hd = v.humanoid;
      if (hd) {
        bonesRef.current = {
          leftUpperArm:  getRawBone(hd, "leftUpperArm"),
          rightUpperArm: getRawBone(hd, "rightUpperArm"),
          leftLowerArm:  getRawBone(hd, "leftLowerArm"),
          rightLowerArm: getRawBone(hd, "rightLowerArm"),
          leftHand:      getRawBone(hd, "leftHand"),
          rightHand:     getRawBone(hd, "rightHand"),
          leftShoulder:  getRawBone(hd, "leftShoulder"),
          rightShoulder: getRawBone(hd, "rightShoulder"),
        };

        if (import.meta.env.DEV) {
          const bc = bonesRef.current;
          console.log("🦴 Bone cache:", {
            leftUpperArm:  !!bc.leftUpperArm,
            rightUpperArm: !!bc.rightUpperArm,
            leftLowerArm:  !!bc.leftLowerArm,
            rightLowerArm: !!bc.rightLowerArm,
            leftHand:      !!bc.leftHand,
            rightHand:     !!bc.rightHand,
          });
        }
      }

      vrmRef.current = v;
      setLoaded(true);
    }, undefined, () => { if (ok) setFailed(true); });

    return () => {
      ok = false;
      // Reset bone cache on unmount
      bonesRef.current = {
        leftUpperArm: null, rightUpperArm: null,
        leftLowerArm: null, rightLowerArm: null,
        leftHand: null,     rightHand: null,
        leftShoulder: null, rightShoulder: null,
      };
      if (vrmRef.current) {
        try { VRMUtils.deepDispose(vrmRef.current.scene); } catch {}
        vrmRef.current = null;
      }
    };
  }, [url]);

  useFrame((_, dtRaw) => {
    const vrm = vrmRef.current;
    if (!vrm) return;
    const dt = Math.min(dtRaw, 0.05);
    t.current += dt;
    const em = vrm.expressionManager;
    const has = (n: string) => availRef.current.has(n);
    const set = (n: VRMExpressionPresetName, val: number) => {
      if (has(n)) { try { em!.setValue(n, val); } catch {} }
    };

    /* ══ 1. LIP-SYNC ══════════════════════════════════════════ */
    if (em) {
      const audioPlaying = speakingRef ? speakingRef.current : false;
      let energy = 0;
      if (audioPlaying && jawEnergy) energy = Math.min(1, jawEnergy.current * 1.35);

      const keys = ["aa", "ih", "ou", "ee", "oh"] as const;
      const presets = [
        VRMExpressionPresetName.Aa, VRMExpressionPresetName.Ih,
        VRMExpressionPresetName.Ou, VRMExpressionPresetName.Ee,
        VRMExpressionPresetName.Oh,
      ];

      if (energy > 0.05) {
        vowelTimer.current -= dt;
        if (vowelTimer.current <= 0) {
          vowelPick.current = Math.floor(Math.random() * 5);
          vowelTimer.current = 0.08 + Math.random() * 0.09;
        }
        for (let i = 0; i < 5; i++) {
          const target = i === vowelPick.current ? energy : 0;
          vowels.current[keys[i]] += (target - vowels.current[keys[i]]) * dt * 22;
          set(presets[i], vowels.current[keys[i]]);
        }
      } else {
        let anyOpen = false;
        for (let i = 0; i < 5; i++) {
          vowels.current[keys[i]] *= 1 - Math.min(1, dt * 28);
          if (vowels.current[keys[i]] < 0.01) vowels.current[keys[i]] = 0;
          if (vowels.current[keys[i]] > 0) anyOpen = true;
          set(presets[i], vowels.current[keys[i]]);
        }
        if (!anyOpen) vowelTimer.current = 0;
      }

      /* ══ 2. NATURAL BLINK ══════════════════════════════════ */
      blink.current -= dt;
      let bv = 0;
      if (blink.current <= 0) {
        if (blink.current < -0.13) {
          if (doubleBlink.current) { doubleBlink.current = false; blink.current = 1.5 + Math.random() * 3.5; }
          else if (Math.random() < 0.18) { doubleBlink.current = true; blink.current = -0.02; }
          else blink.current = 2 + Math.random() * 4;
        } else {
          bv = Math.sin(Math.max(0, Math.min(1, (blink.current + 0.13) / 0.13)) * Math.PI);
        }
      }
      set(VRMExpressionPresetName.Blink, bv);

      /* ══ 3. EMOTION BLEND ══════════════════════════════════ */
      const targetEmo = emotionFor(state);
      const allEmo: VRMExpressionPresetName[] = [
        VRMExpressionPresetName.Happy, VRMExpressionPresetName.Sad,
        VRMExpressionPresetName.Relaxed, VRMExpressionPresetName.Surprised,
        VRMExpressionPresetName.Angry,
      ];
      for (const key of allEmo) {
        const target = (targetEmo as any)[key] ?? 0;
        emo.current[key] = (emo.current[key] ?? 0) + (target - (emo.current[key] ?? 0)) * dt * 3;
        set(key, emo.current[key]);
      }
    }

    /* ══ 4. VRM SYSTEM UPDATE ════════════════════════════════
     * Must run before raw bone writes so spring-bone parent
     * transforms are settled. Raw bone rotations we write
     * after update() are not overwritten by the VRM system.
     */
    vrm.update(dt);

    /* ══ 5. RELAXED ARM POSE (after vrm.update) ═════════════
     * Uses cached raw bone refs (getRawBoneNode = actual THREE.Bone).
     * Raw bones survive vrm.update() — normalized proxy bones do not.
     * No scene traversal, no per-frame allocation.
     */
    const bc = bonesRef.current;
    const pt = poseTargets.current;
    // Snap instantly on first frame (t < 0.1), then blend normally
    const blendSpeed = t.current < 0.1 ? 1.0 : Math.min(1, dt * POSE.poseBlendSpeed);

    const blendBone = (bone: THREE.Object3D | null, target: THREE.Quaternion) => {
      if (!bone) return;
      bone.quaternion.slerp(target, blendSpeed);
    };

    blendBone(bc.leftUpperArm,  pt.leftUpperArm);
    blendBone(bc.rightUpperArm, pt.rightUpperArm);
    blendBone(bc.leftLowerArm,  pt.leftLowerArm);
    blendBone(bc.rightLowerArm, pt.rightLowerArm);
    blendBone(bc.leftHand,      pt.leftHand);
    blendBone(bc.rightHand,     pt.rightHand);

    // suppress unused ref warning
    void tmpQ;
  });

  if (failed || !loaded) return null;
  return <primitive object={vrmRef.current!.scene} />;
}

/* ─── Camera controller ────────────────────────────────── */
function Cam({ mode }: { mode: PresenceMode }) {
  const cfg = CAMERAS[mode] || CAMERAS.portrait;
  const c = useThree(s => s.camera);
  const set = useRef(false);

  useEffect(() => {
    set.current = false; // re-apply on mode change
  }, [mode]);

  useFrame(() => {
    if (!set.current) {
      c.position.set(...cfg.pos);
      c.fov = cfg.fov;
      c.updateProjectionMatrix();
      set.current = true;
    }
    c.lookAt(cfg.target[0], cfg.target[1], cfg.target[2]);
  });
  return null;
}

/* ─── Fallback ─────────────────────────────────────────── */
function AvatarFallback({ state }: { state: CompanionState }) {
  return (
    <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16, color: "#64748b", textAlign: "center", padding: 24 }}>
      <div style={{ width: 80, height: 80, borderRadius: "50%", background: "linear-gradient(135deg, rgba(167,243,208,0.5), rgba(103,232,249,0.5))", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "2rem", border: "2px solid rgba(255,255,255,0.8)" }}>◇</div>
      <div><div style={{ fontWeight: 700, color: "#1a1f2e" }}>HINAA</div><div style={{ fontSize: "0.72rem", marginTop: 4 }}>{state === "idle" ? "Ready" : `${state}…`}</div></div>
    </div>
  );
}

/* ─── Main ─────────────────────────────────────────────── */
interface Props {
  mode: PresenceMode; state: CompanionState;
  jawEnergy?: React.MutableRefObject<number>;
  speakingRef?: React.MutableRefObject<boolean>;
  modelUrl?: string;
  onModeChange?: (m: PresenceMode) => void;
}

export function AvatarPresence({ mode, state, jawEnergy, speakingRef, modelUrl = "/models/hinaa.vrm", onModeChange }: Props) {
  const [webglFailed, setWebglFailed] = useState(false);
  if (mode === "hidden") return null;

  const cycle = () => {
    const modes: PresenceMode[] = ["portrait", "closeup", "full"];
    onModeChange?.(modes[(modes.indexOf(mode) + 1) % modes.length]);
  };

  return (
    <div style={{ position: "relative", width: "100%", height: "100%", minHeight: 180 }}>
      <div style={{ position: "absolute", inset: 0, background: "radial-gradient(ellipse 60% 60% at 50% 38%, rgba(103,232,249,0.07) 0%, transparent 70%)", pointerEvents: "none", zIndex: 0 }} />
      {!webglFailed && (
        <Canvas
          style={{ position: "absolute", inset: 0, zIndex: 1 }}
          dpr={[1, 1.75]}
          gl={{ antialias: true, alpha: true, powerPreference: "high-performance", failIfMajorPerformanceCaveat: false }}
          onCreated={({ gl }) => { gl.domElement.addEventListener("webglcontextlost", e => { e.preventDefault(); setWebglFailed(true); }, { once: true }); }}
        >
          <Suspense fallback={null}>
            <Cam mode={mode} />
            {/* Cinematic soft lighting tuned for white materials */}
            <ambientLight intensity={0.85} color="#fffdf7" />
            <directionalLight position={[2, 3.5, 2.5]} intensity={1.4} color="#fffcf5" />
            <spotLight position={[-3, 2, 2]} intensity={1.4} color="#a7f3d0" angle={0.6} penumbra={0.6} />
            <spotLight position={[3, 1.8, -1]} intensity={1.1} color="#c4b5fd" angle={0.5} penumbra={0.6} />
            <pointLight position={[0, 1.4, 2]} intensity={0.6} color="#fff6ec" />
            <Model state={state} jawEnergy={jawEnergy} speakingRef={speakingRef} url={modelUrl} />
            <ContactShadows resolution={256} scale={2.6} blur={2.4} opacity={0.22} far={1.4} position={[0, -0.02, 0]} color="#1e293b" />
            <Environment preset="apartment" environmentIntensity={0.35} />
          </Suspense>
        </Canvas>
      )}
      {webglFailed && <AvatarFallback state={state} />}
      <div style={{ position: "absolute", bottom: 8, right: 8, zIndex: 5 }}>
        <motion.button type="button" onClick={cycle} whileHover={{ scale: 1.08 }} whileTap={{ scale: 0.92 }}
          style={{ width: 28, height: 28, borderRadius: 8, border: "1px solid rgba(255,255,255,0.6)", background: "rgba(255,255,255,0.55)", backdropFilter: "blur(8px)", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", color: "#64748b" }}
          title={`View: ${mode}`}>
          <Maximize2 size={12} />
        </motion.button>
      </div>
    </div>
  );
}

export default AvatarPresence;
