"""Phase 14 — Artifact OS: Core Data Models.

Defines first-class artifact entities, formats, types, manifests, and metadata
for HINAA's universal artifact engine.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class ArtifactType(str, Enum):
    DOCUMENT = "document"          # Reports, articles, dossiers, notes
    PRESENTATION = "presentation"  # Slide decks, pitches, reviews
    SPREADSHEET = "spreadsheet"    # Tabular sheets, financial models, datasets
    CODE = "code"                  # Source code files, scripts, configs
    ARCHIVE = "archive"            # ZIP packages, repositories, file bundles
    DIAGRAM = "diagram"            # Flowcharts, architecture maps, charts
    IMAGE = "image"                # Rendered images, visual mockups
    DATA = "data"                  # JSON, YAML, CSV raw data


class ArtifactFormat(str, Enum):
    MD = "md"
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    ZIP = "zip"
    HTML = "html"
    JSON = "json"
    CSV = "csv"
    TEXT = "txt"
    PNG = "png"
    SVG = "svg"


class ArtifactStatus(str, Enum):
    DRAFT = "draft"
    GENERATING = "generating"
    VERIFIED = "verified"
    PUBLISHED = "published"
    ARCHIVED = "archived"


MIME_TYPE_MAP: dict[ArtifactFormat, str] = {
    ArtifactFormat.MD: "text/markdown; charset=utf-8",
    ArtifactFormat.PDF: "application/pdf",
    ArtifactFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ArtifactFormat.PPTX: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ArtifactFormat.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ArtifactFormat.ZIP: "application/zip",
    ArtifactFormat.HTML: "text/html; charset=utf-8",
    ArtifactFormat.JSON: "application/json; charset=utf-8",
    ArtifactFormat.CSV: "text/csv; charset=utf-8",
    ArtifactFormat.TEXT: "text/plain; charset=utf-8",
    ArtifactFormat.PNG: "image/png",
    ArtifactFormat.SVG: "image/svg+xml",
}


class ArtifactMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    author: str = "HINAA"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
    mime_type: str = "text/plain"
    language: str | None = None
    license: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ArtifactRecord(BaseModel):
    """Universal Artifact entity representing any generated, uploaded, or compiled output."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"art_{uuid4().hex[:12]}")
    user_id: str
    project_id: str | None = None
    conversation_id: str | None = None
    task_id: str | None = None
    step_id: str | None = None
    parent_artifact_id: str | None = None

    artifact_type: ArtifactType = ArtifactType.DOCUMENT
    format: ArtifactFormat = ArtifactFormat.MD
    title: str
    filename: str

    content: str | bytes = ""
    size_bytes: int = 0
    sha256: str = ""

    status: ArtifactStatus = ArtifactStatus.VERIFIED
    metadata: ArtifactMetadata = Field(default_factory=lambda: ArtifactMetadata(title=""))
    version: int = 1

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def compute_hash_and_size(self) -> None:
        """Compute sha256 checksum and size in bytes."""
        if isinstance(self.content, str):
            raw = self.content.encode("utf-8")
        elif isinstance(self.content, bytes):
            raw = self.content
        else:
            raw = str(self.content).encode("utf-8")

        self.size_bytes = len(raw)
        self.sha256 = hashlib.sha256(raw).hexdigest()

    def get_mime_type(self) -> str:
        return MIME_TYPE_MAP.get(self.format, "application/octet-stream")


class ManifestEntry(BaseModel):
    path: str
    artifact_id: str
    format: str
    size_bytes: int
    sha256: str
    title: str
    mime_type: str


class ArtifactManifest(BaseModel):
    """Manifest describing bundled artifacts or an exported repository archive."""
    model_config = ConfigDict(extra="ignore")

    bundle_id: str = Field(default_factory=lambda: f"bundle_{uuid4().hex[:10]}")
    title: str
    description: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    generator: str = "HINAA Frontier OS / Artifact Engine v2"
    total_artifacts: int = 0
    total_bytes: int = 0
    entries: list[ManifestEntry] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
