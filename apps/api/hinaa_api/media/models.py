from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class AssetKind(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    SPREADSHEET = "spreadsheet"
    TEXT = "text"
    CODE = "code"
    ARCHIVE = "archive"


class MessageAttachment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    asset_id: str
    kind: AssetKind = AssetKind.IMAGE
    mime_type: str = "image/png"
    filename: str = "attachment"
    size_bytes: int = 0
    sha256: str = ""
    ordinal: int = 0
    role: str | None = None
    url: str | None = None


class AssetSource(str, Enum):
    UPLOAD = "upload"
    URL = "url"
    STOCK = "stock"
    GENERATED = "generated"


class AssetRef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"asset_{uuid.uuid4().hex[:12]}")
    kind: AssetKind = AssetKind.IMAGE
    source: AssetSource = AssetSource.UPLOAD

    filename: str | None = None
    mime_type: str
    size_bytes: int
    sha256: str

    width: int | None = None
    height: int | None = None

    public_url: str | None = None
    created_at: float = Field(default_factory=time.time)


class ProviderImageInput(BaseModel):
    """Normalized provider-agnostic reference image payload."""
    model_config = ConfigDict(extra="ignore")

    bytes_data: bytes | None = None
    mime_type: str = "image/png"
    public_url: str | None = None
    role: str | None = None  # "character", "style", "background", "subject"
    asset_id: str | None = None


class MediaResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    operation: str = "image"
    provider: str
    model: str | None = None

    status: Literal["queued", "running", "completed", "failed"] = "completed"
    task_id: str | None = None

    asset_ref: AssetRef | None = None
    assets: list[AssetRef] = Field(default_factory=list)
    credits_used: int = 0
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
