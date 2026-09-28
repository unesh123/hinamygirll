"""Professional PDF generation tool using ReportLab.

Typesets real material only: text supplied for this turn, or a live multi-source
research pass whose findings each carry their source address. The renderer adds
structure and typography, never content.
"""

from __future__ import annotations

import logging
import json
import os
import re
import uuid
from html import escape
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from hinaa_api.tools.registry import registry, ToolDefinition

logger = logging.getLogger("hinaa.tools.pdf_generate")

# Storage directory
DOCS_DIR = (Path(__file__).resolve().parent.parent / "data" / "documents").resolve()
DOCS_DIR.mkdir(parents=True, exist_ok=True)


class GeneratePDFParams(BaseModel):
    userId: str | None = None
    topic: str | None = Field(None, max_length=500, description="The subject or prompt for the PDF")
    title: str | None = Field(None, max_length=240, description="Optional custom document title")
    content: str | None = Field(None, max_length=100_000, description="User-provided document content or notes")
    author: str | None = Field("HINAA AI Academic Studio", max_length=120, description="Document author or student name")
    category: str | None = Field("Document", max_length=80, description="Document type")
    query: str | None = Field(None, max_length=500, description="Search query or subject alias")
    subject: str | None = Field(None, max_length=500, description="Topic alias")
    prompt: str | None = Field(None, max_length=500, description="Prompt alias")


def _sanitize_slug(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "_", cleaned)[:50] or "document"


def _build_user_content_sections(content: str) -> list[tuple[str, Any]]:
    """Turn supplied markdown or plain text into structured sections with tables, bullets, and headings."""
    normalized = content.replace("\r\n", "\n").strip()
    if not normalized:
        return []

    lines = normalized.split("\n")
    sections: list[tuple[str, list[Any]]] = []
    current_title = "Executive Summary & Key Findings"
    current_blocks: list[Any] = []

    table_buffer: list[list[str]] = []
    bullet_buffer: list[str] = []
    text_buffer: list[str] = []

    def flush_buffers():
        nonlocal table_buffer, bullet_buffer, text_buffer
        if text_buffer:
            para = " ".join(text_buffer).strip()
            if para:
                current_blocks.append(para)
            text_buffer = []
        if bullet_buffer:
            current_blocks.append(list(bullet_buffer))
            bullet_buffer = []
        if table_buffer:
            if len(table_buffer) >= 2:
                current_blocks.append(list(table_buffer))
            else:
                current_blocks.append(" | ".join(table_buffer[0]))
            table_buffer = []

    def start_new_section(new_title: str):
        nonlocal current_title, current_blocks
        flush_buffers()
        if current_blocks:
            sections.append((current_title, current_blocks))
        current_title = new_title
        current_blocks = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            flush_buffers()
            continue

        # Check for Heading
        heading_match = (
            re.match(r"^#{1,4}\s+(.+)$", line)
            or re.match(r"^([IVXLCDM]+\.\s+[A-Za-z0-9\s,:'\"&-]+)$", line)
            or re.match(r"^\*\*([A-Za-z0-9\s,:'\"&-]{3,60})\*\*:?$", line)
        )
        if heading_match and not (line.startswith("|") and line.endswith("|")):
            clean_heading = heading_match.group(1).strip()
            clean_heading = re.sub(r"^\*+|\*+$", "", clean_heading).strip()
            start_new_section(clean_heading)
            continue

        # Check for Table row
        if line.startswith("|") and line.endswith("|"):
            if re.match(r"^\|(?:\s*:?-+:?\s*\|)+$", line):
                continue
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if any(cells):
                if text_buffer:
                    flush_buffers()
                if bullet_buffer:
                    flush_buffers()
                table_buffer.append(cells)
                continue

        if table_buffer:
            flush_buffers()

        # Check for Bullet point
        bullet_match = re.match(r"^(?:[-*•]|\d+\.)\s+(.+)$", line)
        if bullet_match:
            if text_buffer:
                flush_buffers()
            bullet_buffer.append(bullet_match.group(1).strip())
            continue

        if bullet_buffer:
            flush_buffers()
        text_buffer.append(line)

    flush_buffers()
    if current_blocks:
        sections.append((current_title, current_blocks))

    if not sections:
        sections = [("Document Content", [normalized])]

    return sections


class NoDocumentSource(Exception):
    """Raised when there is no real body content to put behind a requested document."""

    def __init__(self, topic: str, reason: str) -> None:
        super().__init__(reason)
        self.topic = topic
        self.reason = reason


SOURCE_LABELS = {
    "youcombined": "You.com",
    "stackoverflow": "Stack Overflow",
    "nepalnews": "Nepal News",
    "worldnews": "World News",
    "wikipedia": "Wikipedia",
    "arxiv": "arXiv",
    "github": "GitHub",
    "hackernews": "Hacker News",
}

_CHAT_AFFECTION_RE = re.compile(
    r"(?im)(?:(?<=^)|(?<=[\s,.:;!?]))"
    r"(?:babe|babes|baby|meri\s+jaan|jaan|janu|my\s+love|honey|sweetheart|darling|bro|dude)"
    r"(?=[\s,.:;!?]|$)"
)


def _scrub_chat_affection(text: str) -> str:
    """Strip direct-address pet names: conversational warmth belongs in the chat, not the document."""
    cleaned = _CHAT_AFFECTION_RE.sub("", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"[ \t]+([,.!?])", r"\1", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _research_sections(items: list[dict[str, Any]], sources: list[dict[str, Any]]) -> list[tuple[str, Any]]:
    """Turn live research findings into document sections that cite where each line came from."""
    sections: list[tuple[str, Any]] = [
        (
            "How this document was compiled",
            "Every finding below was fetched live for this topic and is followed by the address it came "
            "from. Nothing in this body was written from memory or invented to fill a section.",
        )
    ]

    source_lines: list[str] = []
    for source in sources:
        sid = str(source.get("id") or "source")
        label = SOURCE_LABELS.get(sid, sid)
        status = source.get("status")
        if status == "ok":
            source_lines.append(f"{label}: {source.get('count')} findings returned.")
        elif status == "empty":
            source_lines.append(f"{label}: no results for this topic.")
        else:
            source_lines.append(f"{label}: did not answer ({source.get('error') or 'unavailable'}).")
    if source_lines:
        sections.append(("Sources queried", source_lines))

    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault(str(item.get("source") or "web"), []).append(item)

    for sid, group in grouped.items():
        bullets: list[str] = []
        for item in group:
            headline = str(item.get("title") or item.get("url") or "untitled").strip()
            snippet = str(item.get("snippet") or "").strip()
            url = str(item.get("url") or "").strip()
            line = f"{headline} — {snippet}" if snippet else headline
            if url:
                line = f"{line} ({url})"
            bullets.append(line[:700])
        sections.append((f"Findings — {SOURCE_LABELS.get(sid, sid)}", bullets))

    return sections


async def _research_body(topic: str) -> list[tuple[str, Any]]:
    """Run the multi-source research pass with fast bounded depth; return [] when no source answered."""
    from .deep_research import deep_research_handler

    try:
        # Fast bounded depth for rapid, sub-3-second document generation
        outcome = await deep_research_handler({"topic": topic, "depth": 6})
    except Exception as error:  # noqa: BLE001
        logger.warning("Research pass failed for '%s': %s", topic, error)
        return []

    if not isinstance(outcome, dict) or outcome.get("status") != "success":
        return []
    data = outcome.get("data") or {}
    items = data.get("items") or []
    if not items:
        return []
    return _research_sections(items, data.get("sources") or [])


def _fetch_last_report_from_db(user_id: str | None = None) -> tuple[str, str] | None:
    """Find the most recent substantive assistant report/text from SQLite."""
    try:
        from hinaa_api.config import get_settings
        from hinaa_api.persistence.db import get_session_factory
        from hinaa_api.persistence.orm import Message
        import json

        session_factory = get_session_factory(get_settings())
        with session_factory() as session:
            messages = (
                session.query(Message)
                .filter(Message.role == "assistant")
                .filter(Message.deleted_at.is_(None))
                .order_by(Message.created_at.desc())
                .limit(10)
                .all()
            )
            for m in messages:
                raw = m.content or ""
                clean_text = ""
                try:
                    data = json.loads(raw)
                    clean_text = data.get("displayText") or ""
                except Exception:
                    clean_text = raw

                clean_text = clean_text.strip()
                # Check if this message looks like a substantial report/document
                if len(clean_text) > 120 and not clean_text.startswith("### 📄 PDF:"):
                    title_match = re.search(r"^#{1,3}\s+(?:📄\s*)?([^\n]+)", clean_text)
                    doc_title = title_match.group(1).strip() if title_match else ""
                    return doc_title, clean_text
    except Exception as e:
        logger.warning("Failed to fetch last report from DB: %s", e)
    return None


_REFERENTIAL_RE = re.compile(
    r"(?i)^(?:make\s+(?:me\s+)?(?:a\s+)?)?(?:based\s+on\s+)?(?:that|this|it|the\s+above|above|same|previous|last|the\s+report|report|thr\s+report|what\s+you\s+(?:said|wrote|generated)|conversation|notes|assignment)(?:\s+(?:assignment|report|paper|doc|document|topic|deck))?$"
)


def _is_referential_query(text: str | None) -> bool:
    if not text:
        return False
    t = text.strip()
    return bool(
        len(t) < 90
        and (
            _REFERENTIAL_RE.search(t)
            or "based on the report" in t.lower()
            or "based on thr report" in t.lower()
            or "based on that" in t.lower()
            or "from the report" in t.lower()
            or "gamma is not configured" in t.lower()
        )
    )


async def compose_document_source(
    topic: str | None,
    content: str | None,
    title: str | None,
    user_id: str | None = None,
) -> tuple[str, list[tuple[str, Any]], str]:
    """Resolve a document body rapidly: supplied text first, conversation history second, live research third."""
    safe_topic = (topic or "").strip() or "Technical Research Report"
    doc_title = (title or "").strip()
    norm_content = (content or "").strip()

    # 1. If explicit non-referential content is supplied, typeset it directly
    if norm_content and not _is_referential_query(norm_content):
        final_title = doc_title or f"{safe_topic}: Executive Report"
        return final_title, _build_user_content_sections(_scrub_chat_affection(norm_content)), "supplied-text"

    # 2. Check conversation history:
    # If explicitly referential, OR if the recent conversation report is relevant to the topic
    db_report = _fetch_last_report_from_db(user_id)
    if db_report:
        fetched_title, fetched_content = db_report
        # Match if explicitly referential OR if topic keywords overlap with recent report
        topic_words = set(re.findall(r"\w{4,}", safe_topic.lower()))
        content_words = set(re.findall(r"\w{4,}", fetched_content.lower()[:1000]))
        is_relevant = bool(topic_words & content_words) if topic_words else True

        if _is_referential_query(norm_content) or _is_referential_query(safe_topic) or is_relevant:
            final_title = doc_title or fetched_title or f"{safe_topic}: Executive Report"
            return final_title, _build_user_content_sections(_scrub_chat_affection(fetched_content)), "conversation-history"

    # 3. Otherwise, run live multi-source research on safe_topic with fast depth=6
    sections = await _research_body(safe_topic)
    if sections:
        final_title = doc_title or f"{safe_topic}: Research Dossier"
        return final_title, sections, "live-research"

    # 4. If research yielded no items but we have db_report, use it rather than failing
    if db_report:
        fetched_title, fetched_content = db_report
        final_title = doc_title or fetched_title or f"{safe_topic}: Executive Report"
        return final_title, _build_user_content_sections(_scrub_chat_affection(fetched_content)), "conversation-history"

    raise NoDocumentSource(
        safe_topic,
        "No research source answered, so there is no real material to typeset.",
    )


PROVENANCE_NOTES = {
    "supplied-text": "Body text supplied in this session; executive typography applied.",
    "conversation-history": "Compiled from the comprehensive report generated in this conversation session.",
    "live-research": "Body compiled from live multi-source research findings, each cited with its address.",
}


def _get_numbered_canvas_class(doc_title: str):
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from reportlab.lib.units import mm

    class NumberedCanvas(canvas.Canvas):
        """Two-pass ReportLab canvas that calculates total pages and draws modern headers and footers."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            num_pages = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self.draw_page_decorations(num_pages)
                super().showPage()
            super().save()

        def draw_page_decorations(self, total_pages: int):
            self.saveState()
            page_num = self._pageNumber

            # Running header on page 2+
            if page_num > 1:
                self.setFont("Helvetica-Bold", 8)
                self.setFillColor(colors.HexColor("#0f172a"))
                self.drawString(15 * mm, 297 * mm - 10 * mm, str(doc_title)[:75])
                self.setFont("Helvetica", 7.5)
                self.setFillColor(colors.HexColor("#94a3b8"))
                self.drawRightString(210 * mm - 15 * mm, 297 * mm - 10 * mm, "EXECUTIVE REPORT")
                self.setStrokeColor(colors.HexColor("#e2e8f0"))
                self.setLineWidth(0.6)
                self.line(15 * mm, 297 * mm - 12 * mm, 210 * mm - 15 * mm, 297 * mm - 12 * mm)

            # Running footer on all pages
            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.6)
            self.line(15 * mm, 12 * mm, 210 * mm - 15 * mm, 12 * mm)
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#64748b"))
            self.drawString(15 * mm, 8 * mm, "HINAA Frontier Academic Studio · Executive Edition")
            self.drawRightString(210 * mm - 15 * mm, 8 * mm, f"Page {page_num} of {total_pages}")
            self.restoreState()

    return NumberedCanvas


def _generate_reportlab_pdf(
    doc_id: str,
    title: str,
    author: str,
    category: str,
    sections: list[tuple[str, Any]],
    *,
    verification_note: str,
) -> tuple[Path, int]:
    """Compile document using ReportLab SimpleDocTemplate with professional typography, tables, and running footers."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch, mm
    from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    output_path = DOCS_DIR / f"{doc_id}.pdf"

    margin = 15 * mm
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
        title=title,
        author=author,
        subject=category,
        creator="HINAA",
    )

    styles = getSampleStyleSheet()

    c_primary = colors.HexColor("#0f172a")
    c_accent = colors.HexColor("#be185d")
    c_dark = colors.HexColor("#1e293b")
    c_body = colors.HexColor("#334155")
    c_bg_light = colors.HexColor("#f8fafc")
    c_border = colors.HexColor("#e2e8f0")

    badge_style = ParagraphStyle(
        "DocBadge",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=c_accent,
        spaceAfter=4,
    )
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=c_primary,
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        "DocSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=8,
    )
    h1_style = ParagraphStyle(
        "SectionH1",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=c_primary,
        spaceBefore=12,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "DocBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=c_body,
        spaceAfter=5,
    )
    bullet_style = ParagraphStyle(
        "DocBullet",
        parent=body_style,
        leftIndent=12,
        spaceAfter=3,
    )
    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=c_dark,
    )
    table_header_style = ParagraphStyle(
        "TableH",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
    )

    story = []

    # Banner Header
    story.append(Paragraph(escape(category.upper()), badge_style))
    story.append(Paragraph(escape(title), title_style))
    story.append(Paragraph(f"Prepared by {escape(author)} · Generated by HINAA AI Academic Studio", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=c_accent, spaceBefore=2, spaceAfter=10))

    # Metadata Executive Card
    meta_data = [
        [
            Paragraph(f"<b>Document Category:</b> {escape(category)}", body_style),
            Paragraph(f"<b>Document ID:</b> {escape(doc_id[:13])}", body_style),
        ],
        [
            Paragraph(f"<b>Prepared By:</b> {escape(author)}", body_style),
            Paragraph(f"<b>Source Provenance:</b> {escape(verification_note)}", body_style),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[280, 240])
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), c_bg_light),
            ("BOX", (0, 0), (-1, -1), 1, c_border),
            ("LINELEFT", (0, 0), (0, -1), 3, c_accent),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, c_border),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    story.append(meta_table)
    story.append(Spacer(1, 10))

    def render_block(block: Any) -> None:
        if isinstance(block, str):
            for para in block.split("\n"):
                if para.strip():
                    story.append(Paragraph(escape(para.strip()), body_style))
        elif isinstance(block, list):
            if block and isinstance(block[0], list):
                table_rows = []
                for row_idx, row in enumerate(block):
                    row_cells = []
                    for cell in row:
                        style_to_use = table_header_style if row_idx == 0 else table_cell_style
                        row_cells.append(Paragraph(escape(str(cell)), style_to_use))
                    table_rows.append(row_cells)

                col_count = max(1, len(block[0]))
                col_w = 520 / col_count
                table_flowable = Table(table_rows, colWidths=[col_w] * col_count)
                table_flowable.setStyle(
                    TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), c_primary),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ])
                )
                story.append(Spacer(1, 4))
                story.append(table_flowable)
                story.append(Spacer(1, 6))
            else:
                for item in block:
                    prefix = "" if str(item).startswith("•") or re.match(r"^\d+\.", str(item)) else "• "
                    story.append(Paragraph(f"{prefix}{escape(str(item))}", bullet_style))

    # Sections
    for sec_title, content in sections:
        story.append(Paragraph(f"■ {escape(sec_title)}", h1_style))
        if isinstance(content, str):
            render_block(content)
        elif isinstance(content, list):
            # Check if content itself is a pure 2D table
            if content and all(isinstance(r, list) and all(isinstance(c, str) for c in r) for r in content):
                render_block(content)
            else:
                for blk in content:
                    render_block(blk)
        else:
            render_block(content)
        story.append(Spacer(1, 6))

    canvas_class = _get_numbered_canvas_class(title)
    doc.build(story, canvasmaker=canvas_class)

    pages_rendered = max(1, getattr(doc, "page", 1))
    return output_path, pages_rendered


async def pdf_generate_handler(params: GeneratePDFParams | dict[str, Any]) -> dict[str, Any]:
    """Execute PDF generation and return download metadata."""
    if isinstance(params, dict):
        params = GeneratePDFParams(**params)
    doc_id = str(uuid.uuid4())
    resolved_topic = (
        params.topic
        or params.subject
        or params.query
        or params.prompt
        or params.title
        or params.content
        or "Technical Research Report"
    ).strip()
    try:
        title, sections, provenance = await compose_document_source(
            topic=resolved_topic,
            content=params.content,
            title=params.title,
            user_id=params.userId,
        )
    except NoDocumentSource as error:
        return {
            "status": "error",
            "code": "DOCUMENT_NO_SOURCE",
            "topic": error.topic,
            "error": (
                f"No PDF was generated for '{error.topic}'. {error.reason} Send me the text to "
                f"typeset, or ask again once the research sources answer — I will not pad the "
                f"pages with template prose."
            ),
        }

    safe_name = f"{_sanitize_slug(title)}.pdf"

    file_path, page_count = _generate_reportlab_pdf(
        doc_id=doc_id,
        title=title,
        author=params.author or "HINAA Academic Studio",
        category=params.category or "Document",
        sections=sections,
        verification_note=PROVENANCE_NOTES[provenance],
    )

    file_size_bytes = file_path.stat().st_size
    file_size_kb = round(file_size_bytes / 1024, 1)

    python_snippet = f"""# HINAA generated document: {safe_name}
# The downloadable PDF is the source of truth for this render.
# Sections: {len(sections)} | Pages: {page_count} | Size: {file_size_kb} KB
# Body source: {provenance}
# Re-run generation through the /v1/tools/execute pdf_generate endpoint with
# the same content to reproduce it; no unverified claims were added.
"""

    result = {
        "status": "success",
        "format": "pdf",
        "mimeType": "application/pdf",
        "provider": "local-reportlab",
        "docId": doc_id,
        "title": title,
        "filename": safe_name,
        "downloadUrl": f"/api/v1/generated-docs/{doc_id}",
        "pageCount": page_count,
        "fileSizeBytes": file_size_bytes,
        "fileSizeKb": file_size_kb,
        "topic": resolved_topic,
        "contentSource": provenance,
        "sectionCount": len(sections),
        "summary": f"Compiled '{title}' into a {page_count}-page PDF ({file_size_kb} KB) from {provenance.replace('-', ' ')} content.",
        "pythonSnippet": python_snippet,
    }
    # /v1/generated-docs lists the sidecars, not the PDFs: gated on a caller
    # supplied userId it was never written on the browser path, so 150 rendered
    # documents were invisible in the library while their downloads worked.
    file_path.with_suffix(".metadata.json").write_text(
        json.dumps({**result, "ownerId": params.userId or "unattributed"}), encoding="utf-8"
    )
    return result


pdf_generate_def = ToolDefinition(
    name="pdf_generate",
    display_name="PDF Generator",
    description=(
        "Typeset a document as a PDF. Pass `content` to render text from this conversation verbatim; "
        "with no content it compiles a live multi-source research pass on `topic`, where every finding "
        "carries the address it came from. It writes no text of its own and returns DOCUMENT_NO_SOURCE "
        "instead of a file when there is no real material to typeset."
    ),
    parameters={
        "topic": {"type": "string", "description": "Subject to research when no content is supplied"},
        "title": {"type": "string", "description": "Title for the document"},
        "content": {"type": "string", "description": "Source text to typeset; authoritative when provided"},
        "author": {"type": "string", "description": "Optional author name"},
        "category": {"type": "string", "description": "Document label, e.g. Research Report or Lecture Notes"},
    },
    required_parameters=[],
    permission_level="default",
    requires_confirmation=False,
    risk_level="low",
    cancellable=True,
    voice_aliases=["create pdf", "make pdf", "generate pdf", "assignment pdf"],
)

registry.register(pdf_generate_def, pdf_generate_handler)
