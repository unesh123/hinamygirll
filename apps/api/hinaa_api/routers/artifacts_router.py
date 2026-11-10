"""
Router for Phase 14 Artifact OS REST Surface.
Extracted from main.py to maintain modular enterprise architecture.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..artifacts.models import ArtifactFormat, MIME_TYPE_MAP
from ..artifacts.service import ArtifactService


class CreateDocumentArtifactBody(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=240)]
    content: Annotated[str, Field(max_length=500_000)]
    format: str = "md"
    projectId: str | None = None
    conversationId: str | None = None
    taskId: str | None = None
    tags: list[str] = Field(default_factory=list)


class CreatePresentationArtifactBody(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=240)]
    subtitle: str = ""
    slides: list[dict[str, Any]]
    projectId: str | None = None
    conversationId: str | None = None
    taskId: str | None = None


class CreateSpreadsheetArtifactBody(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=240)]
    sheets: list[dict[str, Any]]
    projectId: str | None = None
    conversationId: str | None = None
    taskId: str | None = None


class PackageArtifactsBody(BaseModel):
    artifactIds: list[str]
    bundleTitle: str = "Artifacts_Bundle"
    description: str = ""


def build_artifacts_router(
    artifact_service: ArtifactService,
    active_settings: Any,
) -> APIRouter:
    router = APIRouter(tags=["artifacts"])

    def _workspace_user_id(request: Request) -> str:
        auth_context = getattr(request.state, "auth", None)
        if auth_context and getattr(auth_context, "user_id", None):
            return str(auth_context.user_id)
        return str(getattr(active_settings, "dev_auth_subject", "dev-user"))

    @router.post("/v1/artifacts/documents", status_code=201)
    async def create_document_artifact(
        request: Request, body: CreateDocumentArtifactBody
    ) -> dict[str, Any]:
        user_id = _workspace_user_id(request)
        try:
            fmt = ArtifactFormat(body.format.lower())
        except ValueError:
            fmt = ArtifactFormat.MD
        record, doc_ast = artifact_service.create_document(
            user_id=user_id,
            title=body.title,
            content=body.content,
            project_id=body.projectId,
            conversation_id=body.conversationId,
            task_id=body.taskId,
            format=fmt,
            tags=body.tags,
        )
        inspection = artifact_service.inspector.inspect_document(doc_ast)
        return {
            "artifact": record.model_dump(mode="json"),
            "inspection": {
                "wordCount": inspection.word_count,
                "readingTimeMinutes": inspection.reading_time_minutes,
                "estimatedTokens": inspection.estimated_tokens,
                "qualityScore": inspection.quality_score,
                "passed": inspection.passed,
                "tocEntries": [
                    {"level": e.level, "title": e.title, "anchorId": e.anchor_id}
                    for e in inspection.table_of_contents
                ],
            },
            "downloadUrl": f"/v1/artifacts/{record.id}/export",
        }

    @router.post("/v1/artifacts/presentations", status_code=201)
    async def create_presentation_artifact(
        request: Request, body: CreatePresentationArtifactBody
    ) -> dict[str, Any]:
        user_id = _workspace_user_id(request)
        record, _ = artifact_service.create_presentation(
            user_id=user_id,
            title=body.title,
            slides_data=body.slides,
            subtitle=body.subtitle,
            project_id=body.projectId,
            conversation_id=body.conversationId,
            task_id=body.taskId,
        )
        return {
            "artifact": record.model_dump(mode="json"),
            "downloadUrl": f"/v1/artifacts/{record.id}/export?format=pptx",
        }

    @router.post("/v1/artifacts/spreadsheets", status_code=201)
    async def create_spreadsheet_artifact(
        request: Request, body: CreateSpreadsheetArtifactBody
    ) -> dict[str, Any]:
        user_id = _workspace_user_id(request)
        record, _ = artifact_service.create_spreadsheet(
            user_id=user_id,
            title=body.title,
            sheets_data=body.sheets,
            project_id=body.projectId,
            conversation_id=body.conversationId,
            task_id=body.taskId,
        )
        return {
            "artifact": record.model_dump(mode="json"),
            "downloadUrl": f"/v1/artifacts/{record.id}/export?format=xlsx",
        }

    @router.get("/v1/artifacts/{artifact_id}")
    async def get_artifact_endpoint(artifact_id: str) -> dict[str, Any]:
        art = artifact_service.get_artifact(artifact_id)
        if not art:
            raise HTTPException(status_code=404, detail="Artifact not found")
        return {"artifact": art.model_dump(mode="json")}

    @router.get("/v1/artifacts/{artifact_id}/inspect")
    async def inspect_artifact_endpoint(artifact_id: str) -> dict[str, Any]:
        try:
            report = artifact_service.inspect_artifact(artifact_id)
            return {"report": report}
        except KeyError:
            raise HTTPException(status_code=404, detail="Artifact not found")

    @router.get("/v1/artifacts/{artifact_id}/export")
    async def export_artifact_endpoint(artifact_id: str, format: str | None = None) -> Response:
        art = artifact_service.get_artifact(artifact_id)
        if not art:
            raise HTTPException(status_code=404, detail="Artifact not found")

        target_fmt_str = format or art.format.value
        try:
            target_fmt = ArtifactFormat(target_fmt_str.lower())
        except ValueError:
            target_fmt = art.format

        try:
            exported = artifact_service.export_artifact(artifact_id, target_fmt)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Export failed: {exc}") from exc

        media_type = MIME_TYPE_MAP.get(target_fmt, "application/octet-stream")
        filename = f"{art.title.lower().replace(' ', '_')[:40]}.{target_fmt.value}"
        content_bytes = exported if isinstance(exported, bytes) else exported.encode("utf-8")

        return Response(
            content=content_bytes,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )

    @router.post("/v1/artifacts/package")
    async def package_artifacts_endpoint(body: PackageArtifactsBody) -> Response:
        zip_bytes = artifact_service.package_artifacts(
            body.artifactIds, body.bundleTitle, body.description
        )
        filename = f"{body.bundleTitle.lower().replace(' ', '_')[:40]}_package.zip"
        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )

    return router
