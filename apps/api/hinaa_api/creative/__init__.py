"""
HINAA OS — Creative Package
Integrates Phase 09 multimodal intelligence, jobs, assets, and legacy creative registries.
"""

from .models import (
    AssetMetadata,
    CapabilityEntry,
    CapabilityMatrix,
    CapabilityStatus,
    CreativeEvent,
    CreativeJobRecord,
    CreativeJobSpec,
    CreativeOperation,
    JobState,
    MediaType,
)
from .registry import (
    CANONICAL_MODELS,
    CreativeModel,
    CreativeModelRegistry,
    CreativeRegistry,
    creative_registry,
)
from .policy import CreativeSecurityPolicy
from .assets.manager import CreativeAssetManager, creative_asset_manager
from .providers.base import CreativeProvider
from .providers.local_engine import LocalCreativeEngine, local_creative_engine
from .providers.timeline_exporter import TimelineVideoExporter, timeline_video_exporter
from .providers.comfy_provider import ComfyUIProvider, comfyui_provider
from .providers.video_generative_provider import GenerativeVideoProvider, generative_video_provider
from .jobs.store import PersistentJobStore, persistent_creative_job_store
from .jobs.service import CreativeService, creative_service

# Legacy backward-compatibility exports
from .budget_manager import MagnificBudgetManager, PacingMode
from .creative_job import CreativeJob, CreativeJobStore
from .magnific_client import MagnificClient
from .flows import MagnificFlowsEngine, magnific_flows_engine, inspect_flow_safety
from .cost_policy import CostPolicyEngine, PolicyDecision, CostPolicyEvaluation

__all__ = [
    # Phase 09 Models & Enums
    "JobState",
    "MediaType",
    "CreativeOperation",
    "CapabilityStatus",
    "CreativeEvent",
    "AssetMetadata",
    "CreativeJobSpec",
    "CreativeJobRecord",
    "CapabilityEntry",
    "CapabilityMatrix",
    # Registry
    "CreativeRegistry",
    "creative_registry",
    "CreativeModelRegistry",
    "CreativeModel",
    "CANONICAL_MODELS",
    # Policy
    "CreativeSecurityPolicy",
    # Assets
    "CreativeAssetManager",
    "creative_asset_manager",
    # Providers
    "CreativeProvider",
    "LocalCreativeEngine",
    "local_creative_engine",
    "TimelineVideoExporter",
    "timeline_video_exporter",
    "ComfyUIProvider",
    "comfyui_provider",
    "GenerativeVideoProvider",
    "generative_video_provider",
    # Jobs & Service
    "PersistentJobStore",
    "persistent_creative_job_store",
    "CreativeService",
    "creative_service",
    # Legacy
    "MagnificBudgetManager",
    "PacingMode",
    "CreativeJob",
    "CreativeJobStore",
    "MagnificClient",
    "MagnificFlowsEngine",
    "magnific_flows_engine",
    "inspect_flow_safety",
    "CostPolicyEngine",
    "PolicyDecision",
    "CostPolicyEvaluation",
]
