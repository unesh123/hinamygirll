"""Private local avatar inventory and import service for HINAA.

Only explicitly approved application roots and the HINAA-managed avatar folder
are scanned. The browser receives opaque IDs and browser-safe URLs, never a
Windows or user filesystem path.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import shutil
import struct
from typing import Any
from uuid import uuid4

ALLOWED_SUFFIXES = {".vrm", ".vroid", ".vsfavatar", ".glb", ".gltf"}
VRM_SUFFIXES = {".vrm", ".glb", ".gltf"}
MANIFEST_NAME = "manifest.json"


class AvatarAssetError(ValueError):
    pass


@dataclass(frozen=True)
class AvatarAssetRecord:
    asset_id: str
    display_name: str
    format: str
    source: str
    browser_url: str | None
    metadata: dict[str, Any]
    managed_file: Path | None = None

    def public(self) -> dict[str, Any]:
        return {
            "assetId": self.asset_id,
            "displayName": self.display_name,
            "format": self.format,
            "source": self.source,
            "browserUrl": self.browser_url,
            **self.metadata,
        }


class AvatarAssetService:
    def __init__(self, workspace_root: Path, project_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.project_root = project_root.resolve()
        self.managed_root = (self.workspace_root / "avatars").resolve()
        self.managed_root.mkdir(parents=True, exist_ok=True)

    @property
    def manifest_path(self) -> Path:
        return self.managed_root / MANIFEST_NAME

    def _managed_manifest(self) -> dict[str, dict[str, Any]]:
        if not self.manifest_path.exists():
            return {}
        try:
            raw = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_manifest(self, manifest: dict[str, dict[str, Any]]) -> None:
        temp = self.manifest_path.with_suffix(".tmp")
        temp.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        temp.replace(self.manifest_path)

    def _approved_roots(self) -> list[tuple[Path, str, str | None]]:
        """Only application-owned locations, never arbitrary user directories."""
        return [
            (self.project_root / "apps" / "web" / "public" / "models", "bundled", "/models"),
            (self.project_root / "apps" / "web" / "src" / "assets", "bundled", None),
            (self.project_root / "assets", "bundled", None),
            (self.project_root / "models", "bundled", None),
            (self.project_root / "public", "bundled", None),
            (self.managed_root, "managed", None),
        ]

    @staticmethod
    def _opaque_id(prefix: str, value: str) -> str:
        return f"{prefix}-{sha256(value.encode('utf-8')).hexdigest()[:20]}"

    @staticmethod
    def _glb_json(path: Path) -> dict[str, Any]:
        data = path.read_bytes()
        if len(data) < 20 or data[:4] != b"glTF":
            raise AvatarAssetError("The selected file is not a parseable GLB/VRM binary.")
        _magic, _version, total_length = struct.unpack_from("<4sII", data, 0)
        if total_length > len(data):
            raise AvatarAssetError("The selected GLB/VRM binary is truncated.")
        offset = 12
        while offset + 8 <= len(data):
            chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
            offset += 8
            if chunk_length < 0 or offset + chunk_length > len(data):
                break
            if chunk_type == 0x4E4F534A:  # JSON
                try:
                    return json.loads(data[offset: offset + chunk_length].decode("utf-8").rstrip(" \t\r\n\x00"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise AvatarAssetError("The VRM JSON metadata cannot be read.") from exc
            offset += chunk_length
        raise AvatarAssetError("The selected GLB/VRM has no JSON metadata chunk.")

    @staticmethod
    def _gltf_json(path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AvatarAssetError("The selected glTF metadata cannot be read.") from exc

    @classmethod
    def inspect_file(cls, path: Path) -> dict[str, Any]:
        suffix = path.suffix.lower()
        if suffix not in VRM_SUFFIXES:
            return cls._unsupported_metadata(suffix, "This format is catalogued but is not a browser-loadable VRM.")
        document = cls._gltf_json(path) if suffix == ".gltf" else cls._glb_json(path)
        extensions = document.get("extensions") if isinstance(document, dict) else {}
        extensions = extensions if isinstance(extensions, dict) else {}
        vrm0 = extensions.get("VRM") if isinstance(extensions.get("VRM"), dict) else None
        vrm1 = extensions.get("VRMC_vrm") if isinstance(extensions.get("VRMC_vrm"), dict) else None
        if vrm0:
            version = "0.x"
            humanoid = vrm0.get("humanoid") if isinstance(vrm0.get("humanoid"), dict) else {}
            bones = [str(item.get("bone")) for item in humanoid.get("humanBones", []) if isinstance(item, dict) and item.get("bone")]
            blend = vrm0.get("blendShapeMaster") if isinstance(vrm0.get("blendShapeMaster"), dict) else {}
            expressions = [str(item.get("presetName") or item.get("name")) for item in blend.get("blendShapeGroups", []) if isinstance(item, dict) and (item.get("presetName") or item.get("name"))]
            spring_bones = bool((vrm0.get("secondaryAnimation") or {}).get("boneGroups")) if isinstance(vrm0.get("secondaryAnimation"), dict) else False
            meta = vrm0.get("meta") if isinstance(vrm0.get("meta"), dict) else {}
        elif vrm1:
            version = "1.0"
            humanoid = vrm1.get("humanoid") if isinstance(vrm1.get("humanoid"), dict) else {}
            human_bones = humanoid.get("humanBones") if isinstance(humanoid.get("humanBones"), dict) else {}
            bones = [str(name) for name, value in human_bones.items() if isinstance(value, dict) and value.get("node") is not None]
            expression_root = vrm1.get("expressions") if isinstance(vrm1.get("expressions"), dict) else {}
            expressions = list((expression_root.get("preset") or {}).keys()) + list((expression_root.get("custom") or {}).keys())
            spring_bones = isinstance(extensions.get("VRMC_springBone"), dict)
            meta = vrm1.get("meta") if isinstance(vrm1.get("meta"), dict) else {}
        else:
            return cls._unsupported_metadata(suffix, "The asset parses as glTF but does not contain a VRM 0.x or VRM 1.0 extension.")

        lower = {name.lower() for name in expressions}
        mouth = [name for name in expressions if name.lower() in {"a", "i", "u", "e", "o", "aa", "ih", "ou", "ee", "oh", "mouthopen"}]
        blink = [name for name in expressions if "blink" in name.lower()]
        look = [name for name in expressions if "look" in name.lower()]
        humanoid_present = bool(bones)
        license_fields = [meta.get(key) for key in ("licenseName", "licenseUrl", "author", "authors", "commercialUsage", "redistribution")]
        license_present = any(value not in (None, "", [], {}) for value in license_fields)
        license_summary = "; ".join(f"{key}: {meta[key]}" for key in ("licenseName", "licenseUrl", "author", "commercialUsage", "redistribution") if meta.get(key) not in (None, "", [], {}))
        if version == "0.x" and humanoid_present:
            compatibility = "compatible_candidate"
            reason = "VRM 0.x metadata and humanoid rig detected. A real VSeeFace load test is still required."
        elif version == "1.0":
            compatibility = "incompatible"
            reason = "VRM 1.0 is a browser-compatible candidate but is not represented as VSeeFace compatible."
        else:
            compatibility = "unknown"
            reason = "The asset lacks the verified VRM 0.x humanoid requirements for VSeeFace candidacy."
        return {
            "vrmVersion": version,
            "fileSize": path.stat().st_size,
            "humanoidPresent": humanoid_present,
            "humanoidBones": sorted(bones),
            "presetExpressions": sorted(expressions),
            "customExpressions": [],
            "mouthExpressions": sorted(mouth),
            "blinkExpressions": sorted(blink),
            "lookExpressions": sorted(look),
            "springBonesPresent": spring_bones,
            "licenseMetadataPresent": license_present,
            "licenseSummary": license_summary or "No licence metadata was found in the VRM metadata.",
            "browserLoadStatus": "unknown",
            "vseeFaceCompatibility": compatibility,
            "reason": reason,
        }

    @staticmethod
    def _unsupported_metadata(suffix: str, reason: str) -> dict[str, Any]:
        return {
            "vrmVersion": "unknown",
            "fileSize": 0,
            "humanoidPresent": False,
            "humanoidBones": [],
            "presetExpressions": [],
            "customExpressions": [],
            "mouthExpressions": [],
            "blinkExpressions": [],
            "lookExpressions": [],
            "springBonesPresent": False,
            "licenseMetadataPresent": False,
            "licenseSummary": "Unavailable for this format.",
            "browserLoadStatus": "unsupported",
            "vseeFaceCompatibility": "unknown",
            "reason": reason,
        }

    def _record_for_path(self, path: Path, source: str, public_prefix: str | None, managed: dict[str, dict[str, Any]]) -> AvatarAssetRecord | None:
        if not path.is_file() or path.suffix.lower() not in ALLOWED_SUFFIXES:
            return None
        try:
            metadata = self.inspect_file(path)
        except (OSError, AvatarAssetError) as exc:
            metadata = self._unsupported_metadata(path.suffix.lower(), str(exc))
            try:
                metadata["fileSize"] = path.stat().st_size
            except OSError:
                pass
        if source == "managed":
            entry = next((value for value in managed.values() if value.get("fileName") == path.name), None)
            asset_id = str(entry.get("assetId")) if entry else self._opaque_id("managed", path.name)
            browser_url = f"/api/v1/avatar-assets/{asset_id}/file"
        else:
            try:
                relative = path.relative_to(self.project_root).as_posix()
            except ValueError:
                return None
            asset_id = self._opaque_id("bundled", relative)
            browser_url = f"{public_prefix}/{path.name}" if public_prefix and path.parent.name == "models" else None
        return AvatarAssetRecord(asset_id, path.stem, path.suffix.lower().lstrip("."), source, browser_url, metadata, path if source == "managed" else None)

    def inventory(self) -> list[dict[str, Any]]:
        managed = self._managed_manifest()
        records: list[AvatarAssetRecord] = []
        seen: set[Path] = set()
        for root, source, public_prefix in self._approved_roots():
            if not root.exists() or not root.is_dir():
                continue
            for path in root.rglob("*"):
                resolved = path.resolve()
                if resolved in seen or resolved == self.manifest_path:
                    continue
                seen.add(resolved)
                record = self._record_for_path(resolved, source, public_prefix, managed)
                if record:
                    records.append(record)
        return [record.public() for record in sorted(records, key=lambda record: (record.source, record.display_name.lower()))]

    def import_asset(self, file_name: str, source_path: Path) -> dict[str, Any]:
        suffix = Path(file_name).suffix.lower()
        if suffix not in ALLOWED_SUFFIXES:
            raise AvatarAssetError("Choose a .vrm, .vroid, .vsfavatar, .glb, or .gltf avatar asset.")
        if suffix not in VRM_SUFFIXES:
            raise AvatarAssetError("Only a parseable VRM/glTF asset can be imported for the HINAA browser renderer.")
        metadata = self.inspect_file(source_path)
        if metadata["vrmVersion"] == "unknown":
            raise AvatarAssetError(str(metadata["reason"]))
        asset_id = f"avatar-{uuid4()}"
        target_dir = (self.managed_root / asset_id).resolve()
        target_dir.mkdir(parents=True, exist_ok=False)
        safe_name = Path(file_name).name
        target = target_dir / safe_name
        shutil.copy2(source_path, target)
        manifest = self._managed_manifest()
        manifest[asset_id] = {
            "assetId": asset_id,
            "fileName": safe_name,
            "displayName": Path(safe_name).stem,
            "importedAt": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "source": "user-selected-file",
            "metadata": metadata,
        }
        self._write_manifest(manifest)
        return AvatarAssetRecord(asset_id, Path(safe_name).stem, suffix.lstrip("."), "managed", f"/api/v1/avatar-assets/{asset_id}/file", metadata, target).public()

    def resolve_managed(self, asset_id: str) -> Path | None:
        entry = self._managed_manifest().get(asset_id)
        if not entry:
            return None
        candidate = (self.managed_root / asset_id / str(entry.get("fileName", ""))).resolve()
        try:
            candidate.relative_to(self.managed_root)
        except ValueError:
            return None
        return candidate if candidate.is_file() else None

    def delete_managed(self, asset_id: str) -> bool:
        manifest = self._managed_manifest()
        entry = manifest.get(asset_id)
        if not entry:
            return False
        folder = (self.managed_root / asset_id).resolve()
        try:
            folder.relative_to(self.managed_root)
        except ValueError:
            return False
        if folder.exists():
            shutil.rmtree(folder)
        manifest.pop(asset_id, None)
        self._write_manifest(manifest)
        return True
