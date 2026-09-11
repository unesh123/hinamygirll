import * as THREE from "three";
import { VRM, VRMHumanBoneName } from "@pixiv/three-vrm";

export interface AvatarCalibration {
  height?: number;
  armAngleOffset?: number;
  positionOffset?: [number, number, number];
}

export interface NormalizedAvatarMetrics {
  scale: number;
  offset: [number, number, number];
  rawHeight: number;
  targetHeight: number;
}

/** Standard anime humanoid target height in meters. */
export const CANONICAL_AVATAR_HEIGHT = 1.6;

/**
 * Normalizes any VRM model (regardless of origin, height, or bone orientation):
 * 1. Measures skeletal height from humanoid landmarks (Head to LeftFoot/RightFoot + cranial cap)
 * 2. Uses THREE.Box3 for exact floor grounding (Y = 0) and root centering (X = 0, Z = 0)
 * 3. Scales character to standard 1.6m canonical height (or custom calibration)
 * 4. Relaxes extreme T-poses into natural companion rest stance
 */
export function normalizeVrmAvatar(
  vrm: VRM,
  targetHeight: number = CANONICAL_AVATAR_HEIGHT,
  calibration?: AvatarCalibration,
): NormalizedAvatarMetrics {
  // Update matrix world to ensure accurate coordinates
  vrm.scene.updateMatrixWorld(true);

  const box = new THREE.Box3().setFromObject(vrm.scene);
  const size = new THREE.Vector3();
  box.getSize(size);
  const center = new THREE.Vector3();
  box.getCenter(center);

  let rawHeight = 0;

  // 1. Skeletal landmark measurement (immune to tall hairstyles, hats, high heels)
  const humanoid = vrm.humanoid;
  if (humanoid) {
    try {
      const headBone = humanoid.getNormalizedBoneNode(VRMHumanBoneName.Head);
      const leftFoot = humanoid.getNormalizedBoneNode(VRMHumanBoneName.LeftFoot);
      const rightFoot = humanoid.getNormalizedBoneNode(VRMHumanBoneName.RightFoot);

      if (headBone && (leftFoot || rightFoot)) {
        const headWorld = new THREE.Vector3();
        headBone.getWorldPosition(headWorld);

        let groundY = 0;
        if (leftFoot && rightFoot) {
          const lPos = new THREE.Vector3();
          const rPos = new THREE.Vector3();
          leftFoot.getWorldPosition(lPos);
          rightFoot.getWorldPosition(rPos);
          groundY = Math.min(lPos.y, rPos.y);
        } else if (leftFoot) {
          const lPos = new THREE.Vector3();
          leftFoot.getWorldPosition(lPos);
          groundY = lPos.y;
        } else if (rightFoot) {
          const rPos = new THREE.Vector3();
          rightFoot.getWorldPosition(rPos);
          groundY = rPos.y;
        }

        // Cranial cap: head bone pivot is at ear/eye level; add ~14cm for skull/crown
        const skeletalHeight = Math.abs(headWorld.y - groundY) + 0.14;
        if (skeletalHeight > 0.4 && skeletalHeight < 3.0) {
          rawHeight = skeletalHeight;
        }
      }
    } catch {
      // Fallback to Box3 if bone extraction encounters unique rig mappings
    }
  }

  // Fallback to Box3 size if skeletal height was unavailable
  if (rawHeight <= 0.1) {
    rawHeight = size.y > 0.1 ? size.y : targetHeight;
  }

  const effectiveTargetHeight = calibration?.height ?? targetHeight;
  const scale = effectiveTargetHeight / rawHeight;

  // Grounding offset: lock feet to Y=0, center horizontally
  const offsetX = -center.x + (calibration?.positionOffset?.[0] ?? 0);
  const offsetY = -box.min.y + (calibration?.positionOffset?.[1] ?? 0);
  const offsetZ = -center.z + (calibration?.positionOffset?.[2] ?? 0);

  // Apply companion rest pose if model is in extreme T-pose/A-pose
  if (humanoid) {
    try {
      const leftArm = humanoid.getNormalizedBoneNode(VRMHumanBoneName.LeftUpperArm);
      const rightArm = humanoid.getNormalizedBoneNode(VRMHumanBoneName.RightUpperArm);
      const leftLowerArm = humanoid.getNormalizedBoneNode(VRMHumanBoneName.LeftLowerArm);
      const rightLowerArm = humanoid.getNormalizedBoneNode(VRMHumanBoneName.RightLowerArm);

      const armOffset = calibration?.armAngleOffset ?? 0;

      if (leftArm && rightArm) {
        const isVrm1 = Boolean(vrm.meta?.metaVersion?.startsWith("1"));
        // In VRM 1.0 left arm extends along +X (negative Z lowers arm).
        // In VRM 0.x left arm extends along -X (positive Z lowers arm).
        const armZSign = isVrm1 ? -1 : 1;
        if (Math.abs(leftArm.rotation.z) < 0.8 || Math.abs(rightArm.rotation.z) < 0.8) {
          leftArm.rotation.set(0.08, 0, (1.22 - armOffset) * armZSign);
          rightArm.rotation.set(0.08, 0, (-1.22 + armOffset) * armZSign);
          if (leftLowerArm) {
            leftLowerArm.rotation.set(0, 0.15 * -armZSign, 0.1 * armZSign);
          }
          if (rightLowerArm) {
            rightLowerArm.rotation.set(0, -0.15 * -armZSign, -0.1 * armZSign);
          }
        }
      }
    } catch {
      // Non-fatal if rig has specialized humanoid hierarchy
    }
  }

  return {
    scale,
    offset: [offsetX, offsetY, offsetZ],
    rawHeight,
    targetHeight: effectiveTargetHeight,
  };
}
