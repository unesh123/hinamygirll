"""Phase 14 — Artifact OS: Render & Inspect Engine.

Provides deep structural inspection, table-of-contents extraction, token and reading
time estimation, document linting, and quality evaluation before artifact delivery.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .document_ast import (
    CalloutNode,
    CodeBlockNode,
    DocumentAST,
    HeadingNode,
    ListNode,
    ParagraphNode,
    TableNode,
)
from .models import ArtifactFormat, ArtifactRecord


class LintSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class DocumentLintIssue:
    code: str
    message: str
    severity: LintSeverity
    node_index: int | None = None
    fix_suggestion: str | None = None


@dataclass
class TableOfContentsEntry:
    level: int
    title: str
    anchor_id: str


@dataclass
class DocumentInspectionReport:
    title: str
    word_count: int
    char_count: int
    estimated_tokens: int
    reading_time_minutes: float
    table_of_contents: list[TableOfContentsEntry] = field(default_factory=list)
    heading_count: int = 0
    table_count: int = 0
    code_block_count: int = 0
    callout_count: int = 0
    list_count: int = 0
    issues: list[DocumentLintIssue] = field(default_factory=list)
    quality_score: float = 1.0  # 0.0 to 1.0
    preview_snippet: str = ""

    @property
    def passed(self) -> bool:
        return not any(i.severity == LintSeverity.ERROR for i in self.issues)


class ArtifactInspector:
    """Audits and extracts telemetry from DocumentAST and ArtifactRecords."""

    WORDS_PER_MINUTE = 200
    TOKENS_PER_WORD = 1.33

    def inspect_document(self, doc: DocumentAST) -> DocumentInspectionReport:
        plain_text = doc.extract_plain_text()
        words = plain_text.split()
        word_count = len(words)
        char_count = len(plain_text)

        est_tokens = int(math.ceil(word_count * self.TOKENS_PER_WORD))
        reading_time = round(word_count / self.WORDS_PER_MINUTE, 1) if word_count > 0 else 0.0

        # Build ToC
        toc: list[TableOfContentsEntry] = []
        heading_levels: list[int] = []
        for node in doc.children:
            if isinstance(node, HeadingNode):
                toc.append(TableOfContentsEntry(
                    level=node.level,
                    title=node.text,
                    anchor_id=node.anchor_id,
                ))
                heading_levels.append(node.level)

        # Linting issues
        issues: list[DocumentLintIssue] = []

        # 1. Missing or generic title
        if not doc.title or doc.title in ("Document", "Untitled Document"):
            issues.append(DocumentLintIssue(
                code="GENERIC_TITLE",
                message="Document has no custom title set.",
                severity=LintSeverity.WARNING,
                fix_suggestion="Set a descriptive H1 heading or document title.",
            ))

        # 2. Heading hierarchy jumps (e.g. H1 -> H3)
        for i in range(len(heading_levels) - 1):
            curr, nxt = heading_levels[i], heading_levels[i + 1]
            if nxt > curr + 1:
                issues.append(DocumentLintIssue(
                    code="HEADING_LEVEL_JUMP",
                    message=f"Heading level jumps from H{curr} directly to H{nxt}.",
                    severity=LintSeverity.INFO,
                    fix_suggestion=f"Consider inserting an intermediate H{curr + 1} heading.",
                ))

        # 3. Component counters & node inspections
        tables = 0
        code_blocks = 0
        callouts = 0
        lists = 0

        for idx, node in enumerate(doc.children):
            if isinstance(node, TableNode):
                tables += 1
                if not node.headers:
                    issues.append(DocumentLintIssue(
                        code="TABLE_MISSING_HEADERS",
                        message="Table does not specify header columns.",
                        severity=LintSeverity.WARNING,
                        node_index=idx,
                    ))
                if not node.rows:
                    issues.append(DocumentLintIssue(
                        code="EMPTY_TABLE",
                        message="Table has no data rows.",
                        severity=LintSeverity.ERROR,
                        node_index=idx,
                    ))

            elif isinstance(node, CodeBlockNode):
                code_blocks += 1
                if not node.language:
                    issues.append(DocumentLintIssue(
                        code="CODE_BLOCK_NO_LANG",
                        message="Code block lacks a language syntax specifier.",
                        severity=LintSeverity.INFO,
                        node_index=idx,
                    ))
                if not node.code.strip():
                    issues.append(DocumentLintIssue(
                        code="EMPTY_CODE_BLOCK",
                        message="Code block is empty.",
                        severity=LintSeverity.WARNING,
                        node_index=idx,
                    ))

            elif isinstance(node, CalloutNode):
                callouts += 1

            elif isinstance(node, ListNode):
                lists += 1
                if not node.items:
                    issues.append(DocumentLintIssue(
                        code="EMPTY_LIST",
                        message="List contains zero items.",
                        severity=LintSeverity.WARNING,
                        node_index=idx,
                    ))

        # Quality scoring
        error_count = sum(1 for i in issues if i.severity == LintSeverity.ERROR)
        warning_count = sum(1 for i in issues if i.severity == LintSeverity.WARNING)
        deduction = (error_count * 0.3) + (warning_count * 0.1)
        score = max(0.0, round(1.0 - deduction, 2))

        # Preview snippet
        preview = plain_text[:300].strip() + ("..." if len(plain_text) > 300 else "")

        return DocumentInspectionReport(
            title=doc.title,
            word_count=word_count,
            char_count=char_count,
            estimated_tokens=est_tokens,
            reading_time_minutes=reading_time,
            table_of_contents=toc,
            heading_count=len(toc),
            table_count=tables,
            code_block_count=code_blocks,
            callout_count=callouts,
            list_count=lists,
            issues=issues,
            quality_score=score,
            preview_snippet=preview,
        )

    def inspect_artifact(self, artifact: ArtifactRecord) -> dict[str, Any]:
        """High-level inspection report for any ArtifactRecord."""
        report: dict[str, Any] = {
            "artifact_id": artifact.id,
            "title": artifact.title,
            "format": artifact.format.value,
            "size_bytes": artifact.size_bytes,
            "sha256": artifact.sha256,
            "status": artifact.status.value,
        }

        # If document format and text content is present, run deep inspection
        if artifact.format in (ArtifactFormat.MD, ArtifactFormat.HTML, ArtifactFormat.TEXT):
            from .document_ast import DocumentParser
            content_str = (
                artifact.content if isinstance(artifact.content, str)
                else artifact.content.decode("utf-8", errors="replace")
            )
            parsed_doc = DocumentParser().parse(content_str, title=artifact.title)
            doc_report = self.inspect_document(parsed_doc)
            report["document_analysis"] = {
                "word_count": doc_report.word_count,
                "reading_time_minutes": doc_report.reading_time_minutes,
                "toc_entries": len(doc_report.table_of_contents),
                "quality_score": doc_report.quality_score,
                "passed": doc_report.passed,
                "issues": [
                    {"code": i.code, "message": i.message, "severity": i.severity.value}
                    for i in doc_report.issues
                ],
                "preview": doc_report.preview_snippet,
            }

        return report
