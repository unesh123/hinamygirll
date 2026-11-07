import { describe, expect, it } from "vitest";
import * as THREE from "three";
import {
  ARKIT_BLENDSHAPES, FaceEngine, detectModelCapability, applyVrmFaceFrame, matchBodyBone,
  visemeToLipFrame, seededRng, VRM_LEGACY_OWNED, type Vowel,
} from "./index";
import { enhanceHumanMaterial } from "../humanMaterials";
import { AVATAR_REGISTRY, getAvatarFormat, registerAvatar } from "../avatarRegistry";
import { defaultAvatarPresentation } from "../avatarPresentation";

const BINS = 512;
const aaSpectrum = () => {
  const s = new Float32Array(BINS).fill(0.22);
  for (let i = 0; i < BINS; i++) {
    const hz = (i * 24000) / BINS;
    s[i] = Math.max(s[i], 0.85 * Math.exp(-0.5 * ((hz - 800) / 90) ** 2), 0.85 * Math.exp(-0.5 * ((hz - 1250) / 120) ** 2));
  }
  return s;
};
const fakeAnalyser = () => ({
  frequencyBinCount: BINS,
  context: { sampleRate: 48000 },
  getByteFrequencyData(buf: Uint8Array) { const s = aaSpectrum(); for (let i = 0; i < BINS; i++) buf[i] = Math.round(s[i] * 255); },
}) as unknown as AnalyserNode;

const vowelPreset: Record<Vowel, string> = { aa: "aa", ih: "ih", ou: "ou", ee: "ee", oh: "oh" };

describe("VRM face driver", () => {
  it("overrides text-timed vowels with the audio estimate and drives jaw", () => {
    const cap = detectModelCapability({ isVrm: true, names: ["happy", "aa"] });
    const engine = new FaceEngine({ capability: cap, rng: seededRng(3) });
    const analyser = fakeAnalyser();
    const writes: Record<string, number> = {};
    const mouthWeights: Record<Vowel, number> = { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 };
    for (let i = 0; i < 40; i++) {
      const frame = engine.update(0.016, { speaking: true, analyser });
      applyVrmFaceFrame(frame, cap, { em: { setValue() {} }, set: (n, v) => { writes[n] = v; }, vowelPreset, mouthWeights });
    }
    expect(writes.aa).toBeGreaterThan(0.2);
    expect(writes.jawOpen).toBeGreaterThan(0.2);
    expect(mouthWeights.aa).toBeCloseTo(writes.aa, 6);
  });
  it("leaves legacy-owned channels alone on PerfectSync rigs and drives the rest", () => {
    const names = ARKIT_BLENDSHAPES.map((n) => n[0].toUpperCase() + n.slice(1));
    const cap = detectModelCapability({ isVrm: true, names });
    const engine = new FaceEngine({ capability: cap, rng: seededRng(3) });
    engine.update(0.016, { speaking: false, emotions: { surprise: 1 } });
    let frame = engine.update(0.016, { speaking: false });
    for (let i = 0; i < 60; i++) frame = engine.update(0.016, { speaking: false });
    const written: Record<string, number> = {};
    applyVrmFaceFrame(frame, cap, { em: { setValue: (n, v) => { written[n] = v; } }, set: () => {}, vowelPreset, mouthWeights: { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 } });
    expect(written.BrowInnerUp).toBeGreaterThan(0.2);
    expect("EyeBlinkLeft" in written).toBe(false);
    expect("JawOpen" in written).toBe(false);
    expect(VRM_LEGACY_OWNED.has("jawOpen")).toBe(true);
  });
  it("adds only micro flickers on preset-only rigs", () => {
    const cap = detectModelCapability({ isVrm: true, names: ["happy"] });
    const set: Record<string, number> = {};
    const frame = new FaceEngine({ capability: cap }).update(0.016, { speaking: false });
    frame.microVrm.happy = 0.1;
    applyVrmFaceFrame(frame, cap, { em: { setValue() {}, getValue: () => 0.3 }, set: (n, v) => { set[n] = v; }, vowelPreset, mouthWeights: { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 } });
    expect(set.happy).toBeCloseTo(0.4, 6);
  });
});

describe("text-timed viseme fallback", () => {
  it("opens the jaw most for aa and rounds lips for ou", () => {
    const aa = { jawOpen: 0, mouthFunnel: 0, mouthPucker: 0, mouthSmile: 0 };
    const ou = { ...aa };
    const closed = { ...aa, jawOpen: 1 };
    visemeToLipFrame("aa", 1, aa);
    visemeToLipFrame("ou", 1, ou);
    visemeToLipFrame("closed", 1, closed);
    expect(aa.jawOpen).toBeGreaterThan(ou.jawOpen);
    expect(ou.mouthPucker).toBeGreaterThan(0.4);
    expect(closed.jawOpen).toBe(0);
  });
});

describe("rig bone names", () => {
  it.each([
    ["mixamorig:Hips", "hips"], ["mixamorig:Spine2", "chest"], ["CC_Base_Head", "head"],
    ["Neck", "neck"], ["LeftShoulder", "shoulderLeft"], ["mixamorig:RightShoulder", "shoulderRight"],
  ])("maps %s → %s", (name, role) => expect(matchBodyBone(name)).toBe(role));
  it("ignores unrelated nodes", () => expect(matchBodyBone("Wolf3D_Hair")).toBeNull());
});

describe("human materials", () => {
  it("upgrades skin to sheen, eyes to clearcoat, and leaves toon alone", () => {
    const skin = enhanceHumanMaterial(new THREE.MeshStandardMaterial({ name: "Skin_Body" }), "Body") as THREE.MeshPhysicalMaterial;
    expect(skin).toBeInstanceOf(THREE.MeshPhysicalMaterial);
    expect(skin.sheen).toBeGreaterThan(0);
    const eye = enhanceHumanMaterial(new THREE.MeshStandardMaterial({ name: "Eye_L" }), "EyeLeft") as THREE.MeshPhysicalMaterial;
    expect(eye.clearcoat).toBe(1);
    const basic = new THREE.MeshBasicMaterial();
    expect(enhanceHumanMaterial(basic)).toBe(basic);
  });
});

describe("avatar registry formats", () => {
  it("flags capability/license and infers GLB format", () => {
    expect(AVATAR_REGISTRY.every((a) => a.capability && a.license)).toBe(true);
    expect(AVATAR_REGISTRY.find((a) => a.fileUrl === "/models/hinaa.vrm")?.license).toBe("non-commercial");
    expect(getAvatarFormat("/models/hinaa.vrm")).toBe("vrm");
    expect(getAvatarFormat("/models/human.glb")).toBe("glb");
    registerAvatar({ id: "test-human", name: "t", description: "t", fileUrl: "/models/x-no-ext", companionId: "hinaa", format: "glb", capability: "glb-arkit", license: "licensed" });
    expect(getAvatarFormat("/models/x-no-ext")).toBe("glb");
    AVATAR_REGISTRY.splice(AVATAR_REGISTRY.findIndex((a) => a.id === "test-human"), 1);
  });
  it("faces GLBs forward by default", () => {
    expect(defaultAvatarPresentation("/models/human.glb").rotationY).toBe(0);
  });
});
