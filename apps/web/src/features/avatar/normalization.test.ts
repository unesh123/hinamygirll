import { describe, expect, it } from "vitest";
import * as THREE from "three";
import { normalizeVrmAvatar } from "./normalization";
import { AVATAR_REGISTRY, getAvatarById, getDefaultAvatarForCompanion } from "./avatarRegistry";

describe("Avatar Normalization & Registry", () => {
  it("normalizes a 3D mock object into canonical 1.6m anime height and grounds feet at Y=0", () => {
    // Create a mock scene with a 2-meter tall bounding box
    const scene = new THREE.Group();
    const geom = new THREE.BoxGeometry(0.5, 2.0, 0.3);
    const mat = new THREE.MeshBasicMaterial();
    const mesh = new THREE.Mesh(geom, mat);
    // Position mesh so bottom is at Y = -0.5 and top is at Y = 1.5
    mesh.position.set(0.2, 0.5, -0.1);
    scene.add(mesh);

    const mockVrm = {
      scene,
      humanoid: null,
    } as any;

    const metrics = normalizeVrmAvatar(mockVrm, 1.6);
    expect(metrics.targetHeight).toBe(1.6);
    expect(metrics.rawHeight).toBeCloseTo(2.0, 1);
    expect(metrics.scale).toBeCloseTo(1.6 / 2.0, 2);
    // Center X offset should negate center.x
    expect(metrics.offset[0]).toBeCloseTo(-0.2, 1);
    // Foot grounding offset should negate box.min.y (-0.5 -> +0.5)
    expect(metrics.offset[1]).toBeCloseTo(0.5, 1);
  });

  it("contains registry definitions for all bundled avatars with companion defaults", () => {
    expect(AVATAR_REGISTRY.length).toBeGreaterThanOrEqual(4);
    const hinaa = getDefaultAvatarForCompanion("hinaa");
    expect(hinaa.companionId).toBe("hinaa");
    expect(hinaa.fileUrl).toContain(".vrm");

    const hiro = getDefaultAvatarForCompanion("hiro");
    expect(hiro.companionId).toBe("hiro");
    expect(hiro.fileUrl).toContain(".vrm");

    const sample = getAvatarById("hinaa-schoolgirl");
    expect(sample.id).toBe("hinaa-schoolgirl");
  });

  it("normalizes based on humanoid bone landmarks with cranial cap", () => {
    const scene = new THREE.Group();
    const headNode = new THREE.Object3D();
    headNode.position.set(0, 1.4, 0);
    scene.add(headNode);

    const footNode = new THREE.Object3D();
    footNode.position.set(0, 0.0, 0);
    scene.add(footNode);

    const mockVrmWithHumanoid = {
      scene,
      humanoid: {
        getNormalizedBoneNode: (name: string) => {
          if (name === "head") return headNode;
          if (name === "leftFoot") return footNode;
          return null;
        },
      },
    } as any;

    const metrics = normalizeVrmAvatar(mockVrmWithHumanoid, 1.6);
    // 1.4m skeletal + 0.14m cranial cap = 1.54m
    expect(metrics.rawHeight).toBeCloseTo(1.54, 2);
    expect(metrics.scale).toBeCloseTo(1.6 / 1.54, 2);
  });
});
