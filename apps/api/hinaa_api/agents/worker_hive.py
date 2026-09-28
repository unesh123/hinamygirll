"""
Autonomous Background Worker Hive for HINAA.

Enables multi-agent parallel task execution across research, document synthesis,
presentation authoring, and creative visual generation.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


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
        
        # Default task spectrum if not specified
        requested = tasks or ["research", "pdf", "pptx", "creative"]
        results: Dict[str, Any] = {}
        deliverables: Dict[str, Any] = {}

        # 1. Parallel Task Definitions
        async def _run_research() -> Dict[str, Any]:
            try:
                from ..tools.pdf_generate import _research_body, _synthesize_academic_dossier
                sections = await _research_body(mission_clean)
                if not sections:
                    sections = _synthesize_academic_dossier(mission_clean)
                return {"ok": True, "sections": sections, "section_count": len(sections)}
            except Exception as e:
                logger.warning("Research worker failed: %s", e)
                return {"ok": False, "error": str(e)}

        async def _run_pdf(sections_future: asyncio.Task) -> Dict[str, Any]:
            try:
                research_res = await sections_future
                sections = research_res.get("sections") or []
                from ..tools.pdf_generate import _generate_reportlab_pdf, _store_generated_pdf, safe_filename
                pdf_bytes, page_count = _generate_reportlab_pdf(
                    title=f"{mission_clean}: Technical Dossier",
                    sections=sections,
                    topic=mission_clean,
                )
                fname = f"{safe_filename(mission_clean)}_dossier.pdf"
                rec = _store_generated_pdf(fname, pdf_bytes, page_count, mission_clean)
                return {
                    "ok": True,
                    "title": f"{mission_clean}: Technical Dossier",
                    "filename": fname,
                    "downloadUrl": rec["downloadUrl"],
                    "pageCount": page_count,
                    "fileSizeBytes": len(pdf_bytes),
                }
            except Exception as e:
                logger.warning("PDF worker failed: %s", e)
                return {"ok": False, "error": str(e)}

        async def _run_pptx() -> Dict[str, Any]:
            try:
                from ..tools.document_generate import document_generate_handler
                res = await document_generate_handler(
                    topic=mission_clean,
                    format="pptx",
                    document_title=f"{mission_clean} Presentation",
                )
                return res
            except Exception as e:
                logger.warning("PPTX worker failed: %s", e)
                return {"ok": False, "error": str(e)}

        async def _run_creative() -> Dict[str, Any]:
            try:
                from ..tools.image_generate import image_generate_handler
                prompt = (
                    f"Masterpiece architectural and conceptual illustration representing {mission_clean}, "
                    f"highly detailed, cinematic volumetric lighting, 8k resolution, elegant aesthetic"
                )
                res = await image_generate_handler(prompt=prompt)
                return res
            except Exception as e:
                logger.warning("Creative worker failed: %s", e)
                return {"ok": False, "error": str(e)}

        # Launch concurrent background execution
        research_task = asyncio.create_task(_run_research())
        pdf_task = asyncio.create_task(_run_pdf(research_task)) if "pdf" in requested else None
        pptx_task = asyncio.create_task(_run_pptx()) if "pptx" in requested else None
        creative_task = asyncio.create_task(_run_creative()) if "creative" in requested else None

        # Await completion
        res_done = await research_task
        results["research"] = res_done
        deliverables["research"] = {
            "sectionCount": res_done.get("section_count", 0),
            "status": "completed" if res_done.get("ok") else "fallback",
        }

        if pdf_task:
            pdf_res = await pdf_task
            results["pdf"] = pdf_res
            if pdf_res.get("ok"):
                deliverables["pdf"] = {
                    "title": pdf_res.get("title"),
                    "downloadUrl": pdf_res.get("downloadUrl"),
                    "pageCount": pdf_res.get("pageCount"),
                    "filename": pdf_res.get("filename"),
                }

        if pptx_task:
            pptx_res = await pptx_task
            results["pptx"] = pptx_res
            if pptx_res.get("status") == "success":
                deliverables["pptx"] = {
                    "title": pptx_res.get("title"),
                    "downloadUrl": pptx_res.get("downloadUrl"),
                    "filename": pptx_res.get("filename"),
                }

        if creative_task:
            creative_res = await creative_task
            results["creative"] = creative_res
            if creative_res.get("status") == "success":
                deliverables["creative"] = {
                    "imageUrl": creative_res.get("imageUrl") or creative_res.get("url"),
                    "prompt": creative_res.get("prompt"),
                }

        return {
            "status": "success",
            "mission": mission_clean,
            "conversationId": cid,
            "deliverables": deliverables,
            "summary": (
                f"Autonomous swarm completed mission for '{mission_clean}'. "
                f"Generated {len(deliverables)} integrated deliverables."
            ),
        }


worker_hive = WorkerHive()
