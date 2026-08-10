/**
 * AvatarPresence — Centered avatar viewport with relaxed pose.
 * Head stays stable (no spinning). Arms down. Fast & smooth.
 */

import React, { Suspense, useState, useRef, useEffect, useMemo } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { ContactShadows } from "@react-three/drei";
import { motion } from "framer-motion";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { VRMLoaderPlugin, VRM, VRMExpressionPresetName } from "@pixiv/three-vrm";
import * as THREE from "three";
import { Maximize2 } from "lucide-react";
import type { CompanionState } from "../../features/companion/types";

export type PresenceMode = "closeup" | "portrait" | "full" | "hidden";

/* ─── Relaxed idle: arms down, elbows bent ────────────── */
const RELAXED_IDLE: Record<string, [number, number, number]> = {
  leftUpperArm:  [0.1, -0.3, 1.2],
  leftLowerArm:  [0, 0, 0.15],
  leftHand:      [-0.2, 0, 0.1],
  rightUpperArm: [0.1, 0.3, -1.2],
  rightLowerArm: [0, 0, -0.15],
  rightHand:     [-0.2, 0, -0.1],
};

/* ─── Camera per mode ──────────────────────────────────── */
const CAMERAS: Record<PresenceMode, { pos: [number, number, number]; target: [number, number, number]; fov: number }> = {
  closeup:  { pos: [0, 1.6, 0.65], target: [0, 1.55, 0], fov: 24 },
  portrait: { pos: [0, 1.35, 1.4], target: [0, 1.3, 0], fov: 28 },
  full:     { pos: [0, 0.8, 2.2], target: [0, 0.8, 0], fov: 32 },
  hidden:   { pos: [0, 0.5, 3.0], target: [0, 0.5, 0], fov: 35 },
};

/* ─── VRM Model ────────────────────────────────────────── */
function Model({
  url, state, isSpeaking, jawEnergy, mode,
}: {
  url: string; state: CompanionState; isSpeaking: boolean;
  jawEnergy?: React.MutableRefObject<number>;
  mode: PresenceMode;
}) {
  const vrmRef = useRef<VRM | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const timeRef = useRef(0);
  const blinkRef = useRef(2 + Math.random() * 3);
  const mouthRef = useRef(0);

  useEffect(() => {
    let ok = true;
    setFailed(false);
    const ldr = new GLTFLoader();
    ldr.crossOrigin = "anonymous";
    ldr.register(p => new VRMLoaderPlugin(p));

    ldr.load(url, gltf => {
      if (!ok) return;
      const v = gltf.userData.vrm as VRM;
      if (!v) return;
      v.scene.traverse((o: THREE.Object3D) => {
        o.frustumCulled = false;
        if ((o as THREE.Mesh).isMesh) ((o as THREE.Mesh).material as THREE.Material).side = THREE.DoubleSide;
      });
      v.scene.rotation.y = Math.PI;
      vrmRef.current = v;
      setLoaded(true);
    }, undefined, () => { if (ok) setFailed(true); });
    return () => { ok = false; };
  }, [url]);

  useFrame((_, dt) => {
    const vrm = vrmRef.current;
    if (!vrm) return;
    const d = Math.min(dt, 0.1);
    timeRef.current += d;
    const t = timeRef.current;
    const hd = vrm.humanoid;
    const em = vrm.expressionManager;

    if (!hd || !em) { vrm.update(d); return; }

    // ── Lip sync ──────────────────────────────────────
    let tm = 0;
    if (isSpeaking && jawEnergy) tm = Math.min(0.9, jawEnergy.current * 1.2);
    mouthRef.current += (tm - mouthRef.current) * d * 16;
    try { em.setValue(VRMExpressionPresetName.Aa, mouthRef.current); } catch {}

    // ── Blink ──────────────────────────────────────────
    blinkRef.current -= d;
    let bv = 0;
    if (blinkRef.current <= 0) {
      if (blinkRef.current < -0.12) blinkRef.current = 2 + Math.random() * 4;
      else bv = Math.sin(Math.max(0, Math.min(1, (blinkRef.current + 0.12) / 0.12)) * Math.PI);
    }
    try { em.setValue(VRMExpressionPresetName.Blink, bv); } catch {}

    // ── Subtle emotion ─────────────────────────────────
    try {
      if (state === "speaking") em.setValue(VRMExpressionPresetName.Happy, 0.1);
      else if (state === "error") em.setValue(VRMExpressionPresetName.Sad, 0.08);
    } catch {}

    vrm.update(d);

    // ── Apply relaxed idle AFTER update (prevents T-pose) ──
    // Use SET not ADD — prevents accumulation/spinning
    for (const [bn, r] of Object.entries(RELAXED_IDLE)) {
      const raw = (hd as any).getRawBoneNode?.(bn) as THREE.Bone | null;
      const norm = hd.getNormalizedBoneNode(bn as any);
      const bone = raw || norm;
      if (bone) bone.rotation.set(r[0], r[1], r[2]);
    }
    // Elbows bent
    const le = (hd as any).getRawBoneNode?.("leftLowerArm") || hd.getNormalizedBoneNode("leftLowerArm" as any);
    const re = (hd as any).getRawBoneNode?.("rightLowerArm") || hd.getNormalizedBoneNode("rightLowerArm" as any);
    if (le) le.rotation.set(0, 0, 0.35);
    if (re) re.rotation.set(0, 0, -0.35);

    // ── Breathing: chest only, SET not ADD ─────────────
    const chest = hd.getNormalizedBoneNode("chest" as any);
    if (chest) chest.rotation.x = Math.sin(t * 1.4) * 0.005;

    // ── Head: SET absolute value, no accumulation ──────
    const head = hd.getNormalizedBoneNode("head");
    if (head) {
      head.rotation.set(
        Math.sin(t * 0.4) * 0.01,  // tiny pitch
        Math.sin(t * 0.25) * 0.02, // tiny yaw — SET, not +=
        Math.sin(t * 0.35) * 0.005 // tiny roll
      );
    }
  });

  if (failed) return null;
  if (!loaded) return null;
  return <primitive object={vrmRef.current!.scene} />;
}

/* ─── Camera ───────────────────────────────────────────── */
function Cam({ mode }: { mode: PresenceMode }) {
  const cfg = CAMERAS[mode] || CAMERAS.portrait;
  const c = useThree(s => s.camera);
  const pRef = useRef(new THREE.Vector3(...cfg.pos));
  const tRef = useRef(new THREE.Vector3(...cfg.target));

  useEffect(() => {
    pRef.current.set(...cfg.pos);
    tRef.current.set(...cfg.target);
  }, [mode]);

  useFrame((_, dt) => {
    const smooth = 1 - Math.exp(-Math.min(dt, 0.1) * 4);
    c.position.lerp(pRef.current, smooth);
    c.lookAt(tRef.current);
    if (c instanceof THREE.PerspectiveCamera) {
      c.fov += (cfg.fov - c.fov) * smooth;
      c.updateProjectionMatrix();
    }
  });
  return null;
}

/* ─── Fallback ──────────────────────────────────────────── */
function AvatarFallback({ state }: { state: CompanionState }) {
  return (
    <div style={{
      width: "100%", height: "100%", display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center", gap: 16,
      color: "#64748b", fontSize: "0.85rem", textAlign: "center", padding: 24,
    }}>
      <div style={{
        width: 80, height: 80, borderRadius: "50%",
        background: "linear-gradient(135deg, rgba(167,243,208,0.5), rgba(103,232,249,0.5))",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: "2rem", border: "2px solid rgba(255,255,255,0.8)",
        boxShadow: "0 4px 20px rgba(16,185,129,0.2)",
      }}>◇</div>
      <div>
        <div style={{ fontWeight: 700, color: "#1a1f2e" }}>HINAA</div>
        <div style={{ fontSize: "0.72rem", marginTop: 4 }}>
          {state === "idle" ? "Ready" : state === "listening" ? "Listening…" :
           state === "speaking" ? "Speaking…" : state === "thinking" ? "Thinking…" : "Present"}
        </div>
      </div>
    </div>
  );
}

/* ─── Main ─────────────────────────────────────────────── */
interface Props {
  mode: PresenceMode;
  state: CompanionState;
  jawEnergy?: React.MutableRefObject<number>;
  modelUrl?: string;
  onModeChange?: (m: PresenceMode) => void;
}

export function AvatarPresence({
  mode, state, jawEnergy,
  modelUrl = "/models/hinaa.vrm",
  onModeChange,
}: Props) {
  const [webglFailed, setWebglFailed] = useState(false);

  if (mode === "hidden") return null;

  const cycle = () => {
    const modes: PresenceMode[] = ["closeup", "portrait", "full"];
    const idx = modes.indexOf(mode);
    onModeChange?.(modes[(idx + 1) % modes.length]);
  };

  return (
    <div style={{ position: "relative", width: "100%", height: "100%", minHeight: 180 }}>
      {/* Soft halo */}
      <div style={{ position: "absolute", inset: 0, background: "radial-gradient(ellipse 60% 60% at 50% 40%, rgba(103,232,249,0.06) 0%, transparent 70%)", pointerEvents: "none", zIndex: 0 }} />

      {!webglFailed && (
        <Canvas
          style={{ position: "absolute", inset: 0, zIndex: 1 }}
          dpr={[1, 1.5]}
          gl={{ antialias: true, alpha: true, preserveDrawingBuffer: false, powerPreference: "default", failIfMajorPerformanceCaveat: false }}
          onCreated={({ gl }) => {
            gl.domElement.addEventListener("webglcontextlost", (e) => { e.preventDefault(); setWebglFailed(true); }, { once: true });
          }}
        >
          <Suspense fallback={null}>
            <Cam mode={mode} />
            <ambientLight intensity={1.0} color="#fffdf7" />
            <directionalLight position={[2, 3, 2]} intensity={1.2} color="#fffcf5" />
            <spotLight position={[-3, 1.5, 2]} intensity={1.5} color="#a7f3d0" angle={0.6} penumbra={0.5} />
            <spotLight position={[3, 1.5, -1]} intensity={1.2} color="#c4b5fd" angle={0.5} penumbra={0.5} />
            <pointLight position={[0, 1.2, 2]} intensity={0.5} color="#fff8f0" />
            <Model url={modelUrl} state={state} isSpeaking={state === "speaking"} jawEnergy={jawEnergy} mode={mode} />
            <ContactShadows resolution={256} scale={3} blur={2} opacity={0.2} far={1.5} position={[0, -1.0, 0]} color="#1e293b" />
          </Suspense>
        </Canvas>
      )}
      {webglFailed && <AvatarFallback state={state} />}

      {/* Mode toggle */}
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
