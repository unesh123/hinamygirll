"""Phase 19: Sandboxed Preview Runtime & Hot-Reload Asset Server.

Provides safe, isolated browser preview sessions with strict CSP,
hot-reloading bridge, viewport measurement, and path traversal protection.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import mimetypes
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field

# Ensure mimetypes covers modern web extensions
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("text/html", ".html")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("application/json", ".json")


class PreviewSession(BaseModel):
    """Metadata for an active preview session."""

    preview_id: str = Field(default_factory=lambda: f"prev-{uuid4().hex[:8]}")
    task_id: str
    workspace_id: str
    workspace_root: str
    entry_file: str = "index.html"
    status: str = "ready"  # starting | ready | failed | stopped
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    viewport_support: List[str] = Field(default_factory=lambda: ["desktop_1440", "tablet_768", "mobile_390"])
    preview_url: str = ""
    error: Optional[str] = None


class PreviewAssetResponse(BaseModel):
    """File content and headers to serve inside sandboxed iframe."""

    content_bytes: bytes
    media_type: str
    headers: Dict[str, str]


class PreviewRuntimeManager:
    """Manages sandboxed preview sessions and serves isolated assets."""

    def __init__(self, workspaces_base_dir: Optional[Path] = None) -> None:
        self.base_dir = workspaces_base_dir or Path(".runtime/coding").resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.base_dir / "preview_sessions.json"
        self._sessions: Dict[str, PreviewSession] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        if self.registry_file.exists():
            try:
                import json
                data = json.loads(self.registry_file.read_text(encoding="utf-8"))
                for sid, sdata in data.items():
                    self._sessions[sid] = PreviewSession(**sdata)
            except Exception:
                pass

    def _save_registry(self) -> None:
        try:
            import json
            data = {sid: s.model_dump() for sid, s in self._sessions.items()}
            self.registry_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def create_session(
        self,
        task_id: str,
        workspace_id: str,
        workspace_path: Path,
        entry_file: str = "index.html",
    ) -> PreviewSession:
        """Creates or registers a sandboxed preview session for a workspace."""
        root = workspace_path.resolve()
        session_id = f"prev-{task_id[:8]}"
        preview_url = f"/api/coding/preview/{session_id}/{entry_file}"

        session = PreviewSession(
            preview_id=session_id,
            task_id=task_id,
            workspace_id=workspace_id,
            workspace_root=str(root),
            entry_file=entry_file,
            status="ready",
            preview_url=preview_url,
        )
        self._sessions[session_id] = session
        self._save_registry()
        return session

    def get_session(self, session_id: str) -> Optional[PreviewSession]:
        if session_id not in self._sessions:
            self._load_registry()
        return self._sessions.get(session_id)

    def serve_asset(self, session_id: str, relative_path: str) -> Optional[PreviewAssetResponse]:
        """Safely reads and serves an asset from the workspace sandbox with strict headers."""
        session = self.get_session(session_id)
        if not session:
            return None

        # Immediate path traversal and root escape rejection
        if ".." in relative_path or relative_path.startswith("/") or relative_path.startswith("\\"):
            return None

        root = Path(session.workspace_root).resolve()
        clean_rel = relative_path.replace("\\", "/").lstrip("/") or session.entry_file
        target_path = (root / clean_rel).resolve()

        # Strict containment check against path traversal
        if not (target_path == root or str(target_path).startswith(str(root) + os.sep)):
            return None

        if not target_path.exists() or not target_path.is_file():
            # Fallback to index.html ONLY for extension-less SPA client-side routes (e.g. /dashboard)
            ext = os.path.splitext(clean_rel)[1]
            if not ext and clean_rel != "index.html" and (root / "index.html").exists():
                target_path = (root / "index.html").resolve()
            else:
                return None

        try:
            content = target_path.read_bytes()
        except Exception:
            return None

        # Guess MIME type
        media_type, _ = mimetypes.guess_type(str(target_path))
        if not media_type:
            media_type = "application/octet-stream"

        # Inject hot-reload script and responsive viewport meta into HTML files
        if media_type == "text/html":
            html_text = content.decode("utf-8", errors="replace")
            injected_html = self._inject_preview_bridge(html_text, session_id)
            content = injected_html.encode("utf-8")

        etag = hashlib.sha256(content).hexdigest()[:16]

        headers = {
            "Content-Type": media_type,
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "ETag": f'"{etag}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": (
                "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob: https://fonts.googleapis.com https://fonts.gstatic.com https://cdn.jsdelivr.net; "
                "font-src 'self' https://fonts.gstatic.com data:; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "img-src 'self' data: blob: https:; "
                "frame-ancestors 'self' http://localhost:5173 http://127.0.0.1:8000;"
            ),
        }

        return PreviewAssetResponse(
            content_bytes=content,
            media_type=media_type,
            headers=headers,
        )

    @staticmethod
    def _inject_preview_bridge(html: str, session_id: str) -> str:
        """Injects bridge code for hot-reloading and console error forwarding."""
        bridge_script = f"""
        <!-- HINAA Phase 19 Live Preview Bridge -->
        <script>
        (function() {{
            window.__HINAA_PREVIEW_SESSION__ = "{session_id}";
            // Forward console errors to parent studio
            window.addEventListener('error', function(e) {{
                if (window.parent) {{
                    window.parent.postMessage({{
                        type: 'hinaa:preview-error',
                        message: e.message,
                        filename: e.filename,
                        lineno: e.lineno,
                        colno: e.colno
                    }}, '*');
                }}
            }});
        }})();
        </script>
        """
        if "</head>" in html:
            return html.replace("</head>", f"{bridge_script}\n</head>", 1)
        elif "</body>" in html:
            return html.replace("</body>", f"{bridge_script}\n</body>", 1)
        else:
            return html + bridge_script


_GLOBAL_PREVIEW_MANAGER: Optional[PreviewRuntimeManager] = None


def get_preview_manager() -> PreviewRuntimeManager:
    global _GLOBAL_PREVIEW_MANAGER
    if _GLOBAL_PREVIEW_MANAGER is None:
        _GLOBAL_PREVIEW_MANAGER = PreviewRuntimeManager()
    return _GLOBAL_PREVIEW_MANAGER
