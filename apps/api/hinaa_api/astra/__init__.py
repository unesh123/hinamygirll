"""HINA ASTRA — Multimodal Cognitive Operating System.

Universal architecture uniting perception, entity continuity, capability retrieval,
executive routing, and honest execution telemetry into a single observable runtime.
"""

from .compiler import AstraContextCompiler
from .entities import (
    EntityBrainService,
    EntityExtractor,
    EntityMention,
    EntityState,
    ReferenceResolver,
    SalienceTracker,
)
from .events import AstraEventBus
from .registry import AstraCapabilityRegistry, global_capability_registry
from .router import AstraExecutiveRouter
from .runtime import AstraRuntime
from .types import (
    ActiveEntity,
    ArtifactReference,
    AstraAttachment,
    AstraContext,
    AstraEvent,
    AstraInput,
    AstraMemory,
    AstraRequest,
    AstraRoute,
    ClientInfo,
    ContextBudget,
    RouteDecision,
    WorkspaceContext,
)

__all__ = [
    "AstraAttachment",
    "AstraCapabilityRegistry",
    "AstraContext",
    "AstraContextCompiler",
    "AstraEvent",
    "AstraEventBus",
    "AstraExecutiveRouter",
    "AstraInput",
    "AstraMemory",
    "AstraRequest",
    "AstraRoute",
    "AstraRuntime",
    "ClientInfo",
    "ContextBudget",
    "EntityBrainService",
    "EntityExtractor",
    "EntityMention",
    "EntityState",
    "ReferenceResolver",
    "RouteDecision",
    "SalienceTracker",
    "WorkspaceContext",
    "global_capability_registry",
]
