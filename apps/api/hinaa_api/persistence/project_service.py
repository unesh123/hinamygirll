from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from .orm import LocalProject, LocalProjectArtifact, LocalProjectFile, LocalProjectTask


class LocalProjectService:
    """Local-first project storage with metadata in SQLite and files on disk."""

    def __init__(self, factory: sessionmaker[Session], root: Path) -> None:
        self._factory = factory
        self._root = root.expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _slug(value: str) -> str:
        cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return cleaned[:48] or "project"

    def _project_dir(self, project: LocalProject) -> Path:
        path = Path(project.root_path).resolve()
        if self._root not in path.parents and path != self._root:
            raise ValueError("Project path is outside the local workspace.")
        return path

    @staticmethod
    def _project_public(project: LocalProject) -> dict[str, Any]:
        return {
            "id": project.id,
            "title": project.title,
            "description": project.description,
            "status": project.status,
            "createdAt": project.created_at.isoformat() if project.created_at else None,
            "updatedAt": project.updated_at.isoformat() if project.updated_at else None,
        }

    @staticmethod
    def _task_public(task: LocalProjectTask) -> dict[str, Any]:
        return {
            "id": task.id,
            "projectId": task.project_id,
            "parentTaskId": task.parent_task_id,
            "title": task.title,
            "detail": task.detail,
            "status": task.status,
            "requiresApproval": task.requires_approval,
            "position": task.position,
        }

    @staticmethod
    def _artifact_public(artifact: LocalProjectArtifact) -> dict[str, Any]:
        return {
            "id": artifact.id,
            "projectId": artifact.project_id,
            "kind": artifact.kind,
            "title": artifact.title,
            "content": artifact.content,
            "relativePath": artifact.relative_path,
            "sourceUrl": artifact.source_url,
            "metadata": json.loads(artifact.metadata_json or "{}"),
            "createdAt": artifact.created_at.isoformat() if artifact.created_at else None,
        }

    @staticmethod
    def _file_public(file: LocalProjectFile) -> dict[str, Any]:
        return {
            "id": file.id,
            "projectId": file.project_id,
            "name": file.name,
            "mediaType": file.media_type,
            "relativePath": file.relative_path,
            "sizeBytes": file.size_bytes,
            "createdAt": file.created_at.isoformat() if file.created_at else None,
        }

    def create_project(self, user_id: str, title: str, description: str = "") -> dict[str, Any]:
        with self._factory() as session:
            seed = self._slug(title)
            project = LocalProject(
                user_id=user_id,
                title=title.strip(),
                description=description.strip(),
                root_path=str(self._root),
            )
            session.add(project)
            session.flush()
            path = self._root / f"{seed}-{project.id[:8]}"
            project.root_path = str(path)
            path.mkdir(parents=True, exist_ok=True)
            (path / "files").mkdir(exist_ok=True)
            (path / "artifacts").mkdir(exist_ok=True)
            session.commit()
            return self._project_public(project)

    def list_projects(self, user_id: str) -> list[dict[str, Any]]:
        with self._factory() as session:
            projects = (
                session.query(LocalProject)
                .filter_by(user_id=user_id)
                .filter(LocalProject.archived_at.is_(None))
                .order_by(LocalProject.updated_at.desc(), LocalProject.created_at.desc())
                .all()
            )
            return [self._project_public(project) for project in projects]

    def project_detail(self, user_id: str, project_id: str) -> dict[str, Any] | None:
        with self._factory() as session:
            project = session.get(LocalProject, project_id)
            if project is None or project.user_id != user_id or project.archived_at is not None:
                return None
            tasks = (
                session.query(LocalProjectTask)
                .filter_by(project_id=project.id)
                .order_by(LocalProjectTask.position.asc(), LocalProjectTask.created_at.asc())
                .all()
            )
            artifacts = (
                session.query(LocalProjectArtifact)
                .filter_by(project_id=project.id)
                .order_by(LocalProjectArtifact.created_at.desc())
                .all()
            )
            files = (
                session.query(LocalProjectFile)
                .filter_by(project_id=project.id)
                .order_by(LocalProjectFile.created_at.desc())
                .all()
            )
            return {
                **self._project_public(project),
                "tasks": [self._task_public(task) for task in tasks],
                "artifacts": [self._artifact_public(artifact) for artifact in artifacts],
                "files": [self._file_public(file) for file in files],
            }

    def create_task(
        self,
        user_id: str,
        project_id: str,
        title: str,
        detail: str = "",
        parent_task_id: str | None = None,
        requires_approval: bool = False,
    ) -> dict[str, Any] | None:
        with self._factory() as session:
            project = session.get(LocalProject, project_id)
            if project is None or project.user_id != user_id:
                return None
            task = LocalProjectTask(
                project_id=project_id,
                parent_task_id=parent_task_id,
                title=title.strip(),
                detail=detail.strip(),
                requires_approval=requires_approval,
                position=session.query(LocalProjectTask).filter_by(project_id=project_id).count(),
            )
            session.add(task)
            session.commit()
            return self._task_public(task)

    def update_task_status(self, user_id: str, task_id: str, status: str) -> dict[str, Any] | None:
        with self._factory() as session:
            task = session.get(LocalProjectTask, task_id)
            project = session.get(LocalProject, task.project_id) if task else None
            if task is None or project is None or project.user_id != user_id:
                return None
            task.status = status
            session.commit()
            return self._task_public(task)

    def create_artifact(
        self,
        user_id: str,
        project_id: str,
        kind: str,
        title: str,
        content: str = "",
        source_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        with self._factory() as session:
            project = session.get(LocalProject, project_id)
            if project is None or project.user_id != user_id:
                return None
            artifact = LocalProjectArtifact(
                project_id=project_id,
                kind=kind,
                title=title.strip(),
                content=content,
                source_url=source_url,
                metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
            )
            session.add(artifact)
            session.commit()
            return self._artifact_public(artifact)

    def save_file(self, user_id: str, project_id: str, name: str, content: bytes, media_type: str) -> dict[str, Any] | None:
        safe_name = Path(name).name or "upload"
        with self._factory() as session:
            project = session.get(LocalProject, project_id)
            if project is None or project.user_id != user_id:
                return None
            project_dir = self._project_dir(project)
            target_dir = project_dir / "files"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / safe_name
            stem, suffix = target.stem, target.suffix
            index = 1
            while target.exists():
                target = target_dir / f"{stem}-{index}{suffix}"
                index += 1
            target.write_bytes(content)
            relative_path = str(target.relative_to(project_dir))
            record = LocalProjectFile(
                project_id=project_id,
                name=target.name,
                media_type=media_type or "application/octet-stream",
                relative_path=relative_path,
                size_bytes=len(content),
            )
            session.add(record)
            session.commit()
            return self._file_public(record)

    def resolve_file(self, user_id: str, file_id: str) -> tuple[Path, str] | None:
        with self._factory() as session:
            record = session.get(LocalProjectFile, file_id)
            project = session.get(LocalProject, record.project_id) if record else None
            if record is None or project is None or project.user_id != user_id:
                return None
            path = self._project_dir(project) / record.relative_path
            resolved = path.resolve()
            if not resolved.exists() or self._project_dir(project) not in resolved.parents:
                return None
            return resolved, record.media_type


    def create_starter_plan(
        self, user_id: str, project_id: str, goal: str
    ) -> list[dict[str, Any]] | None:
        """Create an editable local plan scaffold with explicit approval gating.

        This intentionally creates a transparent starter plan, not hidden agent
        execution. Hinaa or the user can refine individual tasks afterward.
        """
        clean_goal = goal.strip()
        if not clean_goal:
            return None
        with self._factory() as session:
            project = session.get(LocalProject, project_id)
            if project is None or project.user_id != user_id:
                return None
            root = LocalProjectTask(
                project_id=project_id,
                title=clean_goal,
                detail="Primary local project goal. Review the plan before any consequential action.",
                status="active",
                position=session.query(LocalProjectTask).filter_by(project_id=project_id).count(),
            )
            session.add(root)
            session.flush()
            milestones = [
                ("Clarify outcome and constraints", "Confirm scope, success criteria, privacy needs, and available local tools.", False),
                ("Gather context and source material", "Read local files or user-approved links; save useful findings as artifacts.", False),
                ("Create the working output", "Produce the requested draft, media, code, or structured result inside this project.", False),
                ("Review and approve next actions", "Check quality, save artifacts, and request explicit approval before external or destructive actions.", True),
            ]
            tasks: list[LocalProjectTask] = [root]
            for offset, (title, detail, approval) in enumerate(milestones, start=1):
                task = LocalProjectTask(
                    project_id=project_id,
                    parent_task_id=root.id,
                    title=title,
                    detail=detail,
                    status="waiting_approval" if approval else "pending",
                    requires_approval=approval,
                    position=root.position + offset,
                )
                session.add(task)
                tasks.append(task)
            session.commit()
            return [self._task_public(task) for task in tasks]
