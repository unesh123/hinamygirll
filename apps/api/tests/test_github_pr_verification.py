from unittest.mock import AsyncMock

import pytest

from hinaa_api.errors import HinaaError
from hinaa_api.tools.github_tools import _GithubClient, github_create_pull_request_handler


@pytest.fixture
def github_client(monkeypatch):
    monkeypatch.setattr(_GithubClient, "__init__", lambda self: None)
    post = AsyncMock(return_value={"number": 12})
    get = AsyncMock(return_value={
        "number": 12, "html_url": "https://github.com/owner/repo/pull/12",
        "head": {"ref": "task"}, "base": {"ref": "main"},
        "state": "open", "draft": True,
    })
    monkeypatch.setattr(_GithubClient, "post_json", post)
    monkeypatch.setattr(_GithubClient, "get_json", get)
    return post, get


PARAMS = {"repo": "owner/repo", "head": "task", "base": "main", "title": "Repair"}


async def test_registered_pr_tool_creates_and_reads_back_draft(github_client):
    post, get = github_client
    result = await github_create_pull_request_handler(PARAMS)
    assert post.call_args.args[1]["draft"] is True
    get.assert_awaited_once_with("/repos/owner/repo/pulls/12")
    assert result["url"] == "https://github.com/owner/repo/pull/12"
    assert result["draft"] is True


@pytest.mark.parametrize("field,value", [("html_url", "https://github.com/mock-repo/pull/12"), ("draft", False), ("state", "closed"), ("head", {"ref": "wrong"})])
async def test_registered_tool_rejects_unverified_result(github_client, field, value):
    post, get = github_client
    get.return_value[field] = value
    with pytest.raises(HinaaError) as error:
        await github_create_pull_request_handler(PARAMS)
    assert error.value.code == "GITHUB_PR_UNVERIFIED"


async def test_missing_number_is_not_a_completed_pr(github_client):
    post, get = github_client
    post.return_value = {}
    with pytest.raises(HinaaError):
        await github_create_pull_request_handler(PARAMS)
    get.assert_not_awaited()


async def test_permission_failure_does_not_become_success(github_client):
    post, get = github_client
    post.side_effect = HinaaError("GITHUB_API_ERROR", "GitHub API 403", 502, True)
    with pytest.raises(HinaaError):
        await github_create_pull_request_handler(PARAMS)
    get.assert_not_awaited()
