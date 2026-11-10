"""
Router for Phase 10 Long-Term Memory & Continuous Knowledge Graph Endpoints.
Extracted from main.py to maintain modular enterprise architecture.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request, Response

from ..memory import (
    CandidateStatus,
    CreateMemoryRequest,
    MemoryExportRequest,
    MemoryScope,
    MemorySearchRequest,
    MemoryService as Phase10MemoryService,
    MemoryType,
    ReviewCandidateRequest,
    UpdateMemoryRequest,
)


def build_memory_p10_router(p10_memory_service: Phase10MemoryService) -> APIRouter:
    router = APIRouter(tags=["memory_p10"])

    @router.post("/api/memory/items", status_code=201)
    @router.post("/v1/memory/items", status_code=201)
    async def create_memory_item(request: Request, body: Any = Body(...)) -> dict[str, Any]:
        """Create a durable memory record with contradiction detection and graph linking."""
        tenant_id = request.headers.get("X-Tenant-ID", "default")
        user_id = request.headers.get("X-User-ID", None)
        if isinstance(body, dict):
            payload = dict(body)
            if "tenant_id" not in payload or payload["tenant_id"] == "default":
                payload["tenant_id"] = tenant_id
            if user_id and ("user_id" not in payload or not payload["user_id"]):
                payload["user_id"] = user_id
            req = CreateMemoryRequest.model_validate(payload)
        else:
            req = body
        record = p10_memory_service.create_memory(req)
        return record.model_dump()

    @router.get("/api/memory/items")
    @router.get("/v1/memory/items")
    async def list_memory_items(
        request: Request,
        tenant_id: str | None = None,
        user_id: str | None = None,
        project_id: str | None = None,
        scope: str | None = None,
        memory_type: str | None = None,
        include_contradicted: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List tenant memories with scope and category filters."""
        eff_tenant = tenant_id or request.headers.get("X-Tenant-ID", "default")
        eff_user = user_id or request.headers.get("X-User-ID", None)
        mem_scope = MemoryScope(scope) if scope else None
        mem_type = MemoryType(memory_type) if memory_type else None
        records = p10_memory_service.list_memories(
            tenant_id=eff_tenant,
            user_id=eff_user,
            project_id=project_id,
            scope=mem_scope,
            memory_type=mem_type,
            include_contradicted=include_contradicted,
            limit=limit,
            offset=offset,
        )
        return {"items": [r.model_dump() for r in records], "count": len(records)}

    @router.get("/api/memory/items/{item_id}")
    @router.get("/v1/memory/items/{item_id}")
    async def get_memory_item(item_id: str, request: Request) -> dict[str, Any]:
        """Retrieve memory item with full provenance and confidence metrics."""
        tenant_id = request.headers.get("X-Tenant-ID", "default")
        record = p10_memory_service.get_memory(item_id, tenant_id=tenant_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"Memory item '{item_id}' not found.")
        return record.model_dump()

    @router.patch("/api/memory/items/{item_id}")
    @router.patch("/v1/memory/items/{item_id}")
    async def update_memory_item(item_id: str, request: Request, body: Any = Body(...)) -> dict[str, Any]:
        """Update or correct a memory item without destructive overwrites."""
        tenant_id = request.headers.get("X-Tenant-ID", "default")
        req = UpdateMemoryRequest.model_validate(body) if isinstance(body, dict) else body
        updated = p10_memory_service.update_memory(item_id, req, tenant_id=tenant_id)
        if not updated:
            raise HTTPException(status_code=404, detail=f"Memory item '{item_id}' not found.")
        return updated.model_dump()

    @router.delete("/api/memory/items/{item_id}")
    @router.delete("/v1/memory/items/{item_id}")
    async def delete_memory_item(item_id: str, request: Request) -> dict[str, Any]:
        """Hard-delete memory with cascade to FTS index and derived knowledge edges."""
        tenant_id = request.headers.get("X-Tenant-ID", "default")
        deleted = p10_memory_service.delete_memory(item_id, tenant_id=tenant_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Memory item '{item_id}' not found.")
        return {"deleted": True, "id": item_id}

    @router.post("/api/memory/search")
    @router.post("/v1/memory/search")
    async def search_memory_items(request: Request, body: Any = Body(...)) -> dict[str, Any]:
        """Hybrid retrieval combining FTS5 lexical match, dense embeddings, and graph traversal."""
        tenant_id = request.headers.get("X-Tenant-ID", "default")
        if isinstance(body, dict):
            payload = dict(body)
            if "tenant_id" not in payload or payload["tenant_id"] == "default":
                payload["tenant_id"] = tenant_id
            req = MemorySearchRequest.model_validate(payload)
        else:
            req = body
        results, tokens_used, truncated = p10_memory_service.search_memories(
            query=req.query,
            tenant_id=req.tenant_id,
            user_id=req.user_id,
            project_id=req.project_id,
            scope=req.scope,
            memory_type=req.memory_type,
            include_contradicted=req.include_contradicted,
            limit=req.limit,
            token_budget=req.token_budget,
        )
        return {
            "query": req.query,
            "results": [r.model_dump() for r in results],
            "total_found": len(results),
            "token_budget_used": tokens_used,
            "truncated": truncated,
        }

    @router.post("/api/memory/export")
    @router.post("/v1/memory/export")
    async def export_memory_items(request: Request, body: Any = Body(...)) -> Response:
        """Export tenant memory records in JSON or CSV format."""
        tenant_id = request.headers.get("X-Tenant-ID", "default")
        if isinstance(body, dict):
            payload = dict(body)
            if "tenant_id" not in payload or payload["tenant_id"] == "default":
                payload["tenant_id"] = tenant_id
            req = MemoryExportRequest.model_validate(payload)
        else:
            req = body
        content = p10_memory_service.export_memories(
            tenant_id=req.tenant_id,
            user_id=req.user_id,
            project_id=req.project_id,
            scope=req.scope,
            format_type=req.format,
        )
        media_type = "text/csv" if req.format.lower() == "csv" else "application/json"
        return Response(content=content, media_type=media_type)

    @router.get("/api/memory/knowledge/graph")
    @router.get("/v1/memory/knowledge/graph")
    async def get_memory_knowledge_graph(
        request: Request,
        entity_name: str | None = None,
        entity_type: str | None = None,
        max_depth: int = 2,
        max_nodes: int = 30,
        as_of_date: str | None = None,
    ) -> dict[str, Any]:
        """Fetch knowledge graph nodes and edges with bounded traversal and temporal filtering."""
        tenant_id = request.headers.get("X-Tenant-ID", "default")
        nodes, edges = p10_memory_service.get_knowledge_graph(
            tenant_id=tenant_id,
            entity_name=entity_name,
            entity_type=entity_type,
            max_depth=max_depth,
            max_nodes=max_nodes,
            as_of_date=as_of_date,
        )
        return {
            "nodes": [n.model_dump() for n in nodes],
            "edges": [e.model_dump() for e in edges],
            "total_nodes": len(nodes),
            "total_edges": len(edges),
        }

    @router.get("/api/memory/ingestion/candidates")
    @router.get("/v1/memory/ingestion/candidates")
    async def list_memory_candidates(
        request: Request,
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """List staged candidates discovered by CRAG, browser, or tools awaiting review."""
        tenant_id = request.headers.get("X-Tenant-ID", "default")
        cand_status = CandidateStatus(status) if status else None
        candidates = p10_memory_service.list_candidates(tenant_id=tenant_id, status=cand_status, limit=limit)
        return {"candidates": [c.model_dump() for c in candidates], "count": len(candidates)}

    @router.post("/api/memory/ingestion/{candidate_id}/review")
    @router.post("/v1/memory/ingestion/{candidate_id}/review")
    async def review_memory_candidate(candidate_id: str, request: Request, body: Any = Body(...)) -> dict[str, Any]:
        """Approve or reject a staged memory candidate."""
        tenant_id = request.headers.get("X-Tenant-ID", "default")
        req = ReviewCandidateRequest.model_validate(body) if isinstance(body, dict) else body
        candidate, promoted = p10_memory_service.review_candidate(
            candidate_id=candidate_id,
            decision=req.decision,
            tenant_id=tenant_id,
            review_notes=req.review_notes,
            promoted_scope=req.promoted_scope or MemoryScope.USER,
            promoted_type=req.promoted_type or MemoryType.FACT,
        )
        if not candidate:
            raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found.")
        return {
            "candidate": candidate.model_dump(),
            "promoted_memory": promoted.model_dump() if promoted else None,
        }

    @router.get("/api/memory/health")
    @router.get("/v1/memory/health")
    async def get_memory_health(request: Request) -> dict[str, Any]:
        """Health and telemetry report for the Phase 10 long-term memory engine."""
        tenant_id = request.headers.get("X-Tenant-ID", "default")
        stats = p10_memory_service.get_stats(tenant_id=tenant_id)
        return {"status": "healthy", "stats": stats.model_dump()}

    return router
