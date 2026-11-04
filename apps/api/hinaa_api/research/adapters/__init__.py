"""Search Adapters for Grounded Research."""

from .base import BaseSearchAdapter
from .mock_adapter import MockSearchAdapter, MOCK_CORPUS
from .live_adapter import LiveSearchAdapter

__all__ = [
    "BaseSearchAdapter",
    "MockSearchAdapter",
    "LiveSearchAdapter",
    "MOCK_CORPUS",
]
