"""B3 RepositoryMap & GitWorkspace Comprehensive Acceptance Tests (Directives §1–§9).

Verifies:
1. AST parsing and symbol graph extraction across Python and TypeScript/React.
2. Call graph and test mapping links (refresh_route -> handle_refresh_token -> TokenStore.get_token, test_refresh_token_fails_after_expiry -> handle_refresh_token).
3. Multi-modal neighborhood retrieval for bug: 'Refresh token fails after expiry'.
4. Dirty worktree safety: isolates task changes while preserving unrelated dirty files.
5. GitHub permission hierarchy enforcement (READ_ONLY vs WORKSPACE_WRITE vs PUSH_BRANCH vs MERGE_PR).
"""

from __future__ import annotations

import os
import tempfile
import pytest

from hinaa_api.repository.models import (
    DirtyFile,
    GitHubPermission,
    RelationType,
    SymbolKind,
    check_github_permission,
)
from hinaa_api.repository.mapper import RepositoryMapper
from hinaa_api.repository.search import RepositorySearchEngine
from hinaa_api.repository.workspace import GitWorkspaceService


@pytest.fixture
def auth_fixture_repo(tmp_path):
    """Creates a realistic repository fixture for auth bug reproduction."""
    # 1. auth/tokens.py
    auth_dir = tmp_path / "auth"
    auth_dir.mkdir()
    tokens_py = auth_dir / "tokens.py"
    tokens_py.write_text(
        '"""Authentication token storage and refresh logic."""\n\n'
        'class TokenStore:\n'
        '    """Manages persistent token lifecycles in PostgreSQL."""\n'
        '    def get_token(self, token_id: str) -> dict:\n'
        '        return {"id": token_id, "expired": False}\n\n'
        '    def revoke_token(self, token_id: str) -> None:\n'
        '        pass\n\n'
        'def handle_refresh_token(refresh_token: str) -> dict:\n'
        '    """Validates refresh token and rotates token pair."""\n'
        '    store = TokenStore()\n'
        '    token = store.get_token(refresh_token)\n'
        '    if token.get("expired"):\n'
        '        raise ValueError("Token expired")\n'
        '    return {"access_token": "new_acc", "refresh_token": "new_ref"}\n',
        encoding="utf-8",
    )

    # 2. api/routes.py
    api_dir = tmp_path / "api"
    api_dir.mkdir()
    routes_py = api_dir / "routes.py"
    routes_py.write_text(
        '"""API routes for authentication."""\n'
        'from auth.tokens import handle_refresh_token\n\n'
        '@app.post("/auth/refresh")\n'
        'def refresh_route(req: dict) -> dict:\n'
        '    token_str = req.get("refresh_token")\n'
        '    return handle_refresh_token(token_str)\n',
        encoding="utf-8",
    )

    # 3. tests/test_auth.py
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    test_auth_py = tests_dir / "test_auth.py"
    test_auth_py.write_text(
        '"""Tests for authentication pipeline."""\n'
        'from auth.tokens import handle_refresh_token\n\n'
        'def test_refresh_token_fails_after_expiry():\n'
        '    # Bug scenario: expired refresh token must return 401\n'
        '    res = handle_refresh_token("expired_sample")\n'
        '    assert res is not None\n',
        encoding="utf-8",
    )

    # 4. frontend/AuthModal.tsx
    fe_dir = tmp_path / "frontend"
    fe_dir.mkdir()
    auth_modal_tsx = fe_dir / "AuthModal.tsx"
    auth_modal_tsx.write_text(
        'import React, { useState } from "react";\n\n'
        'export function useAuthSession() {\n'
        '    return { user: "admin", authenticated: true };\n'
        '}\n\n'
        'export const AuthModal: React.FC = () => {\n'
        '    const session = useAuthSession();\n'
        '    return <div>{session.user}</div>;\n'
        '};\n',
        encoding="utf-8",
    )

    return tmp_path


class TestRepositoryMapB3:
    def test_repository_mapper_extracts_ast_symbols_and_relations(self, auth_fixture_repo) -> None:
        mapper = RepositoryMapper(str(auth_fixture_repo))
        repo_map = mapper.scan_and_map()

        assert repo_map.file_count == 4
        assert "python" in repo_map.language_counts
        assert "typescript-react" in repo_map.language_counts

        graph = repo_map.graph
        
        # Check Python symbols
        token_store = graph.find_symbols("TokenStore", exact=True)
        assert len(token_store) == 1
        assert token_store[0].kind == SymbolKind.CLASS

        refresh_handler = graph.find_symbols("handle_refresh_token")
        assert len(refresh_handler) == 1
        assert refresh_handler[0].kind == SymbolKind.FUNCTION

        refresh_route = graph.find_symbols("refresh_route")
        assert len(refresh_route) == 1
        assert refresh_route[0].kind == SymbolKind.ROUTE

        test_func = graph.find_symbols("test_refresh_token_fails_after_expiry")
        assert len(test_func) == 1
        assert test_func[0].kind == SymbolKind.FUNCTION

        # Check TypeScript React symbols
        hook_sym = graph.find_symbols("useAuthSession")
        assert len(hook_sym) == 1
        assert hook_sym[0].kind == SymbolKind.HOOK

        comp_sym = graph.find_symbols("AuthModal")
        assert len(comp_sym) == 1
        assert comp_sym[0].kind == SymbolKind.COMPONENT

        # Check Relations (Call graph and Test graph)
        handler_id = refresh_handler[0].symbol_id
        route_id = refresh_route[0].symbol_id
        test_id = test_func[0].symbol_id

        # Route calls handler
        route_neighborhood = graph.get_neighborhood(route_id)
        assert any(c.name == "handle_refresh_token" for c in route_neighborhood["callees"])

        # Handler has caller 'refresh_route' and test 'test_refresh_token_fails_after_expiry'
        handler_neighborhood = graph.get_neighborhood(handler_id)
        caller_names = [c.name for c in handler_neighborhood["callers"]]
        test_names = [t.name for t in handler_neighborhood["tests"]]
        callee_names = [c.name for c in handler_neighborhood["callees"]]

        assert "refresh_route" in caller_names
        assert "test_refresh_token_fails_after_expiry" in test_names
        assert any("get_token" in name for name in callee_names)

    def test_multimodal_neighborhood_search(self, auth_fixture_repo) -> None:
        """Acceptance test: Searching 'Refresh token fails after expiry' retrieves the target and its neighborhood."""
        mapper = RepositoryMapper(str(auth_fixture_repo))
        repo_map = mapper.scan_and_map()
        engine = RepositorySearchEngine(repo_map)

        results = engine.search("refresh token expiry")
        assert len(results) >= 1

        top = results[0]
        # Top hit is handle_refresh_token or test
        assert "refresh_token" in top.symbol.name

        # Formatted output includes callers, callees, tests, and code context
        context_str = engine.format_search_context("refresh token expiry", results)
        assert "REPOSITORY NEIGHBORHOOD SEARCH" in context_str
        assert "handle_refresh_token" in context_str
        assert "```" in context_str

    def test_dirty_worktree_safety_and_file_isolation(self) -> None:
        """P0.15 / B3 §7: Verify task files are isolated while unrelated dirty files are preserved."""
        service = GitWorkspaceService(root_path=".", permission=GitHubPermission.WORKSPACE_WRITE)
        
        dirty_files = [
            DirtyFile(path="auth/tokens.py", status="M", is_staged=False),
            DirtyFile(path="auth/models.py", status="A", is_staged=True),
            DirtyFile(path="secret_user_scratchpad.py", status="??", is_staged=False),
            DirtyFile(path=".env.local", status="M", is_staged=False),
        ]

        task_allowed = {"auth/tokens.py", "auth/models.py"}
        task_dirty, unrelated_dirty = service.filter_task_changes(task_allowed, dirty_files)

        assert len(task_dirty) == 2
        assert {df.path for df in task_dirty} == {"auth/tokens.py", "auth/models.py"}

        assert len(unrelated_dirty) == 2
        assert {df.path for df in unrelated_dirty} == {"secret_user_scratchpad.py", ".env.local"}

    def test_github_permission_hierarchy(self) -> None:
        """P0.15 / B3 §8: Enforces permission hierarchy and action restrictions."""
        # Read only permits reading, forbids writing
        ro_service = GitWorkspaceService(root_path=".", permission=GitHubPermission.READ_ONLY)
        ro_service.verify_action_allowed("read")
        ro_service.verify_action_allowed("search")
        with pytest.raises(PermissionError):
            ro_service.verify_action_allowed("edit")
        with pytest.raises(PermissionError):
            ro_service.verify_action_allowed("commit")

        # Workspace write permits edit, forbids push
        ww_service = GitWorkspaceService(root_path=".", permission=GitHubPermission.WORKSPACE_WRITE)
        ww_service.verify_action_allowed("edit")
        ww_service.verify_action_allowed("create_file")
        with pytest.raises(PermissionError):
            ww_service.verify_action_allowed("push")

        # Commit permits committing, forbids pushing
        commit_service = GitWorkspaceService(root_path=".", permission=GitHubPermission.COMMIT)
        commit_service.verify_action_allowed("commit")
        with pytest.raises(PermissionError):
            commit_service.verify_action_allowed("push_branch")

        # Push branch permits push, forbids merge PR
        push_service = GitWorkspaceService(root_path=".", permission=GitHubPermission.PUSH_BRANCH)
        push_service.verify_action_allowed("push_branch")
        with pytest.raises(PermissionError):
            push_service.verify_action_allowed("merge_pr")

        # Merge PR permits all
        merge_service = GitWorkspaceService(root_path=".", permission=GitHubPermission.MERGE_PR)
        merge_service.verify_action_allowed("merge_pr")
        merge_service.verify_action_allowed("push_branch")
        merge_service.verify_action_allowed("edit")
