"""document_generate.py — Multi-Format Document Generation Tool (DOCX, PDF, PPTX).

Supports producing publication-grade Word DOCX, ReportLab PDF, and PowerPoint PPTX documents
from supplied text or a live multi-source research pass. The exporters format; they do not author.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
import re
from typing import Any, Literal
import uuid

from pydantic import BaseModel, Field

from hinaa_api.artifacts.document_ast import DocumentParser
from hinaa_api.artifacts.exporters import (
    DocxExporter,
    HtmlExporter,
    MarkdownExporter,
    PptxExporter,
)
from hinaa_api.tools.pdf_generate import (
    DOCS_DIR,
    GeneratePDFParams,
    NoDocumentSource,
    _sanitize_slug,
    _scrub_chat_affection,
    compose_document_source,
    pdf_generate_handler,
)
from hinaa_api.tools.registry import ToolDefinition, registry

logger = logging.getLogger("hinaa.tools.document_generate")


class GenerateDocumentParams(BaseModel):
    model_config = {"extra": "ignore"}

    userId: str | None = None
    title: str | None = Field(None, max_length=240, description="Title of the document")
    content: str | None = Field("", max_length=150_000, description="Document body or notes")
    format: Literal["docx", "pdf", "pptx", "md", "html"] = Field(
        "docx", description="Output document format (docx, pdf, pptx, md, html)"
    )
    topic: str | None = Field(None, max_length=500, description="Topic or subject for synthesis")
    author: str | None = Field("HINAA AI Studio", max_length=120, description="Document author")
    category: str | None = Field("Report", max_length=80, description="Document category")
    query: str | None = Field(None, max_length=500, description="Alias for topic")
    subject: str | None = Field(None, max_length=500, description="Alias for topic")
    prompt: str | None = Field(None, max_length=500, description="Alias for topic")


async def document_generate_handler(params: GenerateDocumentParams) -> dict[str, Any]:
    """Compile content into DOCX, PDF, PPTX, or Markdown document with downloadable artifact URL."""
    fmt = (params.format or "docx").lower().strip()
    if fmt == "word" or fmt == "doc":
        fmt = "docx"

    effective_topic = (
        params.topic
        or params.subject
        or params.query
        or params.prompt
        or params.title
        or params.content
        or "Technical Research Report"
    ).strip()

    # If PDF requested, route to the battle-tested PDF engine
    if fmt == "pdf":
        return await pdf_generate_handler(
            GeneratePDFParams(
                userId=params.userId,
                topic=effective_topic,
                title=params.title,
                content=params.content,
                author=params.author,
                category=params.category,
            )
        )

    # Determine title & markdown content
    provenance = "supplied-text"
    if params.content and params.content.strip():
        title = params.title or effective_topic.title()
        raw_markdown = _scrub_chat_affection(params.content).strip()
    else:
        try:
            title, sections, provenance = await compose_document_source(
                topic=effective_topic,
                content=None,
                title=params.title,
            )
        except NoDocumentSource as error:
            return {
                "status": "error",
                "code": "DOCUMENT_NO_SOURCE",
                "topic": error.topic,
                "error": (
                    f"No {fmt.upper()} was generated for '{error.topic}'. {error.reason} Send me the "
                    f"text to lay out, or ask again once the research sources answer — I will not pad "
                    f"the pages with template prose."
                ),
            }
        # Convert the sourced sections to markdown for the DocumentAST exporters
        md_parts = [
            f"# {title}\n\n*Prepared by {params.author or 'HINAA AI Studio'} · Body source: {provenance}*\n"
        ]
        for heading, body in sections:
            md_parts.append(f"## {heading}\n")
            if isinstance(body, list):
                if body and isinstance(body[0], (list, tuple)):
                    # Table representation
                    headers = body[0]
                    rows = body[1:]
                    md_parts.append("| " + " | ".join(str(h) for h in headers) + " |")
                    md_parts.append("| " + " | ".join("---" for _ in headers) + " |")
                    for row in rows:
                        md_parts.append("| " + " | ".join(str(c) for c in row) + " |")
                    md_parts.append("")
                else:
                    for item in body:
                        md_parts.append(f"- {item}")
                    md_parts.append("")
            else:
                md_parts.append(f"{body}\n")
        raw_markdown = "\n".join(md_parts)

    doc_id = str(uuid.uuid4())
    safe_slug = _sanitize_slug(title)
    filename = f"{safe_slug}.{fmt}"
    file_path = DOCS_DIR / f"{doc_id}_{filename}"

    parser = DocumentParser()
    doc_ast = parser.parse(raw_markdown, title=title)

    if fmt == "docx":
        exporter = DocxExporter()
        output_bytes = exporter.export(doc_ast)
        mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        provider = "local-docx-engine"
    elif fmt == "pptx":
        exporter = PptxExporter()
        output_bytes = exporter.export(doc_ast)
        mime_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        provider = "local-pptx-engine"
    elif fmt == "html":
        exporter = HtmlExporter()
        html_str = exporter.export(doc_ast)
        output_bytes = html_str.encode("utf-8")
        mime_type = "text/html"
        provider = "local-html-engine"
    else:
        # Default fallback to Markdown
        fmt = "md"
        filename = f"{safe_slug}.md"
        file_path = DOCS_DIR / f"{doc_id}_{filename}"
        exporter = MarkdownExporter()
        md_str = exporter.export(doc_ast)
        output_bytes = md_str.encode("utf-8")
        mime_type = "text/markdown"
        provider = "local-markdown-engine"

    file_path.write_bytes(output_bytes)
    file_size_bytes = len(output_bytes)
    file_size_kb = round(file_size_bytes / 1024, 1)

    result = {
        "status": "success",
        "format": fmt,
        "mimeType": mime_type,
        "provider": provider,
        "docId": doc_id,
        "title": title,
        "filename": filename,
        "downloadUrl": f"/api/v1/generated-docs/{doc_id}",
        "fileSizeBytes": file_size_bytes,
        "fileSizeKb": file_size_kb,
        "topic": effective_topic,
        "contentSource": provenance,
        "summary": f"Compiled '{title}' into a downloadable {fmt.upper()} document ({file_size_kb} KB) from {provenance.replace('-', ' ')} content.",
    }

    if params.userId:
        file_path.with_suffix(".metadata.json").write_text(
            json.dumps({**result, "ownerId": params.userId}), encoding="utf-8"
        )

    logger.info("Generated document %s: %s (%d bytes)", doc_id, filename, file_size_bytes)
    return result


document_generate_def = ToolDefinition(
    name="document_generate",
    display_name="Generate Document",
    description=(
        "Lay out a Word DOCX, PDF, PPTX, or Markdown document and return a downloadable URL. "
        "`content` is laid out verbatim; without it the body comes from a live multi-source research "
        "pass on `topic`. Nothing is invented from a bare topic — the tool answers DOCUMENT_NO_SOURCE "
        "when there is no real material."
    ),
    parameters={
        "title": {"type": "string", "description": "Document title"},
        "content": {"type": "string", "description": "Document text or markdown body"},
        "format": {
            "type": "string",
            "enum": ["docx", "pdf", "pptx", "md", "html"],
            "description": "Target file format: docx, pdf, pptx, md, or html",
        },
        "topic": {"type": "string", "description": "Subject to research when no content is supplied"},
        "author": {"type": "string", "description": "Author name"},
        "category": {"type": "string", "description": "Document type / category"},
    },
    required_parameters=[],
    requires_confirmation=False,
    side_effects="Creates a persistent document artifact in the workspace.",
)

registry.register(document_generate_def, document_generate_handler)
