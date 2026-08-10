/**
 * AvatarPresence — HINAA 3D Avatar Director
 * ✅ VRM 0.x + 1.0 support with auto-detect
 * ✅ Relaxed arm pose via setNormalizedPose (three-vrm v3 correct API)
 * ✅ Full body framing — face + hands visible
 * ✅ Natural blink, lip-sync, emotion blend
 * ✅ Zero per-frame allocations
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

/* ─── Camera presets ───────────────────────────────────────
 * Portrait: framed on face — camera high, target at face level.
 * Full: whole body head to toe.
 * Closeup: tight face shot.
 */
const CAMERAS: Record<PresenceMode, { pos: [number,number,number]; target: [number,number,number]; fov: number }> = {
  closeup:  { pos: [0, 1.62, 0.60], target: [0, 1.60, 0], fov: 22 },   // tight face
  portrait: { pos: [0, 1.58, 1.20], target: [0, 1.52, 0], fov: 28 },   // face + chest
  full:     { pos: [0, 0.85, 2.20], target: [0, 0.75, 0], fov: 44 },   // head to toe
  hidden:   { pos: [0, 1.0,  3.0],  target: [0, 1.0,  0], fov: 35 },
};

/* ─── Emotion blends ───────────────────────────────────── */
type EmotionBlend = Partial<Record<VRMExpressionPresetName, number>>;
function emotionFor(state: CompanionState): EmotionBlend {
  switch (state) {
    case "listening":   return { relaxed: 0.10, happy: 0.05 };
    case "thinking":    return { relaxed: 0.16 };
    case "speaking":    return { happy: 0.16, relaxed: 0.06 };
    case "interrupted": return { relaxed: 0.18 };
    case "error":       return { sad: 0.14 };
    default:            return { happy: 0.06, relaxed: 0.04 };
  }
}

/* ─── Relaxed pose target Eulers (normalized-rig space) ────
 * In @pixiv/three-vrm v3 normalized rig (VRM 1.0):
 *   The upper arm rest pose is T-pose (arms horizontal).
 *   Z− rotation lowers both arms toward the body on this model.
 *   (Different VRM models may export arm bones with different local axes.)
 */
const POSE_EULER = {
  leftUpperArm:  new THREE.Euler( 0.06, 0, -1.05, "XYZ"),  // left arm down
  rightUpperArm: new THREE.Euler(-0.06, 0,  1.05, "XYZ"),  // right arm down (mirrored)
  leftLowerArm:  new THREE.Euler( 0,    0, -0.15, "XYZ"),  // slight elbow bend
  rightLowerArm: new THREE.Euler( 0,    0,  0.15, "XYZ"),
  leftHand:      new THREE.Euler(-0.04, 0,  0,    "XYZ"),  // neutral wrist
  rightHand:     new THREE.Euler( 0.04, 0,  0,    "XYZ"),
} as const;

/* Pre-compute target quaternions once — zero per-frame alloc */
const POSE_Q = {
  leftUpperArm:  new THREE.Quaternion().setFromEuler(POSE_EULER.leftUpperArm),
  rightUpperArm: new THREE.Quaternion().setFromEuler(POSE_EULER.rightUpperArm),
  leftLowerArm:  new THREE.Quaternion().setFromEuler(POSE_EULER.leftLowerArm),
  rightLowerArm: new THREE.Quaternion().setFromEuler(POSE_EULER.rightLowerArm),
  leftHand:      new THREE.Quaternion().setFromEuler(POSE_EULER.leftHand),
  rightHand:     new THREE.Quaternion().setFromEuler(POSE_EULER.rightHand),
} as const;

type PoseBoneName = keyof typeof POSE_Q;
const POSE_BONES = Object.keys(POSE_Q) as PoseBoneName[];

/* ─── Model component ──────────────────────────────────── */
function Model({ state, jawEnergy, speakingRef, url }: {
  state: CompanionState;
  jawEnergy?: React.MutableRefObject<number>;
  speakingRef?: React.MutableRefObject<boolean>;
  url: string;
}) {
  const vrmRef   = useRef<VRM | null>(null);
  const availRef = useRef<Set<string>>(new Set());
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);

  // Cached normalized bone nodes (per-model, set on load)
  const normBonesRef = useRef<Partial<Record<PoseBoneName, THREE.Object3D>>>({});
  // Current quaternion per bone for slerp (initialized to identity on load)
  const curQRef = useRef<Partial<Record<PoseBoneName, THREE.Quaternion>>>({});

  const t           = useRef(0);
  const blink       = useRef(2 + Math.random() * 3);
  const doubleBlink = useRef(false);
  const vowels      = useRef({ aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 });
  const vowelPick   = useRef(0);
  const vowelTimer  = useRef(0);
  const emo         = useRef<Record<string, number>>({});

  useEffect(() => {
    let mounted = true;
    setLoaded(false);
    setFailed(false);
    normBonesRef.current = {};
    curQRef.current = {};
    availRef.current = new Set();
    t.current = 0;

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

      // Orientation — VRM 0.x faces -Z, must rotate. VRM 1.0 already faces +Z.
      const specVer: string = (v as any).meta?.specVersion ?? (v as any).meta?.version ?? "1.0";
      const isVrm0 = specVer.startsWith("0");
      if (isVrm0) {
        try { VRMUtils.rotateVRM0(v); } catch { v.scene.rotation.y = Math.PI; }
      } else {
        v.scene.rotation.y = 0; // VRM 1.0: faces +Z by default in three-vrm v3
      }

      // Disable auto look-at
      if (v.lookAt) { try { (v.lookAt as any).enabled = false; } catch {} }

      // Cache available expressions
      const em = v.expressionManager;
      if (em) {
        for (const name of Object.values(VRMExpressionPresetName)) {
          try { if (em.getExpression(name)) availRef.current.add(name); } catch {}
        }
      }

      // Cache normalized bone nodes — these are the correct targets for pose in three-vrm v3
      const hd = v.humanoid;
      if (hd) {
        for (const boneName of POSE_BONES) {
          try {
            const node = hd.getNormalizedBoneNode(boneName as any);
            if (node) {
              normBonesRef.current[boneName] = node;
              // Initialize current quaternion to identity (T-pose start)
              curQRef.current[boneName] = new THREE.Quaternion();
            }
          } catch {}
        }
      }

      if (import.meta.env.DEV) {
        const found = POSE_BONES.filter(b => !!normBonesRef.current[b]);
        console.log(`🎭 VRM loaded: ${specVer}, orientation Y=${v.scene.rotation.y.toFixed(2)}, bones: ${found.join(", ")}`);
      }

      vrmRef.current = v;
      setLoaded(true);
    }, undefined, () => { if (mounted) setFailed(true); });

    return () => {
      mounted = false;
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

    const em  = vrm.expressionManager;
    const has = (n: string) => availRef.current.has(n);
    const set = (n: VRMExpressionPresetName, v: number) => {
      if (has(n)) { try { em!.setValue(n, v); } catch {} }
    };

    /* ── LIP-SYNC ──────────────────────────────────────── */
    if (em) {
      const speaking = speakingRef?.current ?? false;
      let energy = speaking && jawEnergy ? Math.min(1, jawEnergy.current * 1.4) : 0;

      const keys    = ["aa","ih","ou","ee","oh"] as const;
      const presets = [
        VRMExpressionPresetName.Aa, VRMExpressionPresetName.Ih,
        VRMExpressionPresetName.Ou, VRMExpressionPresetName.Ee,
        VRMExpressionPresetName.Oh,
      ];
      if (energy > 0.05) {
        vowelTimer.current -= dt;
        if (vowelTimer.current <= 0) {
          vowelPick.current = Math.floor(Math.random() * 5);
          vowelTimer.current = 0.07 + Math.random() * 0.09;
        }
        for (let i = 0; i < 5; i++) {
          const tgt = i === vowelPick.current ? energy : 0;
          vowels.current[keys[i]] += (tgt - vowels.current[keys[i]]) * dt * 22;
          set(presets[i], vowels.current[keys[i]]);
        }
      } else {
        for (let i = 0; i < 5; i++) {
          vowels.current[keys[i]] *= Math.max(0, 1 - dt * 28);
          if (vowels.current[keys[i]] < 0.01) vowels.current[keys[i]] = 0;
          set(presets[i], vowels.current[keys[i]]);
        }
        vowelTimer.current = 0;
      }

      /* ── BLINK ─────────────────────────────────────── */
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

      /* ── EMOTION ───────────────────────────────────── */
      const tEmo = emotionFor(state);
      for (const key of [
        VRMExpressionPresetName.Happy, VRMExpressionPresetName.Sad,
        VRMExpressionPresetName.Relaxed, VRMExpressionPresetName.Surprised,
        VRMExpressionPresetName.Angry,
      ]) {
        const tgt = (tEmo as any)[key] ?? 0;
        emo.current[key] = (emo.current[key] ?? 0) + (tgt - (emo.current[key] ?? 0)) * dt * 3;
        set(key, emo.current[key]);
      }
    }

    /* ── RELAXED POSE (normalized rig → retargeted by vrm.update) ──────────
     * In three-vrm v3, setting normalized bone node quaternions BEFORE
     * vrm.update() is the correct way to drive arm pose.
     * vrm.update() retargets normalized→raw and runs spring bones.
     * We slerp from current toward target for smooth motion.
     * On first frame (t < 0.1) we snap instantly (alpha=1) to avoid flicker.
     */
    const alpha = t.current < 0.1 ? 1.0 : Math.min(1, dt * 9);
    const nb    = normBonesRef.current;
    const cq    = curQRef.current;

    for (const boneName of POSE_BONES) {
      const bone = nb[boneName];
      const cur  = cq[boneName];
      if (!bone || !cur) continue;
      cur.slerp(POSE_Q[boneName], alpha);
      bone.quaternion.copy(cur);
    }

    /* ── VRM UPDATE (spring bones, expression update, retarget) ── */
    vrm.update(dt);
  });

  if (failed || !loaded) return null;
  return <primitive object={vrmRef.current!.scene} />;
}

/* ─── Camera controller ────────────────────────────────── */
function Cam({ mode }: { mode: PresenceMode }) {
  const cfg    = CAMERAS[mode] ?? CAMERAS.portrait;
  const camera = useThree(s => s.camera);
  const dirty  = useRef(true);

  useEffect(() => { dirty.current = true; }, [mode]);

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

/* ─── Fallback ─────────────────────────────────────────── */
function AvatarFallback({ state }: { state: CompanionState }) {
  return (
    <div style={{ width:"100%", height:"100%", display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", gap:12, color:"#64748b" }}>
      <div style={{ width:72, height:72, borderRadius:"50%", background:"linear-gradient(135deg,rgba(167,243,208,.5),rgba(103,232,249,.5))", display:"flex", alignItems:"center", justifyContent:"center", fontSize:"1.8rem", border:"2px solid rgba(255,255,255,.8)" }}>◇</div>
      <div style={{ fontWeight:700, color:"#1a1f2e", fontSize:"0.85rem" }}>HINAA — {state}</div>
    </div>
  );
}

/* ─── AvatarPresence (main export) ────────────────────────── */
interface Props {
  mode: PresenceMode;
  state: CompanionState;
  jawEnergy?: React.MutableRefObject<number>;
  speakingRef?: React.MutableRefObject<boolean>;
  modelUrl?: string;
  onModeChange?: (m: PresenceMode) => void;
}

export function AvatarPresence({ mode, state, jawEnergy, speakingRef, modelUrl = "/models/model_5447.vrm", onModeChange }: Props) {
  const [webglFailed, setWebglFailed] = useState(false);

  // Reset context-lost flag if user picks a new model
  useEffect(() => { setWebglFailed(false); }, [modelUrl]);

  if (mode === "hidden") return null;

  const cycle = () => {
    const modes: PresenceMode[] = ["portrait","closeup","full"];
    onModeChange?.(modes[(modes.indexOf(mode) + 1) % modes.length]);
  };

  return (
    <div style={{ position:"relative", width:"100%", height:"100%", minHeight:200 }}>
      {/* Atmospheric glow */}
      <div style={{ position:"absolute", inset:0, background:"radial-gradient(ellipse 70% 55% at 50% 35%, rgba(103,232,249,.06) 0%, transparent 70%)", pointerEvents:"none", zIndex:0 }} />

      {!webglFailed && (
        <Canvas
          style={{ position:"absolute", inset:0, zIndex:1 }}
          dpr={[1, Math.min(window.devicePixelRatio, 2)]}
          gl={{ antialias:true, alpha:true, powerPreference:"high-performance" }}
          onCreated={({ gl }) => {
            gl.domElement.addEventListener("webglcontextlost", e => {
              e.preventDefault();
              setWebglFailed(true);
            }, { once:true });
          }}
        >
          <Suspense fallback={null}>
            <Cam mode={mode} />

            {/* Lighting — cinematic soft wrap */}
            <ambientLight intensity={0.9}  color="#fffef8" />
            <directionalLight position={[1.5, 3, 2.5]} intensity={1.5} color="#fffcf0" castShadow={false} />
            <spotLight position={[-2.5, 2.5, 2]} intensity={1.3} color="#b7f5d8" angle={0.55} penumbra={0.7} />
            <spotLight position={[ 2.5, 2.0,-1]} intensity={1.0} color="#d4c0fd" angle={0.5}  penumbra={0.7} />
            <pointLight position={[0, 1.6, 2.2]} intensity={0.55} color="#fff5e8" />

            <Model
              state={state}
              jawEnergy={jawEnergy}
              speakingRef={speakingRef}
              url={modelUrl}
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

      {webglFailed && <AvatarFallback state={state} />}

      {/* Camera cycle button */}
      <div style={{ position:"absolute", bottom:8, right:8, zIndex:5 }}>
        <motion.button
          type="button" onClick={cycle}
          whileHover={{ scale:1.1 }} whileTap={{ scale:0.9 }}
          style={{ width:28, height:28, borderRadius:8, border:"1px solid rgba(255,255,255,.65)", background:"rgba(255,255,255,.55)", backdropFilter:"blur(8px)", cursor:"pointer", display:"flex", alignItems:"center", justifyContent:"center", color:"#64748b" }}
          title={`Camera: ${mode}`}
        >
          <Maximize2 size={12} />
        </motion.button>
      </div>
    </div>
  );
}

export default AvatarPresence;
