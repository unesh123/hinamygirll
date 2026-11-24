"""Interactive Action Approvals Gate for Dangerous Operations (Directive v3.0).

Enforces human-in-the-loop authorization for dangerous agent actions:
- Strict Risk classification:
  * SAFE: Read-only operations inside workspace (Tier 0)
  * CONFIRM: State mutations inside workspace and network navigation (Tier 1 & 2)
  * DANGEROUS: Terminal execution, process launch, OS input, and destructive operations (Tier 3 & 4)
  * DENY: Unregistered or unmapped tools (Default-Deny)
- Execution pause awaiting user resolution
- 300-second (5 min) countdown with fail-safe auto-deny on timeout
- Trusted session support: auto-approves CONFIRM only; DANGEROUS always asks
- Untrusted content warning: red alert if web/external content was seen in the run
- Parameter binding, canonical digest, HMAC-SHA256 signature, plain-language explanations, and audit logging
- Tamper-evident, restart-persistent SQLite WAL storage placed in OS Application Data (outside git repo)
- Tenant-isolated verification and atomic anti-replay consumption
- Strict redaction of secrets, passwords, and tokens before persistence or serialization
- Durable signing key persistence across process restarts
"""
from __future__ import annotations

import asyncio
import enum
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger("hinaa.security.action_approvals")

DEFAULT_POLICY_VERSION = "v3.0"
DEFAULT_KEY_ID = "k1"

# Authoritative centralized risk tier classification (Tiers 0..4)
TOOL_RISK_TIERS: dict[str, int] = {
    # Tier 0 (Read-only inspection)
    "artifact_lookup": 0,
    "user_preference_get": 0,
    "user_preferences_list": 0,
    "read_outlook": 0,
    "github_list_repos": 0,
    "github_repo_overview": 0,
    "github_read_file": 0,
    "github_list_commits": 0,
    "github_list_issues": 0,
    "list_content_week": 0,
    "sales_summary": 0,
    "list_projects": 0,
    "news_digest_now": 0,
    "news_latest": 0,
    "prodcamp_list_features": 0,
    "system_info": 0,
    "memory_consolidate_cycle": 0,
    "file_list": 0,
    "ultra_memory_get": 0,

    # Tier 1 (Reversible local workspace modification)
    "workspace": 1,
    "money_guard": 1,
    "file_read": 1,
    "clipboard_get": 1,
    "reminder.create": 1,
    "plan_content_post": 1,
    "update_content_post": 1,
    "upsert_project": 1,
    "log_sale": 1,
    "news_watch_create": 1,
    "document_generate": 1,
    "pdf_generate": 1,
    "design_website": 1,
    "html_anime_generate": 1,
    "create_lyric_video": 1,
    "create_motion_video": 1,
    "image_generate": 1,
    "magnific_image_generate": 1,
    "freepik_image_generate": 1,
    "magnific_upscale": 1,
    "freepik_stock_search": 1,
    "video_generate": 1,
    "image_upscale": 1,
    "image_relight": 1,
    "auto_goal_decomposer": 1,
    "self_improver": 1,
    "server_start": 1,
    "ffmpeg_export": 1,
    "ultra_file_write": 1,
    "record_frames": 1,
    "video_create": 1,
    "browser_screenshot": 1,
    "ultra_memory_save": 1,

    # Tier 2 (Network & external communication)
    "web_search": 2,
    "image_search": 2,
    "web_answer": 2,
    "web_research": 2,
    "web_research_status": 2,
    "web_extract": 2,
    "finance_research": 2,
    "tinyfish_search": 2,
    "tinyfish_fetch": 2,
    "tinyfish_agent": 2,
    "exa_search": 2,
    "exa_get_contents": 2,
    "exa_agent_run": 2,
    "browser_navigate": 2,
    "browser_extract": 2,
    "browser_scroll": 2,
    "browser_navigation_request": 2,
    "youtube_playback_request": 2,
    "browser_execute_task": 2,
    "browser_cloud_agent": 2,
    "customgpt_query": 2,
    "agent_reach": 2,
    "ugc_trend_extractor": 2,
    "parallel_executor": 2,
    "deep_research": 2,
    "create_gamma_presentation": 2,
    "gamma_create": 2,
    "bivia_decide": 2,
    "treg_call": 2,
    "agent_spawn": 2,

    # Tier 3 (Process execution, shell commands, OS input)
    "shell_run": 3,
    "file_write": 3,
    "edit_file": 3,
    "write_file": 3,
    "terminal_hands": 3,
    "terminal_execute": 3,
    "shell_execute": 3,
    "bash": 3,
    "powershell": 3,
    "app_launch": 3,
    "clipboard_set": 3,
    "screenshot": 3,
    "browser_click": 3,
    "browser_type": 3,
    "browser_press_key": 3,
    "build_with_ide": 3,
    "coding_agent": 3,
    "subagent_fork": 3,
    "swarm_orchestrate": 3,
    "pty_session_run": 3,
    "pty_session_interact": 3,
    "vision_canvas_inspect": 3,
    "vision_canvas_interact": 3,
    "vision_pty_cross_interact": 3,
    "mobile_run_task": 3,
    "mobile_diagnose": 3,
    "mobile_get_device_state": 3,
    "clean_room_loop": 3,
    "git_checkout": 3,
    "git_branch": 3,
    "ui_control": 3,

    # Tier 4 (Destructive mutation, privileged operations, external publishing, financial)
    "delete_file": 4,
    "delete_content_post": 4,
    "delete_project": 4,
    "send_email": 4,
    "social_publish": 4,
    "phone_call_user": 4,
    "whatsapp_send": 4,
    "whatsapp_status": 4,
    "github_write_file": 4,
    "github_create_branch": 4,
    "github_create_pull_request": 4,
    "github_create_issue": 4,
    "github_mcp": 4,
    "prodcamp_create_feature": 4,
    "prodcamp_submit_feedback": 4,
    "user_preference_update": 4,
    "git_commit": 4,
    "git_push": 4,
    "desktop_action": 4,
    "computer_operator": 3,  # Base fallback; dynamic sub-action classification refines to 0..4
}


def redact_sensitive_data(obj: Any) -> Any:
    """Recursively redact passwords, tokens, API keys, cookies, and secrets."""
    if isinstance(obj, dict):
        redacted = {}
        for k, v in obj.items():
            if re.search(
                r"(?i)\b(api[_-]?key|token|access[_-]?token|secret|password|auth|authorization|cookie|private[_-]?key|credential)\b",
                str(k),
            ):
                redacted[k] = "[REDACTED]"
            else:
                redacted[k] = redact_sensitive_data(v)
        return redacted
    elif isinstance(obj, list):
        return [redact_sensitive_data(item) for item in obj]
    elif isinstance(obj, str):
        v = re.sub(r"(?i)\bauthorization\s*[:=]\s*bearer\s+[^\s,;'\"]+", "Authorization: Bearer [REDACTED]", obj)
        v = re.sub(r"(?i)\bbearer\s+[^\s,;'\"]+", "Bearer [REDACTED]", v)
        v = re.sub(
            r"(?i)\b(api[_-]?key|access[_-]?token|secret|password)\s*[:=]\s*[^\s,;'\"]+",
            r"\1=[REDACTED]",
            v,
        )
        return v
    return obj


def get_default_approvals_db_path() -> Path:
    """Resolve OS-appropriate application data directory outside the git repository."""
    override = os.environ.get("HINA_APPROVALS_DB_PATH") or os.environ.get("HINAA_APPROVALS_DB")
    if override:
        return Path(override)
    data_dir = os.environ.get("HINA_DATA_DIR")
    if not data_dir:
        if os.name == "nt":
            data_dir = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
        else:
            data_dir = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return Path(data_dir) / "hina" / "approvals.db"


def get_default_approvals_key_path() -> Path:
    """Resolve OS-appropriate path for persistent development signing key."""
    override = os.environ.get("HINA_APPROVALS_KEY_PATH")
    if override:
        return Path(override)
    return get_default_approvals_db_path().parent / "approvals.key"


def get_approvals_signing_key(key_path: Optional[Path] = None) -> bytes:
    """Obtain or initialize durable signing key for HMAC tamper defense.

    - In production (HINAA_ENV=production or ENVIRONMENT=production): fails closed
      if HINA_APPROVALS_SECRET_KEY is not set.
    - In development: securely persists key to approvals.key with restricted permissions (0o600)
      so that independent subprocesses and process restarts reuse the exact same key.
    """
    env_key = os.environ.get("HINA_APPROVALS_SECRET_KEY")
    if env_key:
        return env_key.encode("utf-8")

    is_prod = (
        os.environ.get("HINAA_ENV", "").lower() == "production"
        or os.environ.get("ENVIRONMENT", "").lower() == "production"
    )
    if is_prod:
        raise RuntimeError("HINA_APPROVALS_SECRET_KEY environment variable is required in production.")

    kp = key_path or get_default_approvals_key_path()
    try:
        if kp.exists():
            key_bytes = kp.read_bytes().strip()
            if len(key_bytes) >= 32:
                return key_bytes

        kp.parent.mkdir(parents=True, exist_ok=True)
        new_key = secrets.token_bytes(32)
        kp.write_bytes(new_key)
        if os.name != "nt":
            try:
                os.chmod(kp, 0o600)
            except OSError:
                pass
        return new_key
    except Exception as exc:
        logger.critical("Failed to initialize persistent approvals signing key at %s: %s", kp, exc)
        raise RuntimeError(f"Cannot initialize persistent approvals signing key: {exc}") from exc


def compute_parameters_digest(parameters: dict[str, Any]) -> str:
    """Compute canonical, tamper-evident SHA256 digest of parameters."""
    canonical = json.dumps(parameters or {}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_approval_signature(
    signing_key: bytes,
    challenge_id: str,
    tenant_id: str,
    actor_id: str,
    device_id: str,
    tool_name: str,
    parameters_digest: str,
    risk_tier: int,
    nonce: str,
    issued_at: float,
    expires_at: float,
    policy_version: str = DEFAULT_POLICY_VERSION,
    key_id: str = DEFAULT_KEY_ID,
) -> str:
    """Compute authenticated HMAC-SHA256 signature binding all mandatory context elements."""
    raw = (
        f"{challenge_id}:{tenant_id}:{actor_id}:{device_id}:{tool_name}:"
        f"{parameters_digest}:{risk_tier}:{nonce}:{round(issued_at, 2)}:"
        f"{round(expires_at, 2)}:{policy_version}:{key_id}"
    )
    return hmac.new(signing_key, raw.encode("utf-8"), hashlib.sha256).hexdigest()


class ToolRiskLevel(str, enum.Enum):
    SAFE = "safe"
    CONFIRM = "confirm"
    DANGEROUS = "dangerous"
    DENY = "deny"

    # Backward compatibility aliases
    LOW = "safe"
    MEDIUM = "confirm"
    HIGH = "confirm"
    CRITICAL = "dangerous"


@dataclass
class PendingApprovalChallenge:
    challenge_id: str
    tool_name: str
    parameters: dict[str, Any]
    risk_level: ToolRiskLevel
    description: str
    created_at: float
    expires_at: float
    tenant_id: str
    actor_id: str
    device_id: str
    countdown_seconds: float = 300.0
    untrusted_content_warning: bool = False
    resolved: bool = False
    approved: bool = False
    resolution_reason: str = ""
    parameters_digest: str = ""
    signature: str = ""
    nonce: str = ""
    risk_tier: int = 3
    policy_version: str = DEFAULT_POLICY_VERSION
    key_id: str = DEFAULT_KEY_ID
    status: str = "PENDING"
    _future: asyncio.Future[bool] | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict with sensitive parameters strictly redacted."""
        risk_str = self.risk_level.value if hasattr(self.risk_level, "value") else str(self.risk_level)
        return {
            "challenge_id": self.challenge_id,
            "tool_name": self.tool_name,
            "parameters": redact_sensitive_data(self.parameters),
            "risk_level": risk_str.upper(),
            "description": self.description,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "countdown_seconds": self.countdown_seconds,
            "untrusted_content_warning": self.untrusted_content_warning,
            "resolved": self.resolved,
            "approved": self.approved,
            "resolution_reason": self.resolution_reason,
            "parameters_digest": self.parameters_digest,
            "signature": self.signature,
            "nonce": self.nonce,
            "tenant_id": self.tenant_id,
            "actor_id": self.actor_id,
            "device_id": self.device_id,
            "risk_tier": self.risk_tier,
            "policy_version": self.policy_version,
            "key_id": self.key_id,
            "status": self.status,
        }


def explain_tool_action(tool_name: str, parameters: dict[str, Any]) -> str:
    """Generate clear, plain-language description of what this tool call will do."""
    redacted = redact_sensitive_data(parameters)
    name = tool_name.lower()
    if name in ("terminal_execute", "shell_execute"):
        cmd = str(redacted.get("command", "")).strip()
        runtime = str(redacted.get("runtime", "windows"))
        return f"Run command in {runtime} shell: `{cmd}`"
    if name == "edit_file":
        fp = str(redacted.get("file_path") or redacted.get("path") or "")
        return f"Edit lines in file: `{fp}`"
    if name == "write_file":
        fp = str(redacted.get("file_path") or redacted.get("path") or "")
        return f"Overwrite or create file: `{fp}`"
    if name in ("desktop_action", "computer_operator"):
        act = str(redacted.get("action", ""))
        target = str(redacted.get("target") or redacted.get("content") or "")
        return f"Perform desktop GUI action '{act}' on target `{target}`"
    return f"Execute tool `{tool_name}` with parameters: {redacted}"


class ActionApprovalGate:
    """Coordinates runtime approval challenges for dangerous tools with durable SQLite backing."""

    def __init__(
        self,
        default_mode: str = "auto_approve_safe",
        default_timeout: float = 300.0,
        db_path: Optional[Path] = None,
        signing_key: Optional[bytes] = None,
        key_id: str = DEFAULT_KEY_ID,
    ) -> None:
        self.mode = default_mode
        self.default_timeout = default_timeout
        self.db_path = Path(db_path) if db_path else get_default_approvals_db_path()
        self.signing_key = signing_key or get_approvals_signing_key()
        self.key_id = key_id
        self._pending: dict[str, PendingApprovalChallenge] = {}
        self._history: list[dict[str, Any]] = []
        self._db_ready = False
        self._init_sqlite()
        if self._db_ready:
            self._recover_pending()

    def _get_db_conn(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            try:
                os.chmod(self.db_path.parent, 0o700)
            except OSError:
                pass
        conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.row_factory = sqlite3.Row
        if os.name != "nt":
            try:
                os.chmod(self.db_path, 0o600)
            except OSError:
                pass
        return conn

    def _init_sqlite(self) -> None:
        try:
            with self._get_db_conn() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS durable_approvals (
                        challenge_id TEXT PRIMARY KEY,
                        tenant_id TEXT NOT NULL,
                        actor_id TEXT NOT NULL,
                        device_id TEXT NOT NULL,
                        tool_name TEXT NOT NULL,
                        parameters_json TEXT NOT NULL,
                        parameters_digest TEXT NOT NULL,
                        signature TEXT NOT NULL,
                        nonce TEXT UNIQUE NOT NULL,
                        risk_level TEXT NOT NULL,
                        risk_tier INTEGER NOT NULL,
                        policy_version TEXT NOT NULL,
                        key_id TEXT NOT NULL DEFAULT 'k1',
                        description TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        expires_at REAL NOT NULL,
                        countdown_seconds REAL NOT NULL,
                        untrusted_content_warning INTEGER NOT NULL,
                        resolved INTEGER NOT NULL,
                        approved INTEGER NOT NULL,
                        resolution_reason TEXT NOT NULL,
                        status TEXT NOT NULL,
                        resolved_at REAL,
                        consumed_at REAL
                    );
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_durable_approvals_tenant ON durable_approvals(tenant_id, status);"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_durable_approvals_nonce ON durable_approvals(nonce);"
                )
                conn.commit()
            self._db_ready = True
        except Exception as exc:
            logger.critical("SECURITY_FAIL_CLOSED: Failed to initialize durable approvals SQLite: %s", exc)
            self._db_ready = False

    def _recover_pending(self) -> None:
        """Recover active pending challenges across server restarts."""
        now = time.time()
        try:
            with self._get_db_conn() as conn:
                cur = conn.execute("SELECT * FROM durable_approvals WHERE status = 'PENDING';")
                rows = cur.fetchall()
                for row in rows:
                    cid = row["challenge_id"]
                    exp = float(row["expires_at"])
                    if exp <= now:
                        conn.execute(
                            "UPDATE durable_approvals SET status = 'EXPIRED', resolution_reason = 'Expired during offline period' WHERE challenge_id = ?;",
                            (cid,),
                        )
                        continue
                    try:
                        params = json.loads(row["parameters_json"])
                    except Exception:
                        params = {}
                    risk_lvl = ToolRiskLevel.DANGEROUS
                    try:
                        risk_lvl = ToolRiskLevel(row["risk_level"].lower())
                    except Exception:
                        pass

                    key_id_val = row["key_id"] if "key_id" in row.keys() else DEFAULT_KEY_ID

                    recovered = PendingApprovalChallenge(
                        challenge_id=cid,
                        tool_name=row["tool_name"],
                        parameters=params,
                        risk_level=risk_lvl,
                        description=row["description"],
                        created_at=float(row["created_at"]),
                        expires_at=exp,
                        tenant_id=row["tenant_id"],
                        actor_id=row["actor_id"],
                        device_id=row["device_id"],
                        countdown_seconds=float(row["countdown_seconds"]),
                        untrusted_content_warning=bool(row["untrusted_content_warning"]),
                        resolved=False,
                        approved=False,
                        resolution_reason="",
                        parameters_digest=row["parameters_digest"],
                        signature=row["signature"],
                        nonce=row["nonce"],
                        risk_tier=int(row["risk_tier"]),
                        policy_version=row["policy_version"],
                        key_id=key_id_val,
                        status="PENDING",
                    )
                    self._pending[cid] = recovered
                conn.commit()
            if self._pending:
                logger.info("Recovered %d pending approval challenges from durable SQLite.", len(self._pending))
        except Exception as exc:
            logger.error("Failed to recover pending challenges from SQLite: %s", exc)

    def get_tool_risk_tier(self, tool_name: str, parameters: dict[str, Any] | None = None) -> int | None:
        """Derive authoritative risk tier strictly from central policy/registry."""
        name = str(tool_name or "").lower().strip()
        params = parameters or {}
        if name == "computer_operator":
            from ..tools.policy import classify_computer_operator_action
            act = str(params.get("action", "")).strip().lower()
            tier = classify_computer_operator_action(act, params)
            return int(tier.value)

        if name in TOOL_RISK_TIERS:
            return TOOL_RISK_TIERS[name]

        from ..tools import registry
        tdef = registry.get_tool(name)
        if tdef is not None:
            return int(tdef.risk_tier)

        return None

    def classify_risk(
        self,
        tool_name: str,
        parameters: dict[str, Any] | None = None,
        is_trusted_session: bool = False,
    ) -> ToolRiskLevel:
        """Classify operation risk tier with default-deny for unknown/unregistered tools."""
        params = parameters or {}
        tier = self.get_tool_risk_tier(tool_name, params)
        if tier is None:
            logger.warning("[SECURITY] Tool '%s' is unregistered and unmapped: DEFAULT DENY.", tool_name)
            return ToolRiskLevel.DENY

        if tier >= 3:
            return ToolRiskLevel.DANGEROUS
        elif tier in (1, 2):
            return ToolRiskLevel.CONFIRM
        elif tier == 0:
            return ToolRiskLevel.SAFE

        return ToolRiskLevel.DENY

    async def request_approval(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        *,
        tenant_id: str,
        actor_id: str,
        device_id: str,
        untrusted_content_seen: bool = False,
        is_trusted_session: bool = False,
        on_challenge_created: Optional[Callable[[dict[str, Any]], Awaitable[None]]] = None,
        description: str = "",
        timeout_seconds: Optional[float] = None,
        risk_tier: Optional[int] = None,
    ) -> tuple[bool, str, str]:
        """Request human approval before executing a dangerous tool.

        - Enforces non-empty tenant, actor, and device context bindings.
        - Derives risk tier strictly from trusted central registry/policy.
        - Fails closed immediately if database is unavailable.
        - Default-denies unknown tools.
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id must be an explicit, non-empty authenticated tenant ID")
        if not actor_id or not actor_id.strip():
            raise ValueError("actor_id must be an explicit, non-empty authenticated actor ID")
        if not device_id or not device_id.strip():
            raise ValueError("device_id must be an explicit, non-empty authenticated device ID")

        # Derive authoritative risk tier
        derived_tier = self.get_tool_risk_tier(tool_name, parameters)
        if derived_tier is None:
            logger.warning("[SECURITY] request_approval denied: '%s' is unmapped (default deny).", tool_name)
            return False, f"DENIED: Tool '{tool_name}' is unregistered or prohibited by policy", ""

        effective_risk_tier = derived_tier
        risk = self.classify_risk(tool_name, parameters, is_trusted_session)
        if risk == ToolRiskLevel.DENY:
            return False, f"DENIED: Tool '{tool_name}' is denied by security policy", ""

        # Trusted sessions auto-approve CONFIRM only; DANGEROUS ALWAYS pauses
        if is_trusted_session and risk == ToolRiskLevel.CONFIRM:
            return True, "Auto-approved for trusted session", ""

        if risk == ToolRiskLevel.SAFE:
            return True, "Safe operation auto-approved", ""

        if not self._db_ready:
            logger.critical("SECURITY_FAIL_CLOSED: Approvals database not ready. Halting action.")
            return False, "SECURITY_FAIL_CLOSED: Approvals database unavailable", ""

        effective_timeout = timeout_seconds if timeout_seconds is not None else self.default_timeout
        challenge_id = f"appr_{secrets.token_hex(12)}"
        nonce = secrets.token_hex(16)
        desc = description or explain_tool_action(tool_name, parameters)
        now = time.time()
        expires = now + effective_timeout
        param_digest = compute_parameters_digest(parameters)
        sig = compute_approval_signature(
            signing_key=self.signing_key,
            challenge_id=challenge_id,
            tenant_id=tenant_id,
            actor_id=actor_id,
            device_id=device_id,
            tool_name=tool_name,
            parameters_digest=param_digest,
            risk_tier=effective_risk_tier,
            nonce=nonce,
            issued_at=now,
            expires_at=expires,
            policy_version=DEFAULT_POLICY_VERSION,
            key_id=self.key_id,
        )

        loop = asyncio.get_running_loop()
        fut: asyncio.Future[bool] = loop.create_future()

        challenge = PendingApprovalChallenge(
            challenge_id=challenge_id,
            tool_name=tool_name,
            parameters=parameters,
            risk_level=risk,
            description=desc,
            created_at=now,
            expires_at=expires,
            tenant_id=tenant_id,
            actor_id=actor_id,
            device_id=device_id,
            countdown_seconds=self.default_timeout,
            untrusted_content_warning=untrusted_content_seen,
            parameters_digest=param_digest,
            signature=sig,
            nonce=nonce,
            risk_tier=effective_risk_tier,
            policy_version=DEFAULT_POLICY_VERSION,
            key_id=self.key_id,
            status="PENDING",
            _future=fut,
        )

        self._pending[challenge_id] = challenge

        # Persist to SQLite with redacted parameters (no secrets saved to disk)
        try:
            with self._get_db_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO durable_approvals (
                        challenge_id, tenant_id, actor_id, device_id, tool_name,
                        parameters_json, parameters_digest, signature, nonce,
                        risk_level, risk_tier, policy_version, key_id, description,
                        created_at, expires_at, countdown_seconds,
                        untrusted_content_warning, resolved, approved,
                        resolution_reason, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        challenge.challenge_id,
                        challenge.tenant_id,
                        challenge.actor_id,
                        challenge.device_id,
                        challenge.tool_name,
                        json.dumps(redact_sensitive_data(challenge.parameters)),
                        challenge.parameters_digest,
                        challenge.signature,
                        challenge.nonce,
                        challenge.risk_level.value,
                        challenge.risk_tier,
                        challenge.policy_version,
                        challenge.key_id,
                        challenge.description,
                        challenge.created_at,
                        challenge.expires_at,
                        challenge.countdown_seconds,
                        1 if challenge.untrusted_content_warning else 0,
                        0,
                        0,
                        "",
                        "PENDING",
                    ),
                )
                conn.commit()
        except Exception as exc:
            logger.critical("SECURITY_FAIL_CLOSED: Failed to persist challenge to SQLite: %s", exc)
            self._pending.pop(challenge_id, None)
            return False, f"SECURITY_FAIL_CLOSED: Database persistence failed: {exc}", challenge_id

        if on_challenge_created:
            try:
                await on_challenge_created(challenge.to_dict())
            except Exception as e:
                logger.warning("Notification callback failed for challenge %s: %s", challenge_id, e)

        # Wait for user resolution or timeout
        try:
            approved = await asyncio.wait_for(fut, timeout=effective_timeout)
            return approved, challenge.resolution_reason, challenge_id
        except asyncio.TimeoutError:
            challenge.resolved = True
            challenge.approved = False
            challenge.status = "EXPIRED"
            challenge.resolution_reason = f"Challenge timed out after {effective_timeout:.1f}s"
            try:
                with self._get_db_conn() as conn:
                    conn.execute(
                        "UPDATE durable_approvals SET status = 'EXPIRED', resolution_reason = ? WHERE challenge_id = ? AND status = 'PENDING';",
                        (challenge.resolution_reason, challenge_id),
                    )
                    conn.commit()
            except Exception as exc:
                logger.warning("Failed to record timeout in SQLite: %s", exc)
            logger.warning("Approval challenge %s timed out. Auto-denied.", challenge_id)
            return False, challenge.resolution_reason, challenge_id
        finally:
            record = challenge.to_dict()
            self._history.append(record)
            self._pending.pop(challenge_id, None)

    def resolve_challenge(
        self,
        challenge_id: str,
        approved: bool,
        *,
        tenant_id: str,
        reason: str = "",
    ) -> bool:
        """Resolve a pending challenge from user UI input with strict tenant binding."""
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id must be an explicit, non-empty string for resolution")

        challenge = self._pending.get(challenge_id)
        if challenge and challenge.tenant_id != tenant_id:
            logger.warning("Cross-tenant resolve blocked: caller %s vs challenge %s", tenant_id, challenge.tenant_id)
            return False

        now = time.time()
        new_status = "APPROVED" if approved else "DENIED"
        res_reason = reason or ("Approved by operator" if approved else "Declined by operator")

        # Update SQLite
        try:
            with self._get_db_conn() as conn:
                cur = conn.execute(
                    "UPDATE durable_approvals SET status = ?, resolution_reason = ?, resolved_at = ? WHERE challenge_id = ? AND tenant_id = ? AND status = 'PENDING';",
                    (new_status, res_reason, now, challenge_id, tenant_id),
                )
                conn.commit()
                db_updated = cur.rowcount > 0
        except Exception as exc:
            logger.warning("Failed to update challenge %s in SQLite: %s", challenge_id, exc)
            db_updated = False

        if challenge:
            challenge.resolved = True
            challenge.approved = approved
            challenge.status = new_status
            challenge.resolution_reason = res_reason

            if challenge._future and not challenge._future.done():
                challenge._future.set_result(approved)

            logger.info("Approval challenge %s resolved: approved=%s (%s)", challenge_id, approved, challenge.resolution_reason)
            return True

        return db_updated

    def verify_and_consume(
        self,
        challenge_id: str,
        parameters: dict[str, Any],
        *,
        tenant_id: str,
    ) -> tuple[bool, str]:
        """Verify parameters against authorized challenge digest, check HMAC, and atomically consume."""
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id must be an explicit, non-empty string for verification")

        now = time.time()
        try:
            with self._get_db_conn() as conn:
                cur = conn.execute("SELECT * FROM durable_approvals WHERE challenge_id = ?;", (challenge_id,))
                row = cur.fetchone()
                if not row:
                    return False, f"Challenge '{challenge_id}' not found."

                # 1. Strict Tenant binding check
                if row["tenant_id"] != tenant_id:
                    return False, "CROSS_TENANT_REPLAY_BLOCKED"

                # 2. Anti-replay status check
                if row["status"] == "CONSUMED":
                    return False, "REPLAY_DETECTED: Challenge has already been consumed."
                if row["status"] != "APPROVED":
                    return False, f"Challenge is not approved (status: '{row['status']}')."
                if float(row["expires_at"]) < now:
                    return False, "Challenge has expired."

                # 3. Parameter hash integrity check (anti-tamper)
                expected_digest = row["parameters_digest"]
                actual_digest = compute_parameters_digest(parameters)
                if not secrets.compare_digest(expected_digest, actual_digest):
                    return False, "TAMPER_DETECTED: Parameters do not match authorized digest."

                # 4. Authenticated HMAC Signature check
                key_id_val = row["key_id"] if "key_id" in row.keys() else DEFAULT_KEY_ID
                expected_sig = compute_approval_signature(
                    signing_key=self.signing_key,
                    challenge_id=row["challenge_id"],
                    tenant_id=row["tenant_id"],
                    actor_id=row["actor_id"],
                    device_id=row["device_id"],
                    tool_name=row["tool_name"],
                    parameters_digest=expected_digest,
                    risk_tier=int(row["risk_tier"]),
                    nonce=row["nonce"],
                    issued_at=float(row["created_at"]),
                    expires_at=float(row["expires_at"]),
                    policy_version=row["policy_version"],
                    key_id=key_id_val,
                )
                if not hmac.compare_digest(expected_sig, row["signature"]):
                    return False, "SIGNATURE_INVALID: Approval challenge signature verification failed."

                # 5. Atomic consumption with optimistic locking
                cur = conn.execute(
                    "UPDATE durable_approvals SET status = 'CONSUMED', consumed_at = ? WHERE challenge_id = ? AND status = 'APPROVED';",
                    (now, challenge_id),
                )
                conn.commit()
                if cur.rowcount != 1:
                    return False, "CONCURRENT_CONSUMPTION_BLOCKED"

                return True, "Challenge successfully verified and consumed."
        except Exception as exc:
            logger.error("SECURITY_FAIL_CLOSED: Error in verify_and_consume: %s", exc)
            return False, f"SECURITY_FAIL_CLOSED: Database error verifying challenge: {exc}"

    def get_challenge(self, challenge_id: str, *, tenant_id: str) -> dict[str, Any] | None:
        """Fetch challenge record from memory or SQLite for the specified tenant."""
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for challenge lookup")

        if challenge_id in self._pending:
            c = self._pending[challenge_id]
            if c.tenant_id == tenant_id:
                return c.to_dict()
            return None
        try:
            with self._get_db_conn() as conn:
                cur = conn.execute(
                    "SELECT * FROM durable_approvals WHERE challenge_id = ? AND tenant_id = ?;",
                    (challenge_id, tenant_id),
                )
                row = cur.fetchone()
                if row:
                    d = dict(row)
                    try:
                        d["parameters"] = json.loads(d["parameters_json"])
                    except Exception:
                        d["parameters"] = {}
                    return d
        except Exception:
            pass
        return None

    def list_pending(self, *, tenant_id: str) -> list[dict[str, Any]]:
        """List currently pending challenges with remaining countdown seconds for the specified tenant."""
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for listing pending challenges")

        now = time.time()
        res: list[dict[str, Any]] = []
        for c in self._pending.values():
            if c.tenant_id != tenant_id:
                continue
            item = c.to_dict()
            item["remaining_seconds"] = max(0.0, round(c.expires_at - now, 1))
            res.append(item)
        return res

    def get_history(self, *, tenant_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """List resolved challenge history for the specified tenant."""
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for history retrieval")

        records = [r for r in self._history if r.get("tenant_id") == tenant_id]
        return records[-limit:]


def verify_startup_policy_coverage() -> None:
    """Verify that all registered tools have explicit policy and risk tier coverage.

    Aborts startup (raises RuntimeError) if any registered tool with risk_tier >= 2
    lacks policy coverage or if any tool is unregistered in policy.
    """
    from ..tools import registry
    registered_tools = registry.list_tools()
    missing_coverage = []

    for tool_name in registered_tools:
        name_lower = tool_name.lower().strip()
        tier = TOOL_RISK_TIERS.get(name_lower)
        tdef = registry.get_tool(tool_name)
        if tier is None and tdef is not None:
            tier = tdef.risk_tier

        if tier is None:
            missing_coverage.append(f"{tool_name} (unmapped tier)")
        elif tier >= 2:
            # Must be covered by TOOL_RISK_TIERS
            if name_lower not in TOOL_RISK_TIERS:
                missing_coverage.append(f"{tool_name} (Tier {tier} lacking policy coverage)")

    if missing_coverage:
        err_msg = f"Startup aborted: Policy coverage missing for registered tools: {', '.join(missing_coverage)}"
        logger.critical(err_msg)
        raise RuntimeError(err_msg)
    logger.info("Startup policy coverage verified for all %d registered tools.", len(registered_tools))


_gate_instance: ActionApprovalGate | None = None


def get_approval_gate(
    db_path: Optional[Path] = None,
    signing_key: Optional[bytes] = None,
) -> ActionApprovalGate:
    global _gate_instance
    if db_path is not None or signing_key is not None:
        return ActionApprovalGate(db_path=db_path, signing_key=signing_key)
    if _gate_instance is None:
        _gate_instance = ActionApprovalGate()
    return _gate_instance
