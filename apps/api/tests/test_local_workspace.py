from fastapi.testclient import TestClient

from hinaa_api.config import Settings
from hinaa_api.main import create_app
from hinaa_api.persistence.db import get_session_factory
from hinaa_api.persistence.orm import LocalProject


def test_local_comfyui_status_is_actionable(tmp_path) -> None:
    settings = Settings(
        HINAA_PROVIDER_MODE="mock",
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
        HINAA_PERSISTENCE_ENABLED=False,
        HINAA_LOCAL_WORKSPACE_DIR=tmp_path,
        _env_file=None,
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/v1/local-services/comfyui")
    assert response.status_code in {200, 503}
    payload = response.json()
    assert payload["service"] == "ComfyUI"
    assert payload["localOnly"] is True
    assert payload["status"] in {"ready", "unavailable"}


def test_local_project_workspace_round_trip(tmp_path) -> None:
    settings = Settings(
        HINAA_PROVIDER_MODE="mock",
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
        HINAA_PERSISTENCE_ENABLED=False,
        HINAA_LOCAL_WORKSPACE_DIR=tmp_path,
        _env_file=None,
    )

    with TestClient(create_app(settings)) as client:
        created = client.post(
            "/v1/projects",
            json={"title": "Launch Hinaa Studio", "description": "Private creator work"},
        )
        assert created.status_code == 201
        project = created.json()
        assert project["title"] == "Launch Hinaa Studio"

        plan = client.post(
            f"/v1/projects/{project['id']}/plans",
            json={"goal": "Prepare a local creator launch plan"},
        )
        assert plan.status_code == 201
        assert len(plan.json()) == 5
        assert plan.json()[-1]["requiresApproval"] is True

        task = client.post(
            f"/v1/projects/{project['id']}/tasks",
            json={
                "title": "Draft local image workflow",
                "detail": "Use ComfyUI only after user approval.",
                "requiresApproval": True,
            },
        )
        assert task.status_code == 201
        assert task.json()["requiresApproval"] is True

        artifact = client.post(
            f"/v1/projects/{project['id']}/artifacts",
            json={
                "kind": "research",
                "title": "Creator notes",
                "content": "Use a locally installed image workflow.",
                "metadata": {"sourceCount": 0},
            },
        )
        assert artifact.status_code == 201

        upload = client.post(
            f"/v1/projects/{project['id']}/files",
            files={"file": ("brief.txt", b"Hinaa local workspace", "text/plain")},
        )
        assert upload.status_code == 201
        file_record = upload.json()

        detail = client.get(f"/v1/projects/{project['id']}")
        assert detail.status_code == 200
        payload = detail.json()
        assert "Prepare a local creator launch plan" in [item["title"] for item in payload["tasks"]]
        assert "Draft local image workflow" in [item["title"] for item in payload["tasks"]]
        assert [item["title"] for item in payload["artifacts"]] == ["Creator notes"]
        assert [item["name"] for item in payload["files"]] == ["brief.txt"]

        downloaded = client.get(f"/v1/projects/files/{file_record['id']}")
        assert downloaded.status_code == 200
        assert downloaded.content == b"Hinaa local workspace"


def test_local_project_uses_resolved_owner_not_schema_placeholder(tmp_path) -> None:
    settings = Settings(
        HINAA_PROVIDER_MODE="mock",
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
        HINAA_PERSISTENCE_ENABLED=False,
        HINAA_DEV_AUTH_SUBJECT="unesh-local",
        HINAA_LOCAL_WORKSPACE_DIR=tmp_path,
        _env_file=None,
    )
    with TestClient(create_app(settings)) as client:
        created = client.post("/v1/projects", json={"title": "Owned local workspace"})
        assert created.status_code == 201
        project_id = created.json()["id"]

        with get_session_factory(settings)() as session:
            record = session.get(LocalProject, project_id)
            assert record is not None
            assert record.user_id == "unesh-local"
            assert record.user_id != "local-user"


def test_local_agent_run_lifecycle_is_durable_and_explicit(tmp_path) -> None:
    settings = Settings(
        HINAA_PROVIDER_MODE="mock",
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
        HINAA_PERSISTENCE_ENABLED=False,
        HINAA_LOCAL_WORKSPACE_DIR=tmp_path,
        _env_file=None,
    )
    with TestClient(create_app(settings)) as client:
        project = client.post("/v1/projects", json={"title": "Agent run project"}).json()
        task = client.post(
            f"/v1/projects/{project['id']}/tasks",
            json={"title": "Publish results", "requiresApproval": True},
        ).json()
        created = client.post(
            f"/v1/projects/{project['id']}/runs",
            json={"goal": "Prepare a safe release", "rootTaskId": task["id"]},
        )
        assert created.status_code == 201
        run = created.json()
        assert run["status"] == "waiting_approval"
        assert [event["kind"] for event in run["events"]] == ["run", "approval"]

        resumed = client.patch(
            f"/v1/projects/runs/{run['id']}",
            json={"status": "running", "summary": "User approved the release review."},
        )
        assert resumed.status_code == 200
        assert resumed.json()["status"] == "running"
        assert resumed.json()["events"][-1]["label"] == "Run resumed"

        completed = client.patch(
            f"/v1/projects/runs/{run['id']}",
            json={"status": "completed", "summary": "Release review completed locally."},
        )
        assert completed.status_code == 200
        assert completed.json()["completedAt"] is not None

        detail = client.get(f"/v1/projects/{project['id']}")
        assert detail.status_code == 200
        assert detail.json()["runs"][0]["status"] == "completed"
        assert len(detail.json()["runs"][0]["events"]) == 4


def test_local_project_artifact_exports_as_markdown(tmp_path) -> None:
    settings = Settings(
        HINAA_PROVIDER_MODE="mock",
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
        HINAA_PERSISTENCE_ENABLED=False,
        HINAA_LOCAL_WORKSPACE_DIR=tmp_path,
        _env_file=None,
    )
    with TestClient(create_app(settings)) as client:
        project = client.post("/v1/projects", json={"title": "Export project"}).json()
        artifact = client.post(
            f"/v1/projects/{project['id']}/artifacts",
            json={
                "kind": "research",
                "title": "Local research brief",
                "content": "A private, portable research note.",
                "sourceUrl": "https://example.com/source",
            },
        ).json()
        exported = client.get(f"/v1/projects/artifacts/{artifact['id']}/export")

    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/markdown")
    assert "# Local research brief" in exported.text
    assert "https://example.com/source" in exported.text
