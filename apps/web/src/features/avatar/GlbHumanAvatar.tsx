import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import { KTX2Loader } from "three/examples/jsm/loaders/KTX2Loader.js";
import type { CompanionState } from "../companion/types";
import { getLipSyncAnalyser } from "../audio/speechAnalyserTap";
import { sampleSpeechPlayback, type SpeechPlaybackBridge } from "../audio/speechPlaybackBridge";
import { computeAffectiveProfile } from "./companionExpression";
import type { AvatarPresentation } from "./avatarPresentation";
import {
  applyArkitToMorphs, buildMorphBindings, collectMorphNames, detectModelCapability,
  FaceEngine, emotionsFromAffect, matchBodyBone, visemeToLipFrame,
  type BodyBoneRole, type MorphBindings, type ModelCapability, type EmotionWeights,
} from "./face";
import { enhanceHumanMaterials } from "./humanMaterials";

export interface GlbAnatomyFrame {
  width?: number;
  depth?: number;
  centerX: number;
  headY: number;
  neckY: number;
  chestY: number;
  hipsY: number;
  minY: number;
  maxY: number;
  revision: string;
}

interface Props {
  url: string;
  presentation: AvatarPresentation;
  state: CompanionState;
  speakingRef: React.MutableRefObject<boolean>;
  jawEnergy: React.MutableRefObject<number>;
  speechBridge?: SpeechPlaybackBridge | null;
  expressionText?: string;
  planEmotion?: string;
  reducedMotion?: boolean;
  castShadows?: boolean;
  onAnatomyFrame?: (frame: GlbAnatomyFrame) => void;
  onLoadState?: (state: "loading" | "ready" | "failed") => void;
  onCapability?: (capability: ModelCapability) => void;
}

/** Real-world human height the model is normalised to before presentation scale. */
const TARGET_HEIGHT_M = 1.65;

type BoneSlot = { node: THREE.Object3D; rest: THREE.Quaternion };

export function GlbHumanAvatar({
  url, presentation, state, speakingRef, jawEnergy, speechBridge, expressionText, planEmotion,
  reducedMotion = false, castShadows = false, onAnatomyFrame, onLoadState, onCapability,
}: Props) {
  const gl = useThree((s) => s.gl);
  const group = useRef<THREE.Group>(null);
  const engineRef = useRef<FaceEngine | null>(null);
  const bindingsRef = useRef<MorphBindings | null>(null);
  const bonesRef = useRef<Partial<Record<BodyBoneRole, BoneSlot>>>({});
  const sceneRef = useRef<THREE.Object3D | null>(null);
  const emotionsRef = useRef<EmotionWeights>({});
  const emotionClock = useRef(0);
  const lipScratch = useRef({ jawOpen: 0, mouthFunnel: 0, mouthPucker: 0, mouthSmile: 0 });
  const euler = useMemo(() => new THREE.Euler(), []);
  const quat = useMemo(() => new THREE.Quaternion(), []);
  const cb = useRef({ onAnatomyFrame, onLoadState, onCapability });
  cb.current = { onAnatomyFrame, onLoadState, onCapability };

  useEffect(() => {
    let disposed = false;
    cb.current.onLoadState?.("loading");
    const loader = new GLTFLoader();
    loader.crossOrigin = "anonymous";
    loader.setMeshoptDecoder(MeshoptDecoder);
    // Basis transcoder files must be copied to /basis/ to load KTX2 textures; see docs/avatar-pipeline.md.
    const ktx2 = new KTX2Loader().setTranscoderPath("/basis/").detectSupport(gl);
    loader.setKTX2Loader(ktx2);

    loader.load(
      url,
      (gltf) => {
        if (disposed) return;
        const scene = gltf.scene;
        const meshes: THREE.Mesh[] = [];
        const bones: Partial<Record<BodyBoneRole, BoneSlot>> = {};
        scene.traverse((obj) => {
          const mesh = obj as THREE.Mesh;
          if (mesh.isMesh) {
            meshes.push(mesh);
            mesh.frustumCulled = false;
            mesh.castShadow = castShadows;
            mesh.receiveShadow = castShadows;
            // sRGB correctness: colour maps must be decoded as sRGB, data maps as linear.
            const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
            for (const m of mats as THREE.MeshStandardMaterial[]) {
              if (m.map) m.map.colorSpace = THREE.SRGBColorSpace;
              if (m.emissiveMap) m.emissiveMap.colorSpace = THREE.SRGBColorSpace;
              if (m.map) m.map.anisotropy = Math.min(8, gl.capabilities.getMaxAnisotropy());
            }
          }
          const role = matchBodyBone(obj.name);
          if (role && !bones[role]) bones[role] = { node: obj, rest: obj.quaternion.clone() };
        });
        enhanceHumanMaterials(scene);

        const capability = detectModelCapability({ isVrm: false, names: collectMorphNames(meshes) });
        bindingsRef.current = capability.hasArkit ? buildMorphBindings(meshes) : null;
        engineRef.current = new FaceEngine({ capability, reducedMotion });
        bonesRef.current = bones;
        sceneRef.current = scene;
        cb.current.onCapability?.(capability);

        // Normalise: feet on the floor, standard human height.
        const box = new THREE.Box3().setFromObject(scene);
        const size = box.getSize(new THREE.Vector3());
        const k = size.y > 0 ? TARGET_HEIGHT_M / size.y : 1;
        scene.scale.multiplyScalar(k);
        scene.updateMatrixWorld(true);
        const fitted = new THREE.Box3().setFromObject(scene);
        scene.position.y -= fitted.min.y;
        scene.position.x -= (fitted.min.x + fitted.max.x) / 2;
        scene.position.z -= (fitted.min.z + fitted.max.z) / 2;
        scene.updateMatrixWorld(true);
        group.current?.add(scene);

        const b = new THREE.Box3().setFromObject(scene);
        const y = (slot?: BoneSlot, fallback = 0) => slot ? slot.node.getWorldPosition(new THREE.Vector3()).y : fallback;
        const height = b.max.y - b.min.y;
        const headY = y(bones.head, b.max.y - height * 0.07);
        const chestY = y(bones.chest ?? bones.spine, b.min.y + height * 0.7);
        cb.current.onAnatomyFrame?.({
          width: b.max.x - b.min.x,
          depth: b.max.z - b.min.z,
          centerX: (b.min.x + b.max.x) / 2,
          headY,
          neckY: y(bones.neck, headY - height * 0.05),
          chestY,
          hipsY: y(bones.hips, b.min.y + height * 0.52),
          minY: b.min.y,
          maxY: b.max.y,
          revision: `${url}:${b.min.y.toFixed(3)}:${b.max.y.toFixed(3)}:${headY.toFixed(3)}`,
        });
        cb.current.onLoadState?.("ready");
      },
      undefined,
      () => { if (!disposed) cb.current.onLoadState?.("failed"); },
    );

    return () => {
      disposed = true;
      ktx2.dispose();
      const scene = sceneRef.current;
      if (scene) {
        scene.parent?.remove(scene);
        scene.traverse((obj) => {
          const mesh = obj as THREE.Mesh;
          if (!mesh.isMesh) return;
          mesh.geometry?.dispose();
          for (const m of Array.isArray(mesh.material) ? mesh.material : [mesh.material]) m?.dispose();
        });
      }
      sceneRef.current = null;
      engineRef.current = null;
      bindingsRef.current = null;
      bonesRef.current = {};
    };
    // Reduced-motion is read at load; the engine suppresses micro-motion for the whole session.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, gl, castShadows]);

  useFrame((_, dtRaw) => {
    const engine = engineRef.current;
    if (!engine) return;
    const dt = Math.min(dtRaw, 0.1);
    const listening = state === "listening";
    const sample = speechBridge ? sampleSpeechPlayback(speechBridge) : null;
    const speaking = !listening && (sample ? sample.speaking : speakingRef.current || state === "speaking");

    emotionClock.current -= dt;
    if (emotionClock.current <= 0) {
      emotionClock.current = 0.25;
      emotionsRef.current = emotionsFromAffect(
        computeAffectiveProfile(expressionText, state, planEmotion, 0, speaking, 0),
      );
    }

    const frame = engine.update(dt, {
      emotions: emotionsRef.current,
      speaking,
      listening,
      thinking: state === "thinking",
      speechEnergy: Math.min(1, jawEnergy.current * 3),
      analyser: speaking ? getLipSyncAnalyser() : null,
    });

    // No analyser signal (browser speech / provider without a node): fall back to text-timed visemes.
    if (speaking && !frame.audioLipSync && sample?.viseme) {
      const s = lipScratch.current;
      visemeToLipFrame(sample.viseme.mouth, sample.viseme.weight * Math.max(0.5, Math.min(1, jawEnergy.current * 3)), s);
      const a = frame.arkit;
      a.jawOpen = Math.min(1, a.jawOpen + s.jawOpen);
      a.mouthFunnel = Math.min(1, a.mouthFunnel + s.mouthFunnel);
      a.mouthPucker = Math.min(1, a.mouthPucker + s.mouthPucker);
      a.mouthSmileLeft = Math.min(1, a.mouthSmileLeft + s.mouthSmile);
      a.mouthSmileRight = Math.min(1, a.mouthSmileRight + s.mouthSmile);
    }

    if (bindingsRef.current) applyArkitToMorphs(bindingsRef.current, frame.arkit);

    const p = frame.body;
    const bones = bonesRef.current;
    const rot = (role: BodyBoneRole, x: number, y: number, z: number) => {
      const slot = bones[role];
      if (!slot) return;
      euler.set(x, y, z);
      slot.node.quaternion.copy(slot.rest).multiply(quat.setFromEuler(euler));
    };
    rot("spine", p.spinePitch, 0, p.spineRoll);
    rot("chest", p.chestPitch, 0, 0);
    rot("neck", p.headPitch * 0.4, p.headYaw * 0.4, p.headRoll * 0.4);
    rot("head", p.headPitch * 0.6 + frame.eye.gazeY * -0.05, p.headYaw * 0.6 + frame.eye.gazeX * 0.08, p.headRoll * 0.6);
    rot("shoulderLeft", 0, 0, p.shoulderLeft);
    rot("shoulderRight", 0, 0, -p.shoulderRight);
    const hips = bones.hips;
    if (hips) {
      euler.set(0, 0, p.hipsRoll);
      hips.node.quaternion.copy(hips.rest).multiply(quat.setFromEuler(euler));
    }
  });

  return (
    <group
      ref={group}
      rotation={[0, presentation.rotationY, 0]}
      position={[0, presentation.offsetY, 0]}
      scale={presentation.scale}
    />
  );
}
