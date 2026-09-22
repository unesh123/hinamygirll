from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hinaa_api.brain_ledger import fingerprint_for, record_call
from hinaa_api.circuit_breaker import get_circuit_breaker, reset_circuit_breakers
from hinaa_api.config import Settings
from hinaa_api.main import create_app
from hinaa_api.services import ConversationService

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


def test_generated_images_listing_only_returns_files_that_exist_on_disk(client: TestClient) -> None:
    """The Library view used to render six fabricated demo rows because no list
    route existed. Every entry must be a real file that the item route serves."""
    from hinaa_api.config import DATA_DIR

    images_root = DATA_DIR / "images"
    images_root.mkdir(parents=True, exist_ok=True)
    probe = images_root / "hinaa_honesty_probe.png"
    # 1×1 transparent PNG.
    probe.write_bytes(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
            "890000000a49444154789c630001000005008115d1d20000000049454e44ae426082"
        )
    )
    created_size = probe.stat().st_size
    try:
        payload = client.get("/api/v1/generated-images?limit=5").json()
    finally:
        probe.unlink()

    assert isinstance(payload["images"], list)
    assert payload["count"] == len(payload["images"])

    probe_entries = [e for e in payload["images"] if e["filename"] == probe.name]
    assert len(probe_entries) == 1, "a file on disk must be listed exactly once"
    entry = probe_entries[0]
    assert entry["url"] == f"/api/v1/generated-images/{probe.name}"
    assert entry["sizeKb"] == round(created_size / 1024, 1)
    assert entry["created_at"], "every entry needs a real timestamp to display"

    for e in payload["images"]:
        if e["filename"] == probe.name:
            continue
        assert (images_root / e["filename"]).is_file(), e["filename"]
        served = client.get(e["url"])
        assert served.status_code == 200, e["url"]
        assert served.headers["content-type"].startswith("image/")


def test_generated_images_listing_is_served_under_both_route_prefixes(client: TestClient) -> None:
    assert client.get("/v1/generated-images").status_code == 200
    assert client.get("/api/v1/generated-images").status_code == 200


# Every brain configured except the ones left disabled above, so routing and
# health can be exercised against a deployment that looks like production.
MULTI_BRAIN = Settings(
    **{
        **DISABLED_RUNTIME.model_dump(),
        "HINAA_PROVIDER_MODE": "claude",
        "claude_api_key": "claude-key-for-tests",
        "codecraft_api_key": "codecraft-key-for-tests",
        "qwen_api_key": "qwen-key-for-tests",
        "gemini_api_key": "gemini-key-for-tests",
        "_env_file": None,
    }
)


@pytest.fixture(autouse=True)
def _clean_live_outcomes():
    """Breakers no longer feed the health badges — the brain ledger does, and
    every test already gets a fresh ledger file. They still cool down the
    fallback ladder, so a cooldown must not leak between tests."""
    reset_circuit_breakers()
    yield
    reset_circuit_breakers()


def _brain(client: TestClient, provider_id: str) -> dict[str, object]:
    return next(entry for entry in client.get("/api/v1/providers").json() if entry["id"] == provider_id)


def test_a_rejected_brain_is_reported_by_what_its_calls_did() -> None:
    with TestClient(create_app(MULTI_BRAIN)) as value:
        # A key nobody has called with yet is not ready — it is untested.
        configured = _brain(value, "claude")
        assert configured["state"] == "untested"
        assert "no live call" in configured["userMessage"]

        fingerprint = fingerprint_for(MULTI_BRAIN, "claude")
        record_call(
            "claude",
            ok=False,
            code="PROVIDER_KEY_INVALID",
            detail="Claude gateway rejected the request (HTTP 403).",
            fingerprint=fingerprint,
        )
        rejected = _brain(value, "claude")
        assert rejected["state"] == "unavailable"
        assert "403" in rejected["userMessage"]

        # A later call that answers is the only thing that clears the verdict.
        record_call("claude", ok=True, fingerprint=fingerprint)
        assert _brain(value, "claude")["state"] == "healthy"


async def test_fallback_candidates_rank_brains_by_answer_quality() -> None:
    candidates = await ConversationService(MULTI_BRAIN)._fallback_candidate_modes("claude")
    modes = [mode for mode, _model in candidates]

    # The pinned brain never competes with itself, the strongest remaining
    # frontier brain goes first, and the always-configured closer goes last.
    # `custom` ranks second because it reuses the CodeCraft credential.
    assert modes == ["codecraft", "custom", "qwen", "real"]
    assert all(model for _mode, model in candidates), "every candidate needs a model to call"


async def test_a_brain_in_cooldown_yields_to_one_that_can_answer() -> None:
    service = ConversationService(MULTI_BRAIN)
    get_circuit_breaker("codecraft").record_failure(
        "PROVIDER_RATE_LIMIT", "CodeCraft is rate limited right now.", retry_after=30.0
    )

    modes = [mode for mode, _model in await service._fallback_candidate_modes("claude")]

    # Demoted, not dropped: a throttled brain still beats ending the turn.
    assert modes == ["custom", "qwen", "real", "codecraft"]
