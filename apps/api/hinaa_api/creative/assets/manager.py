"""
HINAA OS — Phase 09: Creative Asset Storage Manager
Authoritative storage, hash validation, tenant isolation, and non-destructive versioning.
"""

from __future__ import annotations

import hashlib
import io
import mimetypes
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PIL import Image

from ..models import AssetMetadata, CreativeOperation, MediaType


class CreativeAssetManager:
    """Manages immutable creative assets, tenant boundaries, and non-destructive edits."""

    def __init__(self, storage_root: Optional[Path] = None) -> None:
        if storage_root is None:
            from ...config import DATA_DIR
            self.storage_root = DATA_DIR / "creative_assets"
        else:
            self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        self._assets: Dict[str, AssetMetadata] = {}

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitizes filename while preserving Unicode/Devanagari characters."""
        # Remove path separators
        clean = Path(filename).name
        # Strip null bytes and non-printable control characters
        clean = re.sub(r"[\x00-\x1f\x7f]", "", clean)
        # Prevent traversal
        clean = clean.replace("..", "").strip()
        if not clean:
            clean = f"asset_{uuid.uuid4().hex[:8]}"
        return clean

    def _verify_magic_bytes(self, data: bytes) -> Tuple[MediaType, str]:
        """Validates file signatures for PNG, JPEG, MP4, WebM."""
        if len(data) < 8:
            raise ValueError("Asset data is too small to determine file signature.")

        # PNG: 89 50 4E 47 0D 0A 1A 0A
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return MediaType.IMAGE, "image/png"

        # JPEG: FF D8 FF
        if data.startswith(b"\xff\xd8\xff"):
            return MediaType.IMAGE, "image/jpeg"

        # WebM: 1A 45 DF A3
        if data.startswith(b"\x1a\x45\xdf\xa3"):
            return MediaType.VIDEO, "video/webm"

        # MP4: ftyp in first 12 bytes
        if len(data) >= 12 and data[4:8] == b"ftyp":
            return MediaType.VIDEO, "video/mp4"

        # Fallback check via PIL for image formats
        try:
            with Image.open(io.BytesIO(data)) as img:
                fmt = img.format.lower() if img.format else "png"
                mime = f"image/{fmt}"
                return MediaType.IMAGE, mime
        except Exception:
            pass

        raise ValueError("Unsupported or corrupt media file signature. Allowed: PNG, JPEG, MP4, WebM.")

    def store_asset(
        self,
        data: bytes,
        filename: str,
        operation: CreativeOperation,
        provider: str,
        model_version: str,
        tenant_id: str = "default_tenant",
        user_id: str = "default_user",
        prompt: Optional[str] = None,
        prompt_ne: Optional[str] = None,
        seed: Optional[int] = None,
        parent_asset_id: Optional[str] = None,
        mask_sha256: Optional[str] = None,
        workflow_id: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        fps: Optional[float] = None,
        codec: Optional[str] = None,
    ) -> AssetMetadata:
        """Stores media bytes immutably under tenant directory."""
        media_type, mime_type = self._verify_magic_bytes(data)
        safe_name = self._sanitize_filename(filename)
        sha256 = hashlib.sha256(data).hexdigest()
        asset_id = f"asset-{uuid.uuid4().hex[:12]}"

        # Tenant boundary directory
        tenant_dir = self.storage_root / tenant_id
        tenant_dir.mkdir(parents=True, exist_ok=True)

        # File extension
        ext = Path(safe_name).suffix.lower()
        if not ext:
            ext = ".png" if media_type == MediaType.IMAGE else ".mp4"
        disk_filename = f"{asset_id}_{safe_name}"
        file_path = tenant_dir / disk_filename

        # Write immutable asset
        file_path.write_bytes(data)

        # Inspect dimensions
        width = 0
        height = 0
        if media_type == MediaType.IMAGE:
            try:
                with Image.open(io.BytesIO(data)) as img:
                    width, height = img.size
            except Exception:
                pass

        # Version tracking
        version_idx = 1
        is_deriv = False
        if parent_asset_id and parent_asset_id in self._assets:
            parent = self._assets[parent_asset_id]
            version_idx = parent.version_index + 1
            is_deriv = True

        meta = AssetMetadata(
            asset_id=asset_id,
            tenant_id=tenant_id,
            user_id=user_id,
            filename=safe_name,
            media_type=media_type,
            mime_type=mime_type,
            width=width,
            height=height,
            file_size_bytes=len(data),
            sha256_hash=sha256,
            created_at=datetime.now(timezone.utc).isoformat(),
            operation=operation,
            provider=provider,
            model_version=model_version,
            prompt=prompt,
            prompt_ne=prompt_ne,
            seed=seed,
            parent_asset_id=parent_asset_id,
            mask_sha256=mask_sha256,
            workflow_id=workflow_id,
            duration_seconds=duration_seconds,
            fps=fps,
            codec=codec,
            is_derivative=is_deriv,
            version_index=version_idx,
        )

        self._assets[asset_id] = meta
        return meta

    def get_asset_metadata(self, asset_id: str, tenant_id: str) -> Optional[AssetMetadata]:
        meta = self._assets.get(asset_id)
        if not meta or meta.tenant_id != tenant_id:
            return None
        return meta

    def get_asset_path(self, asset_id: str, tenant_id: str) -> Optional[Path]:
        meta = self.get_asset_metadata(asset_id, tenant_id)
        if not meta:
            return None
        tenant_dir = self.storage_root / tenant_id
        disk_filename = f"{asset_id}_{meta.filename}"
        p = (tenant_dir / disk_filename).resolve()
        # Path containment assertion
        if not str(p).startswith(str(self.storage_root.resolve())):
            raise PermissionError("Path traversal boundary violation detected.")
        if not p.exists():
            return None
        return p

    def get_asset_bytes(self, asset_id: str, tenant_id: str) -> Optional[bytes]:
        p = self.get_asset_path(asset_id, tenant_id)
        if not p:
            return None
        return p.read_bytes()

    def list_assets(self, tenant_id: str, user_id: Optional[str] = None, limit: int = 50) -> List[AssetMetadata]:
        results = [
            m for m in self._assets.values()
            if m.tenant_id == tenant_id and (user_id is None or m.user_id == user_id)
        ]
        results.sort(key=lambda x: x.created_at, reverse=True)
        return results[:limit]


creative_asset_manager = CreativeAssetManager()
