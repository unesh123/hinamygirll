"""Base Search Adapter Interface for Grounded Research."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence
from ..models import Source


class BaseSearchAdapter(ABC):
    """Abstract provider adapter for web and enterprise document search."""

    @abstractmethod
    async def search(self, query: str, *, limit: int = 5, requesting_user_id: str | None = None) -> list[Source]:
        """Executes a search query and returns normalized Sources."""
        raise NotImplementedError
