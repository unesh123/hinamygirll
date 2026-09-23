"""What HINAA actually produced, read from the files she left on disk.

The document library indexed ``*.metadata.json`` sidecars rather than the
documents themselves, so a rendered file was only listable if its writer also
managed to write the sidecar next to it. 161 PDFs sat in the documents root
while the library listed a dozen, because the sidecar write was gated on a
userId the browser turn path never resolves. A file on disk is the artifact;
the sidecar only describes it.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("hinaa.artifacts.inventory")

# Suffix -> the format token the UI labels a row with.
DOCUMENT_SUFFIXES = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".pptx": "pptx",
    ".xlsx": "xlsx",
    ".csv": "csv",
    ".md": "markdown",
    ".txt": "text",
    ".html": "html",
}

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}

# A kind that names the container, not a format, so it matches every file.
WILDCARD_KINDS = {"document", "file", "artifact", "export", ""}


def document_roots() -> list[Path]:
    """Every directory a document tool writes into, anchored to ``__file__``.

    Two roots because the reportlab tool and the document tool resolve their
    data directory differently. Both are absolute: a cwd-relative entry here
    used to duplicate these paths when launched from the repo root and lose
    them when launched from ``apps/api``.
    """
    here = Path(__file__).resolve().parent.parent
    return [
        (here / "data" / "documents").resolve(),
        (here.parent / "data" / "documents").resolve(),
    ]


def _label_for(path: Path) -> str:
    """Best honest title for a file with no sidecar.

    Writers name files ``{docId}_{filename}``; the doc id is a random token, so
    only the tail reads like a title. Punctuation becomes spaces rather than
    being dropped, because a filename is a weak source and losing words from it
    would be worse than a slightly awkward label.
    """
    stem = path.stem
    _, _, tail = stem.partition("_")
    candidate = tail or stem
    for separator in ("-", "_", "."):
        candidate = candidate.replace(separator, " ")
    return " ".join(candidate.split()).strip().title() or stem


def _clamp_limit(limit: int | None, default: int = 200, ceiling: int = 500) -> int:
    try:
        return max(1, min(int(limit), ceiling))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def list_document_artifacts(
    kind: str | None = None,
    limit: int = 200,
    roots: Sequence[Path] | None = None,
) -> list[dict[str, object]]:
    """Durable documents across every root, newest first, sidecar-enriched.

    ``kind`` filters on the format token (``pdf``, ``docx``, ...). A document
    whose sidecar is missing or unreadable is still listed with what the file
    itself proves -- size and mtime -- and reports ``indexed: False`` so the UI
    can say the title is a filename guess instead of presenting a guess as a
    recorded fact.
    """
    page = _clamp_limit(limit)

    wanted = kind.strip().lower() if kind else None
    entries: list[dict[str, object]] = []
    seen: set[Path] = set()

    for root in roots if roots is not None else document_roots():
        if not root.exists():
            continue
        try:
            candidates = [
                path
                for path in root.iterdir()
                if path.is_file() and path.suffix.lower() in DOCUMENT_SUFFIXES
            ]
        except OSError as error:
            logger.warning("Document root %s could not be listed: %s", root, error)
            continue

        for path in candidates:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            fmt = DOCUMENT_SUFFIXES[path.suffix.lower()]
            if wanted and wanted not in {fmt} | WILDCARD_KINDS:
                continue

            meta: dict[str, object] = {}
            sidecar = path.with_suffix(".metadata.json")
            if sidecar.is_file():
                try:
                    loaded = json.loads(sidecar.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        meta = loaded
                except (OSError, json.JSONDecodeError):
                    meta = {}

            stat = path.stat()
            doc_id = str(meta.get("docId") or path.stem)
            entry: dict[str, object] = {
                "id": doc_id,
                "docId": doc_id,
                "kind": "document",
                "format": meta.get("format") or fmt,
                "title": meta.get("title") or meta.get("filename") or _label_for(path),
                "filename": meta.get("filename") or path.name,
                "downloadUrl": meta.get("downloadUrl") or f"/api/v1/generated-docs/{doc_id}",
                "fileSizeKb": meta.get("fileSizeKb") or round(stat.st_size / 1024, 1),
                # Only from the sidecar -- a PDF's page count cannot be read off
                # the filename, so an unindexed document reports none.
                "pageCount": meta.get("pageCount"),
                "topic": meta.get("topic"),
                "contentSource": meta.get("contentSource"),
                "ownerId": meta.get("ownerId"),
                "indexed": bool(meta),
                "createdAt": meta.get("createdAt")
                or datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            }
            entries.append(entry)

    entries.sort(key=lambda item: str(item.get("createdAt") or ""), reverse=True)
    return entries[:page]


def image_roots() -> list[Path]:
    from ..config import DATA_DIR

    return [(DATA_DIR / "images").resolve()]


def list_image_artifacts(
    limit: int = 50,
    roots: Sequence[Path] | None = None,
) -> list[dict[str, object]]:
    """Generated images on disk, newest first.

    ``prompt`` is left None because it lives in the database, not in the file
    name; callers that know the prompt (``/v1/generated-images``) fill it in.
    """
    page = _clamp_limit(limit, default=50, ceiling=200)
    entries: list[dict[str, object]] = []
    seen: set[Path] = set()

    for root in roots if roots is not None else image_roots():
        if not root.exists():
            continue
        try:
            candidates = [
                path
                for path in root.iterdir()
                if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
            ]
        except OSError as error:
            logger.warning("Image root %s could not be listed: %s", root, error)
            continue

        for path in candidates:
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            stat = path.stat()
            entries.append(
                {
                    "id": path.name,
                    "kind": "image",
                    "filename": path.name,
                    "url": f"/api/v1/generated-images/{path.name}",
                    "downloadUrl": f"/api/v1/generated-images/{path.name}",
                    "prompt": None,
                    "created_at": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                    "sizeKb": round(stat.st_size / 1024, 1),
                }
            )

    entries.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return entries[:page]
