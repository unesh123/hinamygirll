"""
Autonomous Background Worker Hive for HINAA.

Enables multi-agent parallel task execution across research, document synthesis,
presentation authoring, and creative visual generation.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SUPPORTED_TASKS = {"research", "pdf", "pptx", "creative"}


class WorkerHive:
    """Orchestrates autonomous worker subagents concurrently."""

    async def execute_mission(
        self,
        mission: str,
        tasks: Optional[List[str]] = None,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Decompose mission and execute research, PDF, PPTX, and creative subagents in parallel."""
        mission_clean = mission.strip()
        cid = conversation_id or str(uuid.uuid4())

        if tasks is not None and len(tasks) == 0:
            return {
                "status": "error",
                "mission": mission_clean,
                "conversationId": cid,
                "deliverables": {},
                "errors": ["empty_tasks"],
            }

        requested_list = tasks if tasks is not None else ["research", "pdf", "pptx", "creative"]
        requested = [t for t in requested_list if t in SUPPORTED_TASKS]
        if not requested:
            return {
                "status": "error",
                "mission": mission_clean,
                "conversationId": cid,
                "deliverables": {},
                "errors": ["unsupported_tasks"],
            }

        deliverables: Dict[str, Any] = {}
        pending: Dict[str, Any] = {}
        errors: List[str] = []

        # Check if research is required
        needs_research = any(t in requested for t in ("research", "pdf", "pptx"))
        sections = None

        if needs_research:
            from ..tools.pdf_generate import _research_body
            try:
                sections = await _research_body(mission_clean)
            except Exception as e:
                logger.warning("Research worker exception: %s", e)
                sections = []

            if not sections:
                if "research" in requested:
                    errors.append("research")
                if "pdf" in requested:
                    errors.append("pdf")
                if "pptx" in requested:
                    errors.append("pptx")
            else:
                if "research" in requested:
                    deliverables["research"] = {
                        "sectionCount": len(sections),
                        "status": "completed",
                        "sections": sections,
                    }

        # Format markdown content from researched sections if available
        content_str = None
        if sections:
            lines = [f"# {mission_clean}\n"]
            for heading, body in sections:
                lines.append(f"## {heading}\n")
                if isinstance(body, list):
                    for item in body:
                        lines.append(f"- {item}")
                else:
                    lines.append(f"{body}\n")
            content_str = "\n".join(lines)

        async def _run_doc(fmt: str) -> None:
            if not sections:
                return
            from ..tools.document_generate import document_generate_handler, GenerateDocumentParams
            try:
                doc_title = f"{mission_clean}: Technical Dossier" if fmt == "pdf" else f"{mission_clean} Presentation"
                res = await document_generate_handler(GenerateDocumentParams(
                    title=doc_title,
                    topic=mission_clean,
                    content=content_str,
                    format=fmt,
                ))
                if (
                    isinstance(res, dict)
                    and res.get("status") == "success"
                    and res.get("validationStatus") == "validated"
                    and res.get("canonicalPath")
                    and Path(res["canonicalPath"]).is_file()
                ):
                    deliverables[fmt] = res
                else:
                    errors.append(fmt)
            except Exception as e:
                logger.warning("%s worker failed: %s", fmt.upper(), e)
                errors.append(fmt)

        async def _run_creative() -> None:
            from ..tools.image_generate import image_generate_handler, ImageGenerateParams
            try:
                prompt = (
                    f"Masterpiece architectural and conceptual illustration representing {mission_clean}, "
                    f"highly detailed, cinematic volumetric lighting, 8k resolution, elegant aesthetic"
                )
                res = await image_generate_handler(ImageGenerateParams(prompt=prompt))
                if isinstance(res, dict) and res.get("status") == "processing":
                    pending["creative"] = res
                elif isinstance(res, dict) and res.get("status") == "success" and (res.get("imageUrl") or res.get("url")):
                    deliverables["creative"] = res
                else:
                    errors.append("creative")
            except Exception as e:
                logger.warning("Creative worker failed: %s", e)
                errors.append("creative")

        doc_tasks = []
        if "pdf" in requested and sections:
            doc_tasks.append(_run_doc("pdf"))
        if "pptx" in requested and sections:
            doc_tasks.append(_run_doc("pptx"))
        if "creative" in requested:
            doc_tasks.append(_run_creative())

        if doc_tasks:
            await asyncio.gather(*doc_tasks)

        # Determine overall status
        if pending and not deliverables and not errors:
            status = "processing"
        elif deliverables and not errors:
            status = "success"
        elif deliverables and errors:
            status = "partial"
        elif pending and not deliverables:
            status = "processing"
        else:
            status = "error"

        result_payload: Dict[str, Any] = {
            "status": status,
            "mission": mission_clean,
            "conversationId": cid,
            "deliverables": deliverables,
        }
        if pending:
            result_payload["pending"] = pending
        if errors:
            result_payload["errors"] = errors

        result_payload["summary"] = (
            f"Autonomous swarm completed mission for '{mission_clean}'. "
            f"Generated {len(deliverables)} integrated deliverables."
        )
        return result_payload


worker_hive = WorkerHive()
