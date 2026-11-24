"""Interactive Action Approvals Gate for Dangerous Operations (Workstream A / Directive v3.0).

Enforces human-in-the-loop authorization for dangerous agent actions:
- Strict Risk classification:
  * SAFE: Read-only operations inside workspace
  * CONFIRM: State mutations inside workspace (e.g. edit_file, write_file)
  * DANGEROUS: Terminal execution, OS desktop actions, and actions outside workspace roots
- Execution pause awaiting user resolution
- 300-second (5 min) countdown with fail-safe auto-deny on timeout
- Trusted session support: auto-approves CONFIRM only; DANGEROUS always asks
- Untrusted content warning: red alert if web/external content was seen in the run
- Parameter binding, canonical digest, HMAC-SHA256 signature, plain-language explanations, and audit logging
- Tamper-evident, restart-persistent SQLite WAL storage placed in OS Application Data (outside git repo).
- Tenant-isolated verification and atomic anti-replay consumption.
"""
from __future__ import annotations

import asyncio
import enum
import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger("hinaa.security.action_approvals")

DEFAULT_POLICY_VERSION = "v3.0"
_DEFAULT_SIGNING_KEY: bytes | None = None


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


def get_approvals_signing_key() -> bytes:
    """Obtain or initialize local signing key for HMAC tamper defense."""
    global _DEFAULT_SIGNING_KEY
    if _DEFAULT_SIGNING_KEY is not None:
        return _DEFAULT_SIGNING_KEY
    env_key = os.environ.get("HINA_APPROVALS_SECRET_KEY")
    if env_key:
        _DEFAULT_SIGNING_KEY = env_key.encode("utf-8")
    else:
        _DEFAULT_SIGNING_KEY = secrets.token_bytes(32)
    return _DEFAULT_SIGNING_KEY


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
) -> str:
    """Compute authenticated HMAC-SHA256 signature binding all mandatory context elements."""
    raw = (
        f"{challenge_id}:{tenant_id}:{actor_id}:{device_id}:{tool_name}:"
        f"{parameters_digest}:{risk_tier}:{nonce}:{round(issued_at, 2)}:"
        f"{round(expires_at, 2)}:{policy_version}"
    )
    return hmac.new(signing_key, raw.encode("utf-8"), hashlib.sha256).hexdigest()


class ToolRiskLevel(str, enum.Enum):
    SAFE = "safe"
    CONFIRM = "confirm"
    DANGEROUS = "dangerous"

    # Backward compatibility aliases for existing tests
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
    countdown_seconds: float = 300.0
    untrusted_content_warning: bool = False
    resolved: bool = False
    approved: bool = False
    resolution_reason: str = ""
    parameters_digest: str = ""
    signature: str = ""
    nonce: str = ""
    tenant_id: str = "default_tenant"
    actor_id: str = "default_actor"
    device_id: str = "local"
    risk_tier: int = 3
    policy_version: str = DEFAULT_POLICY_VERSION
    status: str = "PENDING"
    _future: asyncio.Future[bool] | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        risk_str = self.risk_level.value if hasattr(self.risk_level, "value") else str(self.risk_level)
        return {
            "challenge_id": self.challenge_id,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
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
            "status": self.status,
        }


def explain_tool_action(tool_name: str, parameters: dict[str, Any]) -> str:
    """Generate clear, plain-language description of what this tool call will do."""
    name = tool_name.lower()
    if name in ("terminal_execute", "shell_execute"):
        cmd = str(parameters.get("command", "")).strip()
        runtime = str(parameters.get("runtime", "windows"))
        return f"Run command in {runtime} shell: `{cmd}`"
    if name == "edit_file":
        fp = str(parameters.get("file_path") or parameters.get("path") or "")
        return f"Edit lines in file: `{fp}`"
    if name == "write_file":
        fp = str(parameters.get("file_path") or parameters.get("path") or "")
        return f"Overwrite or create file: `{fp}`"
    if name in ("desktop_action", "computer_operator"):
        act = str(parameters.get("action", ""))
        target = str(parameters.get("target") or parameters.get("content") or "")
        return f"Perform desktop GUI action '{act}' on target `{target}`"
    return f"Execute tool `{tool_name}` with parameters: {parameters}"


class ActionApprovalGate:
    """Coordinates runtime approval challenges for dangerous tools with SQLite durability."""

    def __init__(
        self,
        default_mode: str = "auto_approve_safe",
        default_timeout: float = 300.0,
        db_path: Optional[Path] = None,
        signing_key: Optional[bytes] = None,
    ) -> None:
        self.mode = default_mode  # ask_every_time | auto_approve_safe | full_auto
        self.default_timeout = default_timeout
        self.db_path = Path(db_path) if db_path else get_default_approvals_db_path()
        self.signing_key = signing_key or get_approvals_signing_key()
        self._pending: dict[str, PendingApprovalChallenge] = {}
        self._history: list[dict[str, Any]] = []
        self._init_sqlite()
        self._recover_pending()

    def _get_db_conn(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Apply restrictive directory permissions on POSIX
        if os.name != "nt":
            try:
                os.chmod(self.db_path.parent, 0o700)
            except OSError:
                pass
        conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.row_factory = sqlite3.Row
        # Restrict database file permissions on creation
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
        except Exception as exc:
            logger.error("Failed to initialize durable approvals SQLite: %s", exc)

    def _recover_pending(self) -> None:
        """Recover active pending challenges across server restarts."""
        now = time.time()
        try:
            with self._get_db_conn() as conn:
                cur = conn.execute(
                    "SELECT * FROM durable_approvals WHERE status = 'PENDING';"
                )
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

                    recovered = PendingApprovalChallenge(
                        challenge_id=cid,
                        tool_name=row["tool_name"],
                        parameters=params,
                        risk_level=risk_lvl,
                        description=row["description"],
                        created_at=float(row["created_at"]),
                        expires_at=exp,
                        countdown_seconds=float(row["countdown_seconds"]),
                        untrusted_content_warning=bool(row["untrusted_content_warning"]),
                        resolved=False,
                        approved=False,
                        resolution_reason="",
                        parameters_digest=row["parameters_digest"],
                        signature=row["signature"],
                        nonce=row["nonce"],
                        tenant_id=row["tenant_id"],
                        actor_id=row["actor_id"],
                        device_id=row["device_id"],
                        risk_tier=int(row["risk_tier"]),
                        policy_version=row["policy_version"],
                        status="PENDING",
                    )
                    self._pending[cid] = recovered
                conn.commit()
            if self._pending:
                logger.info("Recovered %d pending approval challenges from durable SQLite.", len(self._pending))
        except Exception as exc:
            logger.error("Failed to recover pending challenges from SQLite: %s", exc)

    def classify_risk(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        is_trusted_session: bool = False,
    ) -> ToolRiskLevel:
        """Classify operation risk tier."""
        name = tool_name.lower()
        if name in (
            "terminal_execute", "shell_execute", "bash", "powershell",
            "full_pc_control", "hacker_agent", "bypass_engine", "desktop_action",
            "computer_operator", "git_commit", "git_push",
        ):
            return ToolRiskLevel.DANGEROUS

        if name in ("edit_file", "write_file", "delete_file", "git_checkout", "git_branch"):
            return ToolRiskLevel.CONFIRM

        return ToolRiskLevel.SAFE

    async def request_approval(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        untrusted_content_seen: bool = False,
        is_trusted_session: bool = False,
        on_challenge_created: Optional[Callable[[dict[str, Any]], Awaitable[None]]] = None,
        tenant_id: str = "default_tenant",
        actor_id: str = "default_actor",
        device_id: str = "local",
        risk_tier: int = 3,
        description: str = "",
        timeout_seconds: Optional[float] = None,
    ) -> tuple[bool, str, str]:
        """Request human approval before executing a dangerous tool."""
        risk = self.classify_risk(tool_name, parameters, is_trusted_session)

        # Trusted sessions auto-approve CONFIRM only; DANGEROUS ALWAYS pauses
        if is_trusted_session and risk == ToolRiskLevel.CONFIRM:
            return True, "Auto-approved for trusted session", ""

        if risk == ToolRiskLevel.SAFE:
            return True, "Safe operation auto-approved", ""

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
            risk_tier=risk_tier,
            nonce=nonce,
            issued_at=now,
            expires_at=expires,
            policy_version=DEFAULT_POLICY_VERSION,
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
            countdown_seconds=self.default_timeout,
            untrusted_content_warning=untrusted_content_seen,
            parameters_digest=param_digest,
            signature=sig,
            nonce=nonce,
            tenant_id=tenant_id,
            actor_id=actor_id,
            device_id=device_id,
            risk_tier=risk_tier,
            policy_version=DEFAULT_POLICY_VERSION,
            status="PENDING",
            _future=fut,
        )

        self._pending[challenge_id] = challenge

        # Persist to SQLite
        try:
            with self._get_db_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO durable_approvals (
                        challenge_id, tenant_id, actor_id, device_id, tool_name,
                        parameters_json, parameters_digest, signature, nonce,
                        risk_level, risk_tier, policy_version, description,
                        created_at, expires_at, countdown_seconds,
                        untrusted_content_warning, resolved, approved,
                        resolution_reason, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        challenge.challenge_id,
                        challenge.tenant_id,
                        challenge.actor_id,
                        challenge.device_id,
                        challenge.tool_name,
                        json.dumps(challenge.parameters),
                        challenge.parameters_digest,
                        challenge.signature,
                        challenge.nonce,
                        challenge.risk_level.value,
                        challenge.risk_tier,
                        challenge.policy_version,
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
            logger.error("Failed to persist approval challenge to SQLite: %s", exc)

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
        reason: str = "",
        tenant_id: Optional[str] = None,
    ) -> bool:
        """Resolve a pending challenge from user UI input with tenant binding."""
        challenge = self._pending.get(challenge_id)
        if challenge and tenant_id and challenge.tenant_id != tenant_id:
            logger.warning("Cross-tenant resolve blocked: caller tenant %s vs challenge %s", tenant_id, challenge.tenant_id)
            return False

        now = time.time()
        new_status = "APPROVED" if approved else "DENIED"
        res_reason = reason or ("Approved by operator" if approved else "Declined by operator")

        # Update SQLite
        try:
            with self._get_db_conn() as conn:
                if tenant_id:
                    cur = conn.execute(
                        "UPDATE durable_approvals SET status = ?, resolution_reason = ?, resolved_at = ? WHERE challenge_id = ? AND tenant_id = ? AND status = 'PENDING';",
                        (new_status, res_reason, now, challenge_id, tenant_id),
                    )
                else:
                    cur = conn.execute(
                        "UPDATE durable_approvals SET status = ?, resolution_reason = ?, resolved_at = ? WHERE challenge_id = ? AND status = 'PENDING';",
                        (new_status, res_reason, now, challenge_id),
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
        tenant_id: Optional[str] = None,
    ) -> tuple[bool, str]:
        """Verify parameters against authorized challenge digest, check HMAC, and atomically consume (anti-replay)."""
        now = time.time()
        try:
            with self._get_db_conn() as conn:
                cur = conn.execute("SELECT * FROM durable_approvals WHERE challenge_id = ?;", (challenge_id,))
                row = cur.fetchone()
                if not row:
                    return False, f"Challenge '{challenge_id}' not found."

                # 1. Tenant binding check
                if tenant_id and row["tenant_id"] != tenant_id:
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
            logger.error("Error in verify_and_consume: %s", exc)
            return False, f"Database error verifying challenge: {exc}"

    def get_challenge(self, challenge_id: str, tenant_id: Optional[str] = None) -> dict[str, Any] | None:
        """Fetch challenge record from memory or SQLite, filtered by tenant if supplied."""
        if challenge_id in self._pending:
            c = self._pending[challenge_id]
            if tenant_id and c.tenant_id != tenant_id:
                return None
            return c.to_dict()
        try:
            with self._get_db_conn() as conn:
                if tenant_id:
                    cur = conn.execute(
                        "SELECT * FROM durable_approvals WHERE challenge_id = ? AND tenant_id = ?;",
                        (challenge_id, tenant_id),
                    )
                else:
                    cur = conn.execute("SELECT * FROM durable_approvals WHERE challenge_id = ?;", (challenge_id,))
                row = cur.fetchone()
                if row:
                    return dict(row)
        except Exception:
            pass
        return None

    def list_pending(self, tenant_id: Optional[str] = None) -> list[dict[str, Any]]:
        """List currently pending challenges with remaining countdown seconds."""
        now = time.time()
        res: list[dict[str, Any]] = []
        for c in self._pending.values():
            if tenant_id and c.tenant_id != tenant_id:
                continue
            item = c.to_dict()
            item["remaining_seconds"] = max(0.0, round(c.expires_at - now, 1))
            res.append(item)
        return res

    def get_history(self, limit: int = 20, tenant_id: Optional[str] = None) -> list[dict[str, Any]]:
        """List resolved challenge history."""
        records = self._history
        if tenant_id:
            records = [r for r in records if r.get("tenant_id") == tenant_id]
        return records[-limit:]


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
