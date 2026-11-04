"""
HINAA OS — Phase 09: Creative Provider Base Interface
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from ..models import CreativeJobRecord, CreativeJobSpec, CapabilityEntry, CreativeOperation


class CreativeProvider(ABC):
    """Abstract interface for all creative generation/editing engines."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique provider identifier."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Determines whether the provider is currently operational."""
        pass

    @abstractmethod
    def supported_operations(self) -> List[CreativeOperation]:
        """Returns operations supported by this provider."""
        pass

    @abstractmethod
    async def execute_job(self, job: CreativeJobRecord) -> bytes:
        """Executes the creative job and returns raw output bytes."""
        pass

    @abstractmethod
    async def cancel_job(self, provider_job_id: str) -> bool:
        """Cancels an in-flight job on the provider if supported."""
        pass
