"""Phase 14 — Artifact OS: Exporter Base Protocol."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..document_ast import DocumentAST
from ..models import ArtifactFormat


class BaseExporter(ABC):
    """Base class for all document/media exporters."""

    format: ArtifactFormat

    @abstractmethod
    def export(self, doc: DocumentAST, **kwargs: Any) -> bytes | str:
        """Render DocumentAST into the target format representation."""
        ...
