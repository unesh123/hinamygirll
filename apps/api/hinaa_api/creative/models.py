"""
HINAA OS — Phase 09: Creative Models and Domain Contracts
Authoritative schemas for multimodal intelligence, job lifecycle, and asset provenance.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class JobState(str, Enum):
    QUEUED = "QUEUED"
    PREPARING = "PREPARING"
    RUNNING = "RUNNING"
    ENCODING = "ENCODING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    BLOCKED_UNAVAILABLE = "BLOCKED_UNAVAILABLE"


class MediaType(str, Enum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    ANIMATION = "ANIMATION"


class CreativeOperation(str, Enum):
    TEXT_TO_IMAGE = "TEXT_TO_IMAGE"
    IMAGE_TO_IMAGE = "IMAGE_TO_IMAGE"
    INPAINT = "INPAINT"
    OUTPAINT = "OUTPAINT"
    REMOVE_BACKGROUND = "REMOVE_BACKGROUND"
    TEXT_TO_VIDEO = "TEXT_TO_VIDEO"
    IMAGE_TO_VIDEO = "IMAGE_TO_VIDEO"
    TIMELINE_EXPORT = "TIMELINE_EXPORT"


class CapabilityStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    BLOCKED = "BLOCKED"
    CONFIG_REQUIRED = "CONFIG_REQUIRED"


class CreativeEvent(BaseModel):
    event_id: str
    job_id: str
    sequence_id: int
    timestamp: str
    state: JobState
    progress_percent: float = Field(0.0, ge=0.0, le=100.0)
    label: str
    details: Dict[str, Any] = Field(default_factory=dict)


class AssetMetadata(BaseModel):
    asset_id: str
    tenant_id: str
    user_id: str
    filename: str
    media_type: MediaType
    mime_type: str
    width: int
    height: int
    file_size_bytes: int
    sha256_hash: str
    created_at: str
    operation: CreativeOperation
    provider: str
    model_version: str
    prompt: Optional[str] = None
    prompt_ne: Optional[str] = None
    seed: Optional[int] = None
    parent_asset_id: Optional[str] = None
    mask_sha256: Optional[str] = None
    workflow_id: Optional[str] = None
    duration_seconds: Optional[float] = None
    fps: Optional[float] = None
    codec: Optional[str] = None
    is_derivative: bool = False
    version_index: int = 1


class CreativeJobSpec(BaseModel):
    operation: CreativeOperation
    prompt: str
    prompt_ne: Optional[str] = None
    negative_prompt: Optional[str] = None
    width: int = Field(512, ge=64, le=4096)
    height: int = Field(512, ge=64, le=4096)
    aspect_ratio: str = "1:1"
    seed: Optional[int] = None
    steps: int = Field(20, ge=1, le=150)
    guidance_scale: float = Field(7.5, ge=1.0, le=30.0)
    source_asset_id: Optional[str] = None
    mask_asset_id: Optional[str] = None
    timeline_frames: Optional[List[str]] = None
    fps: float = Field(24.0, ge=1.0, le=60.0)
    duration_seconds: float = Field(3.0, ge=0.1, le=60.0)
    idempotency_key: Optional[str] = None
    user_id: str = "default_user"
    tenant_id: str = "default_tenant"


class CreativeJobRecord(BaseModel):
    job_id: str
    tenant_id: str
    user_id: str
    trace_id: str
    idempotency_key: Optional[str] = None
    spec: CreativeJobSpec
    state: JobState = JobState.QUEUED
    provider: str
    provider_job_id: Optional[str] = None
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_reason: Optional[str] = None
    error_code: Optional[str] = None
    progress_percent: float = 0.0
    progress_label: str = "Queued"
    output_asset_ids: List[str] = Field(default_factory=list)
    output_assets: List[AssetMetadata] = Field(default_factory=list)
    telemetry: Dict[str, Any] = Field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 2


class CapabilityEntry(BaseModel):
    operation: CreativeOperation
    status: CapabilityStatus
    provider: str
    model: str
    hardware_target: str
    cost_credits_estimate: int
    description_en: str
    description_ne: str
    limitations: List[str] = Field(default_factory=list)


class CapabilityMatrix(BaseModel):
    discovered_at: str
    gpu_name: Optional[str] = None
    vram_total_mb: int = 0
    vram_free_mb: int = 0
    ram_available_gb: float = 0.0
    disk_free_gb: float = 0.0
    ffmpeg_available: bool = False
    ffmpeg_version: Optional[str] = None
    comfyui_available: bool = False
    comfyui_url: Optional[str] = None
    capabilities: Dict[CreativeOperation, CapabilityEntry]
