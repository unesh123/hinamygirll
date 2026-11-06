# HINAA OS Phase 20: Preview Security, Sandbox Architecture & Threat Model

## Threat Model Overview
When an autonomous AI agent synthesizes and renders arbitrary HTML, CSS, and JavaScript in real-time, the system must guarantee that:
1. Untrusted synthesized code cannot escape its sandbox to read user cookies, auth tokens, or parent window DOM.
2. Code running in an iframe cannot access host filesystem paths outside its designated workspace directory.
3. Network calls within previewed apps cannot bypass CORS or execute unauthorized background exfiltration.
4. Secrets, API keys (`OPENAI_API_KEY`, `ELEVENLABS_API_KEY`, `XKIRO_API_KEY`), and database credentials are never reflected into preview assets.

---

## Multi-Layer Isolation Defense

### 1. Iframe Sandbox Isolation
Every sandboxed preview rendered by Developer Studio uses the following attributes:
```html
<iframe
  src="/api/coding/preview/{session_id}/index.html"
  sandbox="allow-scripts allow-forms"
></iframe>
```
> [!IMPORTANT]
> The sandbox attribute strictly **omits** `allow-same-origin` and `allow-top-navigation`.
> Without `allow-same-origin`, the preview iframe executes in an opaque unique origin (`null`), rendering it completely impossible for synthesized code to access the parent application's `window.localStorage`, `sessionStorage`, `document.cookie`, or DOM tree.

### 2. HTTP Defense-in-Depth Headers
Every static and dynamic asset served by `PreviewRuntimeManager.serve_asset` carries strict HTTP containment headers:
```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Content-Security-Policy: default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob: https://fonts.googleapis.com https://fonts.gstatic.com https://cdn.jsdelivr.net; font-src 'self' https://fonts.gstatic.com data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; frame-ancestors 'self';
X-Content-Type-Options: nosniff
Cache-Control: no-cache, no-store, must-revalidate
```
- `frame-ancestors 'self'`: Prevents clickjacking and prevents untrusted third-party sites from framing HINAA preview sessions.
- `X-Content-Type-Options: nosniff`: Prevents MIME-type sniffing attacks.

### 3. File System Jail & Canonical Path Validation
All workspace file queries (`PreviewRuntimeManager.serve_asset` and `AutonomousProjectEngine._resolve_safe_path`) enforce strict path jail confinement:
```python
def _resolve_safe_path(self, workspace_path: Path, relative_path: str) -> Path:
    rel = relative_path.replace("\\", "/").lstrip("/")
    dest = (workspace_path / rel).resolve()
    if not str(dest).startswith(str(workspace_path.resolve())):
        raise PermissionError(f"Path traversal detected outside workspace: {relative_path}")
    return dest
```
Any attempt to pass `../`, `..\\`, or symlink escape sequences is immediately rejected with `PermissionError` (HTTP 403 / 404).

### 4. Secret Redaction Pipeline
The `DeveloperEventStore._redact_secrets` pipeline intercepts every WAL event, command stdout/stderr, and synthesized file before writing to disk or emitting across SSE:
- Matches key patterns: `sk-[a-zA-Z0-9_-]{20,}`, `bearer\s+[a-zA-Z0-9_\-\.]+`, `xkiro_[a-zA-Z0-9]{16,}`.
- Replaces matches with `[REDACTED_SECRET]`.
- Enforces zero secret leakage across tests `P20-030` and `P20-081..P20-088`.
