"""
Directive §10: Durable Long-Report Generation Subsystem.

Implements failure-resistant, checkpointed document compilation:
1. Section-level checkpoints persisted to durable JSON draft state.
2. Maximum section size enforcement.
3. Stream interruption continuation & resume capabilities.
4. Final artifact assembly with post-write size and section-count validation.
5. Card Gate: Strictly blocks emitting completed UI document cards before artifact validation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from hinaa_api.artifacts.document_validation import validate_document

logger = logging.getLogger("hinaa.artifacts.durable_report")

DRAFTS_DIR = Path(__file__).resolve().parents[3] / "data" / "renders" / "drafts"


@dataclass
class ReportCheckpointState:
    report_id: str
    title: str
    expected_sections: List[str]
    completed_sections: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: Literal["draft", "interrupted", "assembled", "validated", "error"] = "draft"
    max_section_chars: int = 20_000
    assembled_path: Optional[str] = None
    validation_receipt: Optional[Dict[str, Any]] = None


class DurableReportPipeline:
    """Orchestrates checkpointed, resumable long-report compilation."""

    @classmethod
    def _draft_path(cls, report_id: str) -> Path:
        DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
        return DRAFTS_DIR / f"{report_id}.json"

    @classmethod
    def init_report(
        cls,
        report_id: str,
        title: str,
        expected_sections: List[str],
        max_section_chars: int = 20_000,
    ) -> ReportCheckpointState:
        """Initializes a new durable report session with section checkpoints."""
        state = ReportCheckpointState(
            report_id=report_id,
            title=title,
            expected_sections=expected_sections,
            max_section_chars=max_section_chars,
        )
        cls._save_state(state)
        return state

    @classmethod
    def _save_state(cls, state: ReportCheckpointState) -> None:
        p = cls._draft_path(state.report_id)
        state.updated_at = datetime.now(timezone.utc).isoformat()
        p.write_text(json.dumps(asdict(state), indent=2), encoding="utf-8")

    @classmethod
    def load_state(cls, report_id: str) -> Optional[ReportCheckpointState]:
        p = cls._draft_path(report_id)
        if not p.is_file():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        return ReportCheckpointState(**data)

    @classmethod
    def checkpoint_section(
        cls,
        report_id: str,
        section_name: str,
        content: str,
    ) -> ReportCheckpointState:
        """Records a single section checkpoint, enforcing maximum section length."""
        state = cls.load_state(report_id)
        if not state:
            raise ValueError(f"Report state {report_id} not found")

        trimmed = content.strip()
        if len(trimmed) > state.max_section_chars:
            logger.warning(
                "Section '%s' exceeds max length (%d > %d); trimming to limit",
                section_name,
                len(trimmed),
                state.max_section_chars,
            )
            trimmed = trimmed[: state.max_section_chars]

        state.completed_sections[section_name] = trimmed
        state.status = (
            "draft"
            if len(state.completed_sections) < len(state.expected_sections)
            else "assembled"
        )
        cls._save_state(state)
        return state

    @classmethod
    def can_resume(cls, report_id: str) -> bool:
        """Checks if an interrupted draft exists with missing sections."""
        state = cls.load_state(report_id)
        if not state:
            return False
        if state.status in ("validated", "assembled"):
            return False
        return len(state.completed_sections) < len(state.expected_sections)

    @classmethod
    def assemble_and_validate(
        cls,
        report_id: str,
        output_format: str = "md",
        output_dir: Optional[Path] = None,
    ) -> ReportCheckpointState:
        """Assembles all checkpointed sections into final document and executes validation."""
        state = cls.load_state(report_id)
        if not state:
            raise ValueError(f"Report state {report_id} not found")

        missing = [s for s in state.expected_sections if s not in state.completed_sections]
        if missing:
            state.status = "interrupted"
            cls._save_state(state)
            raise ValueError(f"Cannot assemble report: missing sections {missing}")

        target_dir = output_dir or DRAFTS_DIR.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        final_file = target_dir / f"{report_id}.{output_format}"

        # Markdown body synthesis
        lines = [f"# {state.title}\n"]
        for sec in state.expected_sections:
            lines.append(f"## {sec}\n")
            lines.append(state.completed_sections[sec] + "\n")

        full_content = "\n".join(lines)
        final_file.write_text(full_content, encoding="utf-8")

        # Validate artifact bytes and integrity
        validation = validate_document(final_file, fmt=output_format)
        state.assembled_path = str(final_file.resolve())
        state.validation_receipt = validation
        state.status = "validated"
        cls._save_state(state)
        return state

    @classmethod
    def emit_completed_card(cls, report_id: str) -> Dict[str, Any]:
        """
        Directive §10 & §11: Strictly forbids emitting a completed UI card before
        artifact validation has passed.
        """
        state = cls.load_state(report_id)
        if not state:
            raise ValueError(f"Report {report_id} does not exist.")
        if state.status != "validated" or not state.assembled_path:
            raise ValueError(
                f"DOCUMENT_CARD_BLOCKED: Cannot emit completed card for report '{report_id}' "
                f"because status is '{state.status}', not 'validated'."
            )

        p = Path(state.assembled_path)
        if not p.is_file() or p.stat().st_size <= 0:
            raise ValueError("DOCUMENT_CARD_BLOCKED: Assembled file missing or empty on disk.")

        return {
            "type": "document_card",
            "reportId": report_id,
            "title": state.title,
            "status": "ready",
            "downloadUrl": f"/v1/renders/{p.name}",
            "filePath": str(p),
            "fileSizeBytes": p.stat().st_size,
            "sectionCount": len(state.expected_sections),
            "validation": state.validation_receipt,
        }
