from __future__ import annotations

import httpx
import pytest

from hinaa_api.integrations_hub import connectors, github_repos


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("HINAA_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setattr(connectors, "_settings", lambda: None)
    for name in ("GITHUB_TOKEN", "EXA_API_KEY", "APP_CUSTOMGPT_AI_API_KEY", "APP_COUSTOMGPT_AI_API_KEY",
                 "CUSTOMGPT_API_KEY", "FREEPIK_API_KEY", "MAGNIFIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def test_configured_detection_checks_presence_only(monkeypatch):
    exa = connectors.get_connector("exa")
    assert not connectors.describe(exa)["configured"]
    monkeypatch.setenv("EXA_API_KEY", "super-secret-value")
    info = connectors.describe(exa)
    assert info["configured"] and info["missingEnv"] == []
    assert "super-secret-value" not in repr(info)
    assert "exa_search" in info["tools"]


def test_alias_keys_satisfy_requirement(monkeypatch):
    assert not connectors.describe(connectors.get_connector("customgpt"))["configured"]
    monkeypatch.setenv("APP_COUSTOMGPT_AI_API_KEY", "x")  # legacy misspelling still works
    assert connectors.describe(connectors.get_connector("customgpt"))["configured"]
    monkeypatch.setenv("FREEPIK_API_KEY", "x")
    assert connectors.describe(connectors.get_connector("freepik"))["configured"]


def test_tools_cross_reference_registry():
    from hinaa_api.tools.registry import registry

    names = {t.name for t in registry.get_all_tools()}
    for connector in connectors.CONNECTORS:
        assert connectors.describe(connector, registered_tools=names)["tools"] == [
            t for t in connector.tools if t in names
        ]


def test_integrations_endpoints(client, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret")
    body = client.get("/v1/integrations").json()
    ids = {i["id"] for i in body["integrations"]}
    assert {"github", "exa", "notion", "spotify", "outlook", "gamma", "tinyfish"} <= ids
    assert next(i for i in body["integrations"] if i["id"] == "github")["configured"] is True
    assert "ghp_secret" not in client.get("/api/v1/integrations/github").text
    assert client.get("/v1/integrations/nope").status_code == 404


def _gh_transport(calls):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        assert request.headers["authorization"] == "Bearer ghp_test"
        path, page = request.url.path, int(request.url.params.get("page", "1"))
        if path == "/user/repos":
            if page == 1:
                repos = [{"full_name": f"me/r{i}", "private": i == 0} for i in range(2)]
                return httpx.Response(200, json=repos)
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    return httpx.MockTransport(handler)


async def test_list_repos_paginates(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setattr("hinaa_api.config.get_settings", lambda: type("S", (), {"github_token": None})())
    calls: list[str] = []
    monkeypatch.setattr(github_repos, "transport", _gh_transport(calls))
    repos = await github_repos.list_repos(per_page=2)
    assert [r["fullName"] for r in repos] == ["me/r0", "me/r1"]
    assert repos[0]["private"] is True
    assert len(calls) == 2  # full first page triggers a second request


async def test_list_repos_installation_fallback(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setattr("hinaa_api.config.get_settings", lambda: type("S", (), {"github_token": None})())

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user/repos":
            return httpx.Response(403)
        return httpx.Response(200, json={"repositories": [{"full_name": "org/app"}]})

    monkeypatch.setattr(github_repos, "transport", httpx.MockTransport(handler))
    assert [r["fullName"] for r in await github_repos.list_repos()] == ["org/app"]


def test_github_repos_and_active_endpoints(client, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setattr("hinaa_api.config.get_settings", lambda: type("S", (), {"github_token": None})())
    monkeypatch.setattr(github_repos, "transport", _gh_transport([]))
    assert client.get("/v1/integrations/github/active-repos").json()["repos"] == []
    saved = client.post("/v1/integrations/github/active-repos", json={"repos": ["me/r1", "me/r1"]})
    assert saved.json()["repos"] == ["me/r1"]
    bad = client.post("/v1/integrations/github/active-repos", json={"repos": ["not a repo"]})
    assert bad.status_code == 400
    listing = client.get("/v1/integrations/github/repos").json()
    assert {r["fullName"]: r["active"] for r in listing["repos"]} == {"me/r0": False, "me/r1": True}


def test_github_repos_requires_token(client, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setattr("hinaa_api.config.get_settings", lambda: type("S", (), {"github_token": None})())
    assert client.get("/v1/integrations/github/repos").status_code == 400
