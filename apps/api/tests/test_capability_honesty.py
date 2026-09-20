from __future__ import annotations

from fastapi.testclient import TestClient

from hinaa_api.config import Settings
from hinaa_api.main import create_app

DISABLED_RUNTIME = Settings(
    HINAA_PROVIDER_MODE="mock",
    AZURE_SPEECH_KEY="",
    AZURE_SPEECH_REGION="",
    GEMINI_API_KEY="",
    GROQ_API_KEY="",
    OPENAI_API_KEY="",
    OPENAI_CODEX_API_KEY="",
    OPENAI_CODEX_BASE_URL="",
    AGENT_ROUTER_API_KEY="",
    AGENT_ROUTER_BASE_URL="",
    CX_GATEWAY_API_KEY="",
    CX_GATEWAY_BASE_URL="",
    ELEVENLABS_API_KEY="",
    HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
    HINAA_AUTH_MODE="dev",
    HINAA_PERSISTENCE_ENABLED=False,
    HINAA_AGENT_RUNTIME_ENABLED=False,
    HINAA_VMC_PORT=0,
    _env_file=None,
)


def test_capabilities_never_report_a_worker_cluster(client: TestClient) -> None:
    features = client.get("/api/v1/capabilities").json()["features"]
    assert "agentCluster" not in features
    assert features["agentRuntime"] is True


def test_goal_and_artifact_flags_follow_the_settings_they_depend_on() -> None:
    with TestClient(create_app(DISABLED_RUNTIME)) as value:
        payload = value.get("/api/v1/capabilities").json()

    assert payload["modes"]["goal"] is False
    assert payload["features"]["goals"] is False
    assert payload["features"]["artifacts"] is False
    assert payload["features"]["memory"] is False


def test_commands_do_not_claim_ready_for_capabilities_their_dependency_disables() -> None:
    with TestClient(create_app(DISABLED_RUNTIME)) as value:
        commands = {
            entry["capability"]: entry["availability"]
            for entry in value.get("/api/v1/commands").json()["commands"]
        }

    assert commands["memory"] == "unavailable"
    assert commands["planning"] == "unavailable"
    assert commands["agent_goal"] == "unavailable"
    assert commands["voice_config"] == "unconfigured"
    assert commands["web_search"] == "unconfigured"
    for brain_backed in ("summarization", "analysis", "model_selection"):
        assert commands[brain_backed] == "unconfigured", brain_backed


def test_github_integration_reports_the_credential_that_is_actually_set() -> None:
    with TestClient(create_app(DISABLED_RUNTIME)) as value:
        unconfigured = value.get("/api/v1/capabilities").json()["integrations"]["github"]

    assert unconfigured == {"configured": False, "defaultRepo": None, "served": False}

    tokened = Settings(
        **{
            **DISABLED_RUNTIME.model_dump(),
            "github_token": "ghp_not_a_real_token",
            "github_default_repo": "owner/repo",
        }
    )
    with TestClient(create_app(tokened)) as value:
        configured = value.get("/api/v1/capabilities").json()["integrations"]["github"]

    assert configured["configured"] is True
    assert configured["defaultRepo"] == "owner/repo"
    # A credential is not an integration: github_flow.py has no caller, so this
    # must stay False until a route actually serves it.
    assert configured["served"] is False
