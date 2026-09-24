"""Phase 14 — Artifact OS: PDF Document Exporter.

Renders DocumentAST to branded PDF dossiers using the existing HINAA PDF layout engine.
"""
from __future__ import annotations

from typing import Any

from ...documents.pdf import render_markdown_pdf
from ..document_ast import DocumentAST
from ..models import ArtifactFormat
from .base import BaseExporter
from .markdown_html import MarkdownExporter


class PdfExporter(BaseExporter):
    """Renders DocumentAST into a high-polish branded PDF document."""

    format = ArtifactFormat.PDF

    def __init__(self) -> None:
        self._md_exporter = MarkdownExporter()

    def export(self, doc: DocumentAST, **kwargs: Any) -> bytes:
        md_text = self._md_exporter.export(doc)
        title = doc.title or "HINAA Artifact Dossier"
        pdf_bytes = render_markdown_pdf(md_text, title=title)
        return pdf_bytes
