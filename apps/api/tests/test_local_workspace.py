from fastapi.testclient import TestClient

from hinaa_api.config import Settings
from hinaa_api.main import create_app


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
        assert [item["title"] for item in payload["tasks"]] == ["Draft local image workflow"]
        assert [item["title"] for item in payload["artifacts"]] == ["Creator notes"]
        assert [item["name"] for item in payload["files"]] == ["brief.txt"]

        downloaded = client.get(f"/v1/projects/files/{file_record['id']}")
        assert downloaded.status_code == 200
        assert downloaded.content == b"Hinaa local workspace"
