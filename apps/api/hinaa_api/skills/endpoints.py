"""endpoints.py — FastAPI router for HINAA's Skill Ecosystem."""

from __future__ import annotations

import logging
from typing import Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .catalog import skill_catalog
from .importer import skill_importer
from .router import skill_router

logger = logging.getLogger("hinaa.skills.endpoints")

router = APIRouter(prefix="/api/skills", tags=["skills"])


class SkillImportPayload(BaseModel):
    url: str = Field(..., description="Git repository URL to import as a skill")
    name: str | None = Field(None, description="Optional custom identifier for the skill")


@router.get("")
async def list_skills(
    category: str | None = Query(None, description="Filter skills by domain category"),
    refresh: bool = Query(False, description="Force re-indexing of all skills"),
) -> dict[str, Any]:
    """Returns the full catalog of indexed skills and category breakdowns."""
    if refresh:
        skill_catalog.load_all_skills(force_reload=True)
        skill_router.build_index(force=True)

    skills = skill_catalog.list_all()
    if category:
        skills = [s for s in skills if s.category.lower() == category.lower()]

    return {
        "status": "ok",
        "total": len(skills),
        "categories": skill_catalog.get_categories(),
        "skills": [s.to_dict() for s in skills],
    }


@router.get("/categories")
async def get_categories() -> dict[str, Any]:
    """Returns domain categories and counts across the skill ecosystem."""
    cats = skill_catalog.get_categories()
    return {
        "status": "ok",
        "totalSkills": sum(cats.values()),
        "categories": cats,
    }


@router.get("/search")
async def search_skills(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(6, ge=1, le=50, description="Max matches to return"),
    category: str | None = Query(None, description="Optional category filter"),
) -> dict[str, Any]:
    """Performs sub-5ms semantic/keyword search across hundreds or thousands of skills."""
    matches = skill_router.search(q, top_k=limit, category=category)
    return {
        "status": "ok",
        "query": q,
        "count": len(matches),
        "results": [
            {
                "skill": m.skill.to_dict(),
                "score": m.score,
                "matchedTerms": m.matched_terms,
            }
            for m in matches
        ],
    }


@router.get("/{skill_id}")
async def get_skill(skill_id: str) -> dict[str, Any]:
    """Inspects a specific skill by ID."""
    skill = skill_catalog.get_skill(skill_id) or skill_catalog.get_skill(f"tool:{skill_id}")
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    return {
        "status": "ok",
        "skill": skill.to_dict(),
    }


@router.post("/import")
async def import_skill(payload: SkillImportPayload) -> dict[str, Any]:
    """Dynamically installs and indexes a skill from a Git repository."""
    try:
        record = skill_importer.import_from_git(payload.url, custom_name=payload.name)
        return {
            "status": "success",
            "message": f"Successfully imported '{record.name}' into Hina's skill universe.",
            "skill": record.to_dict(),
        }
    except Exception as exc:
        logger.error("Failed importing skill from %s: %s", payload.url, exc)
        raise HTTPException(status_code=400, detail=str(exc))
