from __future__ import annotations

import io
import os
import wave

# Test imports create app/tool singletons. Isolate their default storage before
# importing the runtime so no test writes to the owner's real memories/assets.
from pathlib import Path
from uuid import uuid4

_TEST_STATE = Path(__file__).resolve().parents[3] / ".runtime" / "test-state" / uuid4().hex
_TEST_STATE.mkdir(parents=True, exist_ok=True)
# Opt-in: run the suite against a real Postgres (CI service container or local).
TEST_PG_URL = os.environ.get("HINAA_TEST_DATABASE_URL", "").strip()
os.environ["HINAA_DATABASE_URL"] = TEST_PG_URL or f"sqlite+pysqlite:///{_TEST_STATE / 'test.db'}"
if TEST_PG_URL:
    os.environ.setdefault("HINAA_DB_POOL_SIZE", "2")
    os.environ.setdefault("HINAA_DB_MAX_OVERFLOW", "3")
os.environ["HINAA_LOCAL_WORKSPACE_DIR"] = str(_TEST_STATE / "workspace")
os.environ["HINAA_ASSET_STORE_DIR"] = str(_TEST_STATE / "assets")
os.environ["HINAA_VMC_PORT"] = "0"
# The suite was written against dev auth. Pin it so a developer's local
# .env.local (clerk mode, persistence on) cannot change what these tests mean.
# Auth-specific tests opt back into clerk explicitly through their own Settings.
os.environ["HINAA_AUTH_MODE"] = "dev"
os.environ["HINAA_PERSISTENCE_ENABLED"] = "false"
os.environ["HINAA_ALLOW_TUNNEL_DEV_AUTH"] = "false"

import pytest
from fastapi.testclient import TestClient

from hinaa_api.brain_ledger import reset_ledger
from hinaa_api.config import Settings
from hinaa_api.main import create_app
from hinaa_api.vmc_bridge import vmc_bridge


def pcm_wav(seconds: float = 0.08) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16_000)
        target.writeframes(b"\x01\x00" * int(16_000 * seconds))
    return output.getvalue()


@pytest.fixture
def settings() -> Settings:
    return Settings(
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
        HINAA_DATABASE_URL=TEST_PG_URL or "sqlite+pysqlite:///:memory:",
        HINAA_AUTH_MODE="dev",
        HINAA_PERSISTENCE_ENABLED=True,
        HINAA_VMC_PORT=0,
        _env_file=None,
    )


@pytest.fixture(autouse=True)
def _clean_postgres_state(monkeypatch, request):
    """With a Postgres test database, give every test empty tables and route
    file-path raw-SQL stores (tmp-dir .db files) to Postgres too; ``:memory:``
    stores stay on SQLite."""
    if not TEST_PG_URL or request.module.__name__.endswith("test_postgres_support"):
        yield
        return
    from sqlalchemy import text

    from hinaa_api.persistence import db as persistence_db
    from hinaa_api.persistence import sqlcompat

    original = sqlcompat.pg_target

    def _pg_target(db_path, *, is_default):
        if str(db_path) == ":memory:":
            return None
        return original(TEST_PG_URL, is_default=True)

    monkeypatch.setattr(sqlcompat, "pg_target", _pg_target)
    created_engines: list = []
    real_make_engine = persistence_db.make_engine

    def _tracking_make_engine(url):
        created = real_make_engine(url)
        created_engines.append(created)
        return created

    monkeypatch.setattr(persistence_db, "make_engine", _tracking_make_engine)
    engine = persistence_db.make_engine(TEST_PG_URL)
    with engine.begin() as conn:
        tables = conn.execute(
            text(
                "SELECT quote_ident(schemaname) || '.' || quote_ident(tablename) FROM pg_tables "
                "WHERE schemaname IN ('public', :rt) "
                "AND tablename NOT IN ('schema_migrations', 'alembic_version')"
            ),
            {"rt": sqlcompat.RUNTIME_SCHEMA},
        ).scalars().all()
        if tables:
            conn.execute(text("TRUNCATE " + ", ".join(tables) + " RESTART IDENTITY CASCADE"))
    engine.dispose()
    persistence_db.reset_session_factory()
    yield
    # Apps built per test leave engines behind; dispose them so a long run stays
    # under Postgres' max_connections.
    persistence_db.reset_session_factory()
    for created in created_engines:
        created.dispose()


@pytest.fixture(autouse=True)
def _reset_vmc_bridge():
    """Ensure the VMC singleton releases its UDP port between tests."""
    vmc_bridge.reset()
    yield
    vmc_bridge.reset()


@pytest.fixture(autouse=True)
def _isolated_brain_ledger(tmp_path):
    """Brain verdicts outlive the process by design, so the default ledger path
    is the file the running backend reads. A test must never write it."""
    previous = os.environ.get("HINAA_BRAIN_LEDGER_PATH")
    reset_ledger(tmp_path / "brain_outcomes.json")
    yield
    if previous is None:
        os.environ.pop("HINAA_BRAIN_LEDGER_PATH", None)
    else:
        os.environ["HINAA_BRAIN_LEDGER_PATH"] = previous
    reset_ledger()


@pytest.fixture
def client(settings: Settings) -> TestClient:
    # Loopback base_url so Host names the host machine: the effect policy in
    # tools/policy.py denies machine-touching tools to public-origin requests,
    # and "testserver" reads as one. tests/test_tool_policy.py passes an explicit
    # host header to cover both origins.
    # The dev identity header mirrors what the frontend sends: dev mode rejects
    # anonymous callers, so private-data routes need a named subject.
    with TestClient(
        create_app(settings),
        base_url="http://127.0.0.1:8000",
        headers={"X-HINAA-Dev-User": "test-local-user"},
    ) as value:
        yield value
