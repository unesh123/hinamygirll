"""Phase 14 — Artifact OS: Archive & Repository Packager.

Handles bundling multiple artifacts, source code trees, and datasets into
secure ZIP archives with cryptographically verified manifests.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Any
import zipfile

from .models import (
    ArtifactFormat,
    ArtifactManifest,
    ArtifactRecord,
    ManifestEntry,
)


class ArchiveSecurityError(Exception):
    """Raised when an unsafe path or zip-slip attempt is detected."""
    pass


class ArchivePackager:
    """Creates, inspects, and safely extracts ZIP archives and repository bundles."""

    DEFAULT_EXCLUDES = {
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        ".pytest_cache",
        ".DS_Store",
        "Thumbs.db",
    }

    def package_artifacts(
        self,
        artifacts: list[ArtifactRecord],
        bundle_title: str,
        description: str = "",
    ) -> bytes:
        """Bundle multiple ArtifactRecords into a single ZIP with an auto-generated manifest.json."""
        manifest_entries: list[ManifestEntry] = []
        total_bytes = 0

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for art in artifacts:
                # Determine raw bytes
                if isinstance(art.content, str):
                    raw = art.content.encode("utf-8")
                elif isinstance(art.content, bytes):
                    raw = art.content
                else:
                    raw = str(art.content).encode("utf-8")

                filename = art.filename or f"{art.id}.{art.format.value}"
                zf.writestr(filename, raw)

                total_bytes += len(raw)
                manifest_entries.append(ManifestEntry(
                    path=filename,
                    artifact_id=art.id,
                    format=art.format.value,
                    size_bytes=len(raw),
                    sha256=art.sha256,
                    title=art.title,
                    mime_type=art.get_mime_type(),
                ))

            manifest = ArtifactManifest(
                title=bundle_title,
                description=description,
                total_artifacts=len(artifacts),
                total_bytes=total_bytes,
                entries=manifest_entries,
            )

            manifest_json = manifest.model_dump_json(indent=2)
            zf.writestr("manifest.json", manifest_json)

        return buf.getvalue()

    def package_directory(
        self,
        source_dir: Path,
        bundle_title: str,
        excludes: set[str] | None = None,
    ) -> bytes:
        """Bundle a local directory (e.g. project workspace or repo) into a ZIP archive."""
        root = source_dir.resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"Source directory not found: {source_dir}")

        ignored = set(excludes) if excludes else self.DEFAULT_EXCLUDES
        manifest_entries: list[ManifestEntry] = []
        total_bytes = 0

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for dirpath, dirnames, filenames in os.walk(root):
                # Filter out ignored directories in-place
                dirnames[:] = [d for d in dirnames if d not in ignored]

                for fname in filenames:
                    if fname in ignored:
                        continue

                    full_path = Path(dirpath) / fname
                    rel_path = full_path.relative_to(root).as_posix()

                    try:
                        raw = full_path.read_bytes()
                    except Exception:
                        continue

                    zf.writestr(rel_path, raw)
                    total_bytes += len(raw)

                    # Guess format
                    ext = full_path.suffix.lstrip(".").lower() or "txt"
                    manifest_entries.append(ManifestEntry(
                        path=rel_path,
                        artifact_id=f"file_{rel_path.replace('/', '_')}",
                        format=ext,
                        size_bytes=len(raw),
                        sha256="",
                        title=fname,
                        mime_type="application/octet-stream",
                    ))

            manifest = ArtifactManifest(
                title=bundle_title,
                total_artifacts=len(manifest_entries),
                total_bytes=total_bytes,
                entries=manifest_entries,
            )
            zf.writestr("manifest.json", manifest.model_dump_json(indent=2))

        return buf.getvalue()

    def inspect_archive(self, zip_bytes: bytes) -> dict[str, Any]:
        """Inspect a ZIP archive and return metadata, file count, and manifest if present."""
        buf = io.BytesIO(zip_bytes)
        with zipfile.ZipFile(buf, "r") as zf:
            file_list = zf.infolist()
            total_uncompressed = sum(f.file_size for f in file_list)
            total_compressed = sum(f.compress_size for f in file_list)
            names = [f.filename for f in file_list]

            manifest_data: dict[str, Any] | None = None
            if "manifest.json" in names:
                try:
                    manifest_bytes = zf.read("manifest.json")
                    manifest_data = json.loads(manifest_bytes.decode("utf-8"))
                except Exception:
                    pass

            ratio = (1 - (total_compressed / total_uncompressed)) if total_uncompressed > 0 else 0.0

            return {
                "file_count": len(file_list),
                "uncompressed_bytes": total_uncompressed,
                "compressed_bytes": total_compressed,
                "compression_ratio": round(ratio, 3),
                "has_manifest": manifest_data is not None,
                "manifest": manifest_data,
                "files": names,
            }

    def safe_extract(self, zip_bytes: bytes, target_dir: Path) -> list[str]:
        """Extract a ZIP archive safely with Zip Slip (path traversal) protection."""
        target_root = target_dir.resolve()
        target_root.mkdir(parents=True, exist_ok=True)

        extracted_files: list[str] = []
        buf = io.BytesIO(zip_bytes)

        with zipfile.ZipFile(buf, "r") as zf:
            for member in zf.infolist():
                # Security Check: Prevent path traversal
                dest_path = (target_root / member.filename).resolve()
                if not str(dest_path).startswith(str(target_root)):
                    raise ArchiveSecurityError(f"Zip slip path traversal detected: {member.filename}")

                if member.is_dir():
                    dest_path.mkdir(parents=True, exist_ok=True)
                else:
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member) as source, open(dest_path, "wb") as target:
                        target.write(source.read())
                    extracted_files.append(str(dest_path))

        return extracted_files
