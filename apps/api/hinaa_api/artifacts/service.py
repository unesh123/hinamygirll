"""Phase 14 — Artifact OS: Central Artifact Service.

Provides a unified high-level orchestration interface for creating, converting,
inspecting, exporting, and packaging all HINAA artifacts.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .document_ast import DocumentAST, DocumentParser, SheetNode, SlideNode
from .exporters import (
    DocxExporter,
    HtmlExporter,
    MarkdownExporter,
    PdfExporter,
    PptxExporter,
    XlsxExporter,
)
from .inspector import ArtifactInspector, DocumentInspectionReport
from .models import (
    ArtifactFormat,
    ArtifactMetadata,
    ArtifactRecord,
    ArtifactStatus,
    ArtifactType,
)
from .packager import ArchivePackager

logger = logging.getLogger(__name__)


class ArtifactService:
    """Unified service for artifact lifecycle management, multi-format rendering,

    archive bundling, and verification inspection.
    """

    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = storage_dir.resolve() if storage_dir else None
        if self.storage_dir:
            self.storage_dir.mkdir(parents=True, exist_ok=True)

        self._artifacts: dict[str, ArtifactRecord] = {}

        # Component instances
        self.parser = DocumentParser()
        self.inspector = ArtifactInspector()
        self.packager = ArchivePackager()

        # Exporters
        self.md_exporter = MarkdownExporter()
        self.html_exporter = HtmlExporter()
        self.docx_exporter = DocxExporter()
        self.pptx_exporter = PptxExporter()
        self.xlsx_exporter = XlsxExporter()
        self.pdf_exporter = PdfExporter()

    def create_document(
        self,
        user_id: str,
        title: str,
        content: str,
        *,
        project_id: str | None = None,
        conversation_id: str | None = None,
        task_id: str | None = None,
        format: ArtifactFormat = ArtifactFormat.MD,
        tags: list[str] | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ) -> tuple[ArtifactRecord, DocumentAST]:
        """Parse markdown content into DocumentAST, register an ArtifactRecord, and return both."""
        doc_ast = self.parser.parse(content, title=title)

        meta = ArtifactMetadata(
            title=title,
            tags=tags or [],
            extra=extra_metadata or {},
        )

        filename = f"{title.lower().replace(' ', '_')[:40]}.{format.value}"
        artifact = ArtifactRecord(
            user_id=user_id,
            project_id=project_id,
            conversation_id=conversation_id,
            task_id=task_id,
            artifact_type=ArtifactType.DOCUMENT,
            format=format,
            title=title,
            filename=filename,
            content=content,
            metadata=meta,
            status=ArtifactStatus.VERIFIED,
        )
        artifact.compute_hash_and_size()

        self._artifacts[artifact.id] = artifact
        return artifact, doc_ast

    def create_presentation(
        self,
        user_id: str,
        title: str,
        slides_data: list[dict[str, Any]],
        *,
        subtitle: str = "",
        project_id: str | None = None,
        conversation_id: str | None = None,
        task_id: str | None = None,
    ) -> tuple[ArtifactRecord, DocumentAST]:
        """Create a presentation deck artifact from structured slide definitions."""
        slides = [
            SlideNode(
                title=s.get("title", ""),
                subtitle=s.get("subtitle", ""),
                bullets=s.get("bullets", []),
                speaker_notes=s.get("speaker_notes", ""),
                layout=s.get("layout", "bullet"),
            )
            for s in slides_data
        ]

        doc = DocumentAST(title=title, subtitle=subtitle, slides=slides)
        pptx_bytes = self.pptx_exporter.export(doc)

        filename = f"{title.lower().replace(' ', '_')[:40]}.pptx"
        artifact = ArtifactRecord(
            user_id=user_id,
            project_id=project_id,
            conversation_id=conversation_id,
            task_id=task_id,
            artifact_type=ArtifactType.PRESENTATION,
            format=ArtifactFormat.PPTX,
            title=title,
            filename=filename,
            content=pptx_bytes,
            status=ArtifactStatus.VERIFIED,
        )
        artifact.compute_hash_and_size()

        self._artifacts[artifact.id] = artifact
        return artifact, doc

    def create_spreadsheet(
        self,
        user_id: str,
        title: str,
        sheets_data: list[dict[str, Any]],
        *,
        project_id: str | None = None,
        conversation_id: str | None = None,
        task_id: str | None = None,
    ) -> tuple[ArtifactRecord, DocumentAST]:
        """Create a spreadsheet artifact from structured sheet definitions."""
        sheets = [
            SheetNode(
                name=s.get("name", f"Sheet{idx}"),
                headers=s.get("headers", []),
                rows=s.get("rows", []),
            )
            for idx, s in enumerate(sheets_data, start=1)
        ]

        doc = DocumentAST(title=title, sheets=sheets)
        xlsx_bytes = self.xlsx_exporter.export(doc)

        filename = f"{title.lower().replace(' ', '_')[:40]}.xlsx"
        artifact = ArtifactRecord(
            user_id=user_id,
            project_id=project_id,
            conversation_id=conversation_id,
            task_id=task_id,
            artifact_type=ArtifactType.SPREADSHEET,
            format=ArtifactFormat.XLSX,
            title=title,
            filename=filename,
            content=xlsx_bytes,
            status=ArtifactStatus.VERIFIED,
        )
        artifact.compute_hash_and_size()

        self._artifacts[artifact.id] = artifact
        return artifact, doc

    def export_artifact(
        self,
        artifact_id: str,
        target_format: ArtifactFormat,
    ) -> bytes | str:
        """Render an existing artifact to the specified target format."""
        art = self.get_artifact(artifact_id)
        if not art:
            raise KeyError(f"Artifact {artifact_id} not found")

        # Parse text content into DocumentAST
        if isinstance(art.content, bytes):
            content_str = art.content.decode("utf-8", errors="replace")
        else:
            content_str = str(art.content)

        doc = self.parser.parse(content_str, title=art.title)

        if target_format == ArtifactFormat.MD:
            return self.md_exporter.export(doc)
        elif target_format == ArtifactFormat.HTML:
            return self.html_exporter.export(doc)
        elif target_format == ArtifactFormat.DOCX:
            return self.docx_exporter.export(doc)
        elif target_format == ArtifactFormat.PPTX:
            return self.pptx_exporter.export(doc)
        elif target_format == ArtifactFormat.XLSX:
            return self.xlsx_exporter.export(doc)
        elif target_format == ArtifactFormat.PDF:
            return self.pdf_exporter.export(doc)
        else:
            raise ValueError(f"Unsupported export format: {target_format}")

    def inspect_artifact(self, artifact_id: str) -> dict[str, Any]:
        """Run deep quality and structural inspection on an artifact."""
        art = self.get_artifact(artifact_id)
        if not art:
            raise KeyError(f"Artifact {artifact_id} not found")
        return self.inspector.inspect_artifact(art)

    def package_artifacts(
        self,
        artifact_ids: list[str],
        bundle_title: str,
        description: str = "",
    ) -> bytes:
        """Bundle multiple artifacts into a single ZIP archive with a manifest."""
        selected: list[ArtifactRecord] = []
        for aid in artifact_ids:
            art = self.get_artifact(aid)
            if art:
                selected.append(art)
        return self.packager.package_artifacts(selected, bundle_title, description)

    def get_artifact(self, artifact_id: str) -> ArtifactRecord | None:
        return self._artifacts.get(artifact_id)

    def list_artifacts(
        self,
        *,
        user_id: str | None = None,
        project_id: str | None = None,
        task_id: str | None = None,
    ) -> list[ArtifactRecord]:
        results = list(self._artifacts.values())
        if user_id:
            results = [a for a in results if a.user_id == user_id]
        if project_id:
            results = [a for a in results if a.project_id == project_id]
        if task_id:
            results = [a for a in results if a.task_id == task_id]
        return results
