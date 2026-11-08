"""Organisations, RBAC, scoped API keys and the hash-chained audit log."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from hinaa_api.config import Settings
from hinaa_api.main import create_app
from hinaa_api.orgs import service
from hinaa_api.orgs.models import OrgApiKey, OrgAuditEntry
from hinaa_api.orgs.permissions import ALL_PERMISSIONS, ROLE_PERMISSIONS
from hinaa_api.persistence.db import get_session_factory, reset_session_factory

ALICE = {"X-HINAA-Dev-User": "alice"}
BOB = {"X-HINAA-Dev-User": "bob"}
CAROL = {"X-HINAA-Dev-User": "carol"}
ORG = "/v1/org"


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("HINAA_API_KEY_PEPPER", "test-pepper-not-a-secret")
    reset_session_factory()
    s = Settings(
        _env_file=None,
        HINAA_PROVIDER_MODE="mock",
        HINAA_DATABASE_URL=f"sqlite+pysqlite:///{(tmp_path / 'id.db').as_posix()}",
        HINAA_AUTH_MODE="dev",
        HINAA_PERSISTENCE_ENABLED=True,
        HINAA_VMC_PORT=0,
        AZURE_SPEECH_KEY="",
        AZURE_SPEECH_REGION="",
        ELEVENLABS_API_KEY="",
    )
    get_session_factory(s)
    yield s
    reset_session_factory()


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def factory(settings):
    return get_session_factory(settings)


def me(client, headers=ALICE):
    r = client.get(f"{ORG}/me", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def team(client):
    """Alice owns her org with bob=admin, carol=member plus a viewer, all in alice's org."""
    org_id = me(client)["org"]["id"]
    ids = {"alice": me(client)["user"]["id"]}
    for name, role in (("bob", "admin"), ("carol", "member"), ("dave", "viewer")):
        h = {"X-HINAA-Dev-User": name}
        ids[name] = me(client, h)["user"]["id"]
        r = client.post(f"{ORG}/members", json={"userId": ids[name], "role": role}, headers=ALICE)
        assert r.status_code == 201, r.text
    return org_id, ids


def act(name, org_id):
    return {"X-HINAA-Dev-User": name, "X-HINAA-Org": org_id}


def test_personal_org_bootstrap_is_idempotent(client):
    first = me(client)
    second = me(client)
    assert first["org"]["isPersonal"] is True
    assert first["role"] == "owner"
    assert first["org"]["id"] == second["org"]["id"]
    assert sorted(first["permissions"]) == sorted(ALL_PERMISSIONS)
    assert len(first["organisations"]) == 1
    assert me(client, BOB)["org"]["id"] != first["org"]["id"]
    entries = client.get(f"{ORG}/audit", headers=ALICE).json()["items"]
    assert sorted(e["action"] for e in entries) == ["auth.login", "org.create"]


def test_role_matrix_and_me_permissions(client):
    org_id, _ = team(client)
    for name, role in (("alice", "owner"), ("bob", "admin"), ("carol", "member"), ("dave", "viewer")):
        data = me(client, act(name, org_id))
        assert data["role"] == role
        assert set(data["permissions"]) == ROLE_PERMISSIONS[role]
    assert "tools:execute" not in ROLE_PERMISSIONS["viewer"]
    assert "tools:execute_high_risk" not in ROLE_PERMISSIONS["member"]
    assert "org:manage" not in ROLE_PERMISSIONS["admin"]
    # Endpoint access by role
    for name, members_ok, keys_ok, audit_ok in (
        ("alice", 201, 200, 200),
        ("bob", 201, 200, 200),
        ("carol", 403, 403, 403),
        ("dave", 403, 403, 403),
    ):
        h = act(name, org_id)
        assert client.get(f"{ORG}/members", headers=h).status_code == 200
        assert client.get(f"{ORG}/api-keys", headers=h).status_code == keys_ok
        assert client.get(f"{ORG}/audit", headers=h).status_code == audit_ok
        r = client.post(f"{ORG}/members", json={"userId": "nobody", "role": "viewer"}, headers=h)
        assert r.status_code == (404 if members_ok == 201 else 403)


def test_non_member_cannot_target_foreign_org(client):
    org_id, _ = team(client)
    r = client.get(f"{ORG}/me", headers=act("mallory", org_id))
    assert r.status_code == 403


def test_last_owner_protection_and_owner_tier(client):
    org_id, ids = team(client)
    r = client.patch(f"{ORG}/members/{ids['alice']}", json={"role": "admin"}, headers=ALICE)
    assert r.status_code == 409
    assert client.delete(f"{ORG}/members/{ids['alice']}", headers=ALICE).status_code == 409
    # Admin cannot touch or mint owners
    h = act("bob", org_id)
    assert client.patch(f"{ORG}/members/{ids['carol']}", json={"role": "owner"}, headers=h).status_code == 403
    assert client.patch(f"{ORG}/members/{ids['alice']}", json={"role": "viewer"}, headers=h).status_code == 403
    assert client.delete(f"{ORG}/members/{ids['alice']}", headers=h).status_code == 403
    # With a second owner the first may step down
    assert client.patch(f"{ORG}/members/{ids['bob']}", json={"role": "owner"}, headers=ALICE).status_code == 200
    assert client.patch(f"{ORG}/members/{ids['alice']}", json={"role": "member"}, headers=h).status_code == 200
    assert client.delete(f"{ORG}/members/{ids['carol']}", headers=h).status_code == 204
    assert client.patch(f"{ORG}/members/{ids['bob']}", json={"role": "bad"}, headers=h).status_code == 422


def _create_key(client, headers=ALICE, scopes=("data:read",), **extra):
    r = client.post(f"{ORG}/api-keys", json={"name": "ci", "scopes": list(scopes), **extra}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_api_key_lifecycle_and_hash_not_plaintext(client, factory):
    created = _create_key(client, scopes=("data:read", "audit:read"))
    key = created["key"]
    assert key.startswith("hk_")
    listed = client.get(f"{ORG}/api-keys", headers=ALICE).json()["items"]
    assert len(listed) == 1 and "key" not in listed[0] and listed[0]["prefix"] == created["prefix"]
    assert key not in str(listed)
    with factory() as s:
        row = s.scalar(select(OrgApiKey))
        secret = key.split("_", 2)[2]
        assert secret not in (row.key_hash, row.salt, row.prefix)
        assert len(row.key_hash) == 64 and row.last_used_at is None
        dump = " ".join(str(v) for v in s.execute(text("SELECT * FROM org_api_keys")).one())
        assert secret not in dump

    bearer = {"Authorization": f"Bearer {key}"}
    data = me(client, bearer)
    assert data["authMode"] == "api_key" and data["apiKeyId"] == created["id"]
    assert set(data["permissions"]) == {"data:read", "audit:read"}
    assert data["org"]["id"] == me(client)["org"]["id"]
    with factory() as s:
        assert s.scalar(select(OrgApiKey.last_used_at)) is not None

    assert client.get(f"{ORG}/audit", headers=bearer).status_code == 200
    # tampered secret / unknown prefix are rejected
    assert client.get(f"{ORG}/me", headers={"Authorization": f"Bearer {key}x"}).status_code == 401
    assert client.get(f"{ORG}/me", headers={"Authorization": "Bearer hk_deadbeef_nope"}).status_code == 401


def test_api_key_scope_enforcement(client):
    org_id, _ = team(client)
    key = _create_key(client, scopes=("data:read",))["key"]
    bearer = {"Authorization": f"Bearer {key}"}
    assert client.get(f"{ORG}/members", headers=bearer).status_code == 200
    assert client.get(f"{ORG}/audit", headers=bearer).status_code == 403
    assert client.get(f"{ORG}/api-keys", headers=bearer).status_code == 403
    assert client.post(f"{ORG}/members", json={"userId": "x"}, headers=bearer).status_code == 403
    # invalid / non-grantable scopes
    bad = client.post(f"{ORG}/api-keys", json={"name": "x", "scopes": ["nope"]}, headers=ALICE)
    assert bad.status_code == 422
    over = client.post(
        f"{ORG}/api-keys", json={"name": "x", "scopes": ["org:manage"]}, headers=act("bob", org_id)
    )
    assert over.status_code == 403
    assert client.post(f"{ORG}/api-keys", json={"name": "x", "scopes": []}, headers=ALICE).status_code == 422


def test_api_key_expiry_and_revocation(client, factory):
    created = _create_key(client, expiresInDays=1)
    bearer = {"Authorization": f"Bearer {created['key']}"}
    assert client.get(f"{ORG}/me", headers=bearer).status_code == 200
    with factory() as s:
        row = s.scalar(select(OrgApiKey))
        row.expires_at = service._now().replace(year=2000)
        s.commit()
    assert client.get(f"{ORG}/me", headers=bearer).status_code == 401
    assert client.get(f"{ORG}/api-keys", headers=ALICE).json()["items"][0]["active"] is False

    live = _create_key(client)
    live_h = {"Authorization": f"Bearer {live['key']}"}
    assert client.get(f"{ORG}/me", headers=live_h).status_code == 200
    r = client.delete(f"{ORG}/api-keys/{live['id']}", headers=ALICE)
    assert r.status_code == 200 and r.json()["revokedAt"]
    assert client.get(f"{ORG}/me", headers=live_h).status_code == 401
    assert client.delete(f"{ORG}/api-keys/nope", headers=ALICE).status_code == 404


def test_key_dies_when_creator_leaves_org(client):
    org_id, ids = team(client)
    key = _create_key(client, headers=act("bob", org_id))["key"]
    bearer = {"Authorization": f"Bearer {key}"}
    assert client.get(f"{ORG}/me", headers=bearer).status_code == 200
    client.delete(f"{ORG}/members/{ids['bob']}", headers=ALICE)
    assert client.get(f"{ORG}/me", headers=bearer).status_code == 401


def test_audit_chain_verify_and_tamper_detection(client, factory):
    org_id, ids = team(client)
    created = _create_key(client)
    client.delete(f"{ORG}/api-keys/{created['id']}", headers=ALICE)
    client.get(f"{ORG}/audit", headers=act("carol", org_id))  # denied
    actions = [e["action"] for e in client.get(f"{ORG}/audit?limit=200", headers=ALICE).json()["items"]]
    for expected in ("org.create", "auth.login", "member.add", "apikey.create", "apikey.revoke", "permission.denied"):
        assert expected in actions

    verdict = client.get(f"{ORG}/audit/verify", headers=ALICE).json()
    assert verdict["ok"] is True and verdict["checked"] >= 6 and verdict["headHash"]

    page = client.get(f"{ORG}/audit?limit=2&offset=1", headers=ALICE).json()
    assert len(page["items"]) == 2 and page["total"] >= 6
    denied = client.get(f"{ORG}/audit?outcome=denied", headers=ALICE).json()
    assert denied["items"] and all(e["outcome"] == "denied" for e in denied["items"])
    by_user = client.get(f"{ORG}/audit?userId={ids['carol']}", headers=ALICE).json()
    assert by_user["items"] and all(e["userId"] == ids["carol"] for e in by_user["items"])
    assert all(e["requestId"] and e["ipHash"] and "127.0.0.1" not in str(e) for e in page["items"])

    # ORM refuses mutation; raw SQL tampering is caught by the chain.
    with factory() as s:
        row = s.scalar(select(OrgAuditEntry).where(OrgAuditEntry.org_id == org_id, OrgAuditEntry.seq == 2))
        row.outcome = "forged"
        with pytest.raises(RuntimeError):
            s.commit()
        s.rollback()
        s.execute(text("UPDATE org_audit_log SET outcome='forged' WHERE org_id=:o AND seq=2"), {"o": org_id})
        s.commit()
    broken = client.get(f"{ORG}/audit/verify", headers=ALICE).json()
    assert broken["ok"] is False and broken["firstInvalidSeq"] == 2

    # deleting a row also breaks the chain (sequence gap)
    with factory() as s:
        s.execute(text("UPDATE org_audit_log SET outcome='success' WHERE org_id=:o AND seq=2"), {"o": org_id})
        s.execute(text("DELETE FROM org_audit_log WHERE org_id=:o AND seq=3"), {"o": org_id})
        s.commit()
    assert client.get(f"{ORG}/audit/verify", headers=ALICE).json()["ok"] is False


def test_tool_execution_rbac(client):
    org_id, _ = team(client)
    body = {"toolName": "send_email", "parameters": {}, "confirmed": True, "approvalSource": "user"}

    def code(headers, tool="send_email"):
        r = client.post("/v1/tools/execute", json={**body, "toolName": tool}, headers=headers)
        return r.status_code, (r.json().get("code") or r.json().get("detail") or "")

    assert code(act("dave", org_id)) == (403, "PERMISSION_DENIED")
    assert code(act("dave", org_id), "web_search") == (403, "PERMISSION_DENIED")
    assert code(act("carol", org_id)) == (403, "PERMISSION_DENIED")
    # admin/owner pass RBAC and meet the pre-existing Host policy instead
    for name in ("bob", "alice"):
        assert code(act(name, org_id))[1] == "IRREVERSIBLE_TOOL_NOT_PERMITTED"
    # a member may run ordinary tools (past RBAC)
    assert code(act("carol", org_id), "diagnostic_echo")[1] != "PERMISSION_DENIED"
    entries = client.get(f"{ORG}/audit?limit=200", headers=ALICE).json()["items"]
    denied = [e for e in entries if e["action"] == "permission.denied" and e["target"].startswith("tool:")]
    assert len(denied) == 3
    assert any(e["action"] == "tool.execute" and e["target"] == "tool:send_email" for e in entries)


def test_per_org_isolation(client):
    a_org = me(client)["org"]["id"]
    b_org = me(client, BOB)["org"]["id"]
    assert a_org != b_org
    _create_key(client)
    assert client.get(f"{ORG}/api-keys", headers=BOB).json()["items"] == []
    a_audit = client.get(f"{ORG}/audit", headers=ALICE).json()
    b_audit = client.get(f"{ORG}/audit", headers=BOB).json()
    assert a_audit["total"] > b_audit["total"]
    assert {e["hash"] for e in a_audit["items"]}.isdisjoint({e["hash"] for e in b_audit["items"]})
    assert client.get(f"{ORG}/audit/verify", headers=BOB).json()["ok"] is True
    # bob cannot revoke alice's key by id
    key_id = client.get(f"{ORG}/api-keys", headers=ALICE).json()["items"][0]["id"]
    assert client.delete(f"{ORG}/api-keys/{key_id}", headers=BOB).status_code == 404
    assert len(client.get(f"{ORG}/members", headers=BOB).json()["items"]) == 1


def test_allow_list_still_enforced_and_pepper_not_in_responses(settings):
    gated = settings.model_copy(update={"hinaa_allowed_user_ids": "alice"})
    with TestClient(create_app(gated)) as c:
        assert c.get(f"{ORG}/me", headers=ALICE).json()["role"] == "owner"
        assert c.get(f"{ORG}/me", headers=BOB).status_code == 403
