from fastapi.testclient import TestClient

from hinaa_api.config import Settings
from hinaa_api.main import create_app


def _client(tmp_path):
    return TestClient(
        create_app(
            Settings(
                HINAA_PROVIDER_MODE="mock",
                HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
                HINAA_PERSISTENCE_ENABLED=True,
                HINAA_AUTH_MODE="dev",
                HINAA_LOCAL_WORKSPACE_DIR=tmp_path,
                _env_file=None,
            )
        )
    )


def test_conversation_compatibility_list_is_authenticated(tmp_path):
    with _client(tmp_path) as client:
        response = client.get("/v1/conversations")
    assert response.status_code == 200
    assert response.json() == []


def test_run_events_and_code_file_listing_are_scoped_routes(tmp_path):
    with _client(tmp_path) as client:
        project = client.post("/v1/projects", json={"title": "Phase 1"}).json()
        run = client.post(f"/v1/projects/{project['id']}/runs", json={"goal": "Write code"}).json()
        created = client.post(
            f"/v1/projects/{project['id']}/code/files",
            json={"path": "src/app.py", "content": "print('ok')", "runId": run["id"]},
        )
        assert created.status_code == 201
        files = client.get(f"/v1/projects/{project['id']}/code/files")
        events = client.get(f"/v1/projects/runs/{run['id']}/events")

    assert files.status_code == 200
    assert files.json()[0]["path"] == "src/app.py"
    assert events.status_code == 200
    assert events.json()["events"][-1]["kind"] == "code"
