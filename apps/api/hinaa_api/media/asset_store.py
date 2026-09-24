from __future__ import annotations

import hashlib
import io
import logging
import uuid
from pathlib import Path
from typing import Any
from .models import AssetKind, AssetRef, AssetSource

logger = logging.getLogger("hinaa.media.asset_store")

ALLOWED_IMAGE_MIMES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

ALLOWED_MIMES: dict[str, tuple[str, AssetKind]] = {
    # Images
    "image/png": (".png", AssetKind.IMAGE),
    "image/jpeg": (".jpg", AssetKind.IMAGE),
    "image/jpg": (".jpg", AssetKind.IMAGE),
    "image/webp": (".webp", AssetKind.IMAGE),
    "image/gif": (".gif", AssetKind.IMAGE),
    "image/svg+xml": (".svg", AssetKind.IMAGE),
    # Documents
    "application/pdf": (".pdf", AssetKind.DOCUMENT),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (".docx", AssetKind.DOCUMENT),
    "application/msword": (".doc", AssetKind.DOCUMENT),
    # Spreadsheets
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (".xlsx", AssetKind.SPREADSHEET),
    "application/vnd.ms-excel": (".xls", AssetKind.SPREADSHEET),
    "text/csv": (".csv", AssetKind.SPREADSHEET),
    # Text / Code
    "text/plain": (".txt", AssetKind.TEXT),
    "text/markdown": (".md", AssetKind.TEXT),
    "text/html": (".html", AssetKind.TEXT),
    "application/json": (".json", AssetKind.CODE),
    "application/javascript": (".js", AssetKind.CODE),
    "text/javascript": (".js", AssetKind.CODE),
    "text/x-python": (".py", AssetKind.CODE),
    # Audio
    "audio/wav": (".wav", AssetKind.AUDIO),
    "audio/x-wav": (".wav", AssetKind.AUDIO),
    "audio/mpeg": (".mp3", AssetKind.AUDIO),
    "audio/mp3": (".mp3", AssetKind.AUDIO),
    "audio/ogg": (".ogg", AssetKind.AUDIO),
    "audio/webm": (".webm", AssetKind.AUDIO),
    # Video
    "video/mp4": (".mp4", AssetKind.VIDEO),
    "video/webm": (".webm", AssetKind.VIDEO),
    # Archive
    "application/zip": (".zip", AssetKind.ARCHIVE),
    "application/x-zip-compressed": (".zip", AssetKind.ARCHIVE),
}

EXTENSION_MAP: dict[str, tuple[str, AssetKind]] = {
    ".png": ("image/png", AssetKind.IMAGE),
    ".jpg": ("image/jpeg", AssetKind.IMAGE),
    ".jpeg": ("image/jpeg", AssetKind.IMAGE),
    ".webp": ("image/webp", AssetKind.IMAGE),
    ".gif": ("image/gif", AssetKind.IMAGE),
    ".svg": ("image/svg+xml", AssetKind.IMAGE),
    ".pdf": ("application/pdf", AssetKind.DOCUMENT),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", AssetKind.DOCUMENT),
    ".doc": ("application/msword", AssetKind.DOCUMENT),
    ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", AssetKind.SPREADSHEET),
    ".xls": ("application/vnd.ms-excel", AssetKind.SPREADSHEET),
    ".csv": ("text/csv", AssetKind.SPREADSHEET),
    ".txt": ("text/plain", AssetKind.TEXT),
    ".md": ("text/markdown", AssetKind.TEXT),
    ".json": ("application/json", AssetKind.CODE),
    ".js": ("text/javascript", AssetKind.CODE),
    ".py": ("text/x-python", AssetKind.CODE),
    ".html": ("text/html", AssetKind.TEXT),
    ".wav": ("audio/wav", AssetKind.AUDIO),
    ".mp3": ("audio/mpeg", AssetKind.AUDIO),
    ".ogg": ("audio/ogg", AssetKind.AUDIO),
    ".mp4": ("video/mp4", AssetKind.VIDEO),
    ".webm": ("video/webm", AssetKind.VIDEO),
    ".zip": ("application/zip", AssetKind.ARCHIVE),
}

ALL_EXTENSIONS: list[str] = sorted(
    list({ext for ext, _ in ALLOWED_MIMES.values()} | set(ALLOWED_IMAGE_MIMES.values()) | {".bin"})
)

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25MB


class AssetStore:
    """Manages secure, deduplicated server-side storage of user-uploaded and generated assets."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or (Path.home() / ".hinaa" / "assets")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, AssetRef] = {}
        self._sha_map: dict[str, str] = {}  # sha256 -> asset_id

    def store_bytes(
        self,
        raw_bytes: bytes,
        filename: str | None = None,
        mime_type: str = "image/png",
        source: AssetSource = AssetSource.UPLOAD,
    ) -> AssetRef:
        """Stores raw bytes, validates MIME and size, deduplicates by SHA256, and records metadata."""
        if len(raw_bytes) > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"Attachment exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024*1024)}MB.")

        norm_mime = (mime_type or "").lower().strip()
        kind = AssetKind.IMAGE
        ext = ".bin"

        ext_candidate = Path(filename).suffix.lower() if filename else ""
        if ext_candidate in EXTENSION_MAP and (not norm_mime or norm_mime in ("application/octet-stream", "binary/octet-stream")):
            norm_mime, kind = EXTENSION_MAP[ext_candidate]
            ext = ext_candidate

        if norm_mime in ALLOWED_MIMES:
            ext, kind = ALLOWED_MIMES[norm_mime]
        else:
            # Check bytes magic headers
            if raw_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
                norm_mime, ext, kind = "image/png", ".png", AssetKind.IMAGE
            elif raw_bytes.startswith(b"\xff\xd8\xff"):
                norm_mime, ext, kind = "image/jpeg", ".jpg", AssetKind.IMAGE
            elif raw_bytes.startswith(b"RIFF") and b"WEBP" in raw_bytes[:16]:
                norm_mime, ext, kind = "image/webp", ".webp", AssetKind.IMAGE
            elif raw_bytes.startswith(b"%PDF-"):
                norm_mime, ext, kind = "application/pdf", ".pdf", AssetKind.DOCUMENT
            elif raw_bytes.startswith(b"RIFF") and b"WAVE" in raw_bytes[:16]:
                norm_mime, ext, kind = "audio/wav", ".wav", AssetKind.AUDIO
            elif raw_bytes.startswith(b"GIF8"):
                norm_mime, ext, kind = "image/gif", ".gif", AssetKind.IMAGE
            elif raw_bytes.startswith(b"PK\x03\x04"):
                if ext_candidate == ".docx":
                    norm_mime, ext, kind = "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx", AssetKind.DOCUMENT
                elif ext_candidate == ".xlsx":
                    norm_mime, ext, kind = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx", AssetKind.SPREADSHEET
                else:
                    norm_mime, ext, kind = "application/zip", ".zip", AssetKind.ARCHIVE
            elif ext_candidate in EXTENSION_MAP:
                norm_mime, kind = EXTENSION_MAP[ext_candidate]
                ext = ext_candidate
            else:
                # Try UTF-8 plain text detection
                try:
                    raw_bytes[:1024].decode("utf-8")
                    norm_mime, ext, kind = "text/plain", ".txt", AssetKind.TEXT
                except Exception:
                    raise ValueError(f"Unsupported media type: '{mime_type}'. Supported: images, PDF, DOCX, XLSX, CSV, TXT, audio, video, ZIP.")

        sha256 = hashlib.sha256(raw_bytes).hexdigest()

        # Deduplication check
        if sha256 in self._sha_map:
            existing_id = self._sha_map[sha256]
            if existing_id in self._index:
                logger.debug("Deduplicated upload for SHA256=%s -> asset_id=%s", sha256, existing_id)
                return self._index[existing_id]

        # Determine dimensions if PIL is available and it's an image
        width, height = None, None
        if kind == AssetKind.IMAGE:
            try:
                from PIL import Image
                with Image.open(io.BytesIO(raw_bytes)) as img:
                    width, height = img.size
            except Exception:
                pass

        asset_id = f"asset_{uuid.uuid4().hex[:12]}"
        asset_ref = AssetRef(
            id=asset_id,
            kind=kind,
            filename=filename,
            mime_type=norm_mime,
            size_bytes=len(raw_bytes),
            sha256=sha256,
            width=width,
            height=height,
            source=source,
            public_url=f"/v1/assets/{asset_id}/file",
        )

        file_path = self.base_dir / f"{asset_ref.id}{ext}"
        file_path.write_bytes(raw_bytes)

        self._index[asset_ref.id] = asset_ref
        self._sha_map[sha256] = asset_ref.id
        return asset_ref

    def get_asset(self, asset_id: str) -> AssetRef | None:
        if asset_id in self._index:
            return self._index[asset_id]
        if asset_id in self._sha_map:
            return self._index.get(self._sha_map[asset_id])
        
        # Disk fallback: inspect if file exists on disk
        for ext in ALL_EXTENSIONS:
            candidate = self.base_dir / f"{asset_id}{ext}"
            if candidate.exists():
                try:
                    data = candidate.read_bytes()
                    sha256 = hashlib.sha256(data).hexdigest()
                    width, height = None, None
                    mime = "application/octet-stream"
                    kind = AssetKind.IMAGE
                    if ext in EXTENSION_MAP:
                        mime, kind = EXTENSION_MAP[ext]
                    if kind == AssetKind.IMAGE:
                        try:
                            from PIL import Image
                            with Image.open(io.BytesIO(data)) as img:
                                width, height = img.size
                        except Exception:
                            pass
                    ref = AssetRef(
                        id=asset_id,
                        kind=kind,
                        filename=candidate.name,
                        mime_type=mime,
                        size_bytes=len(data),
                        sha256=sha256,
                        width=width,
                        height=height,
                        public_url=f"/v1/assets/{asset_id}/file",
                    )
                    self._index[asset_id] = ref
                    self._sha_map[sha256] = asset_id
                    return ref
                except Exception:
                    pass
        return None

    def get_file_path(self, asset_id: str) -> Path | None:
        ref = self.get_asset(asset_id)
        if not ref:
            for ext in ALL_EXTENSIONS:
                candidate = self.base_dir / f"{asset_id}{ext}"
                if candidate.exists():
                    return candidate
            return None
        ext = ALLOWED_MIMES.get(ref.mime_type, (None, None))[0] or ALLOWED_IMAGE_MIMES.get(ref.mime_type, ".bin")
        p = self.base_dir / f"{ref.id}{ext}"
        if p.exists():
            return p
        for ext_cand in ALL_EXTENSIONS:
            candidate = self.base_dir / f"{ref.id}{ext_cand}"
            if candidate.exists():
                return candidate
        return None

    def read_bytes(self, asset_id: str) -> bytes | None:
        path = self.get_file_path(asset_id)
        return path.read_bytes() if path else None

    def register_asset_metadata(
        self,
        asset_id: str,
        *,
        filename: str | None = None,
        owner_id: str | None = None,
        project_id: str | None = None,
        conversation_id: str | None = None,
        entity_ids: list[str] | None = None,
        approval_state: str | None = None,
        tags: list[str] | None = None,
        semantic_metadata: dict[str, Any] | None = None,
    ) -> AssetRef | None:
        """Enrich an asset with ownership, project, entity, and approval metadata."""
        ref = self.get_asset(asset_id)
        if not ref:
            ref = AssetRef(
                id=asset_id,
                kind=AssetKind.IMAGE,
                mime_type="image/png",
                source=AssetSource.LOCAL,
                filename=filename,
                sha256="",
                size_bytes=0,
                owner_id=owner_id,
                project_id=project_id,
                conversation_id=conversation_id,
                entity_ids=entity_ids or [],
                approval_state=approval_state or "pending",
                tags=tags or [],
                semantic_metadata=semantic_metadata or {},
            )
            self._index[asset_id] = ref
            return ref
        if filename is not None:
            ref.filename = filename
        if owner_id is not None:
            ref.owner_id = owner_id
        if project_id is not None:
            ref.project_id = project_id
        if conversation_id is not None:
            ref.conversation_id = conversation_id
        if entity_ids is not None:
            for eid in entity_ids:
                if eid not in ref.entity_ids:
                    ref.entity_ids.append(eid)
        if approval_state is not None:
            ref.approval_state = approval_state
        if tags is not None:
            for tag in tags:
                if tag not in ref.tags:
                    ref.tags.append(tag)
        if semantic_metadata is not None:
            ref.semantic_metadata.update(semantic_metadata)
        self._index[ref.id] = ref
        return ref

    def query_assets(
        self,
        *,
        owner_id: str | None = None,
        project_id: str | None = None,
        entity_id: str | None = None,
        approval_state: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
    ) -> list[AssetRef]:
        """Search assets across conversations by owner, project, entity, and approval state."""
        results: list[AssetRef] = []
        for ref in self._index.values():
            if owner_id and ref.owner_id and ref.owner_id != owner_id:
                continue
            if project_id and ref.project_id and ref.project_id != project_id:
                continue
            if entity_id:
                eid_lower = entity_id.lower()
                matches_entity = any(e.lower() == eid_lower for e in ref.entity_ids) or (
                    ref.filename and eid_lower in ref.filename.lower()
                ) or any(eid_lower in t.lower() for t in ref.tags)
                if not matches_entity:
                    continue
            if approval_state and ref.approval_state != approval_state:
                continue
            if tags:
                if not any(t in ref.tags for t in tags):
                    continue
            results.append(ref)
        # Sort approved first, then newest
        results.sort(
            key=lambda r: (1 if r.approval_state == "approved" else 0, r.created_at),
            reverse=True,
        )
        return results[:limit]


_default_asset_store: AssetStore | None = None


def get_asset_store() -> AssetStore:
    global _default_asset_store
    if _default_asset_store is None:
        _default_asset_store = AssetStore()
    return _default_asset_store

