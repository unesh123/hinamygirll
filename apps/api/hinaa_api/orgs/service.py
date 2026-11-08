"""Persistence for organisations, memberships, API keys and the audit chain."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import Settings
from ..errors import HinaaError
from ..persistence.orm import User
from .models import IDENTITY_TABLES, Organisation, OrgApiKey, OrgAuditEntry, OrgMembership
from .permissions import ALL_PERMISSIONS, ROLES, permissions_for

SessionFactory = Callable[[], Session]


def factory_of(settings: Settings, memory: Any) -> SessionFactory:
    factory = getattr(memory, "_factory", None)
    if factory is None:
        from ..persistence.db import get_session_factory

        factory = get_session_factory(settings)
    return factory


GENESIS_HASH = "0" * 64
KEY_PREFIX = "hk_"
_lock = threading.RLock()
_schema_ready: set[int] = set()
_pepper_cache: dict[str, bytes] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ensure_schema(factory: SessionFactory) -> None:
    """Idempotent safety net for databases built with create_all instead of migrations."""
    with factory() as session:
        engine = session.get_bind()
        if id(engine) in _schema_ready:
            return
        existing = set(inspect(engine).get_table_names())
        for table in IDENTITY_TABLES:
            if table.name not in existing:
                table.create(engine, checkfirst=True)
        _schema_ready.add(id(engine))


# --- secrets -----------------------------------------------------------------

def pepper(settings: Settings | None = None) -> bytes:
    """Server-side secret mixed into key hashes and IP hashes."""
    configured = getattr(settings, "api_key_pepper", None) if settings else None
    if configured is not None and configured.get_secret_value().strip():
        return configured.get_secret_value().strip().encode()
    env = os.environ.get("HINAA_API_KEY_PEPPER", "").strip()
    if env:
        return env.encode()
    from ..runtime_paths import runtime_dir

    path: Path = runtime_dir("api_key_pepper")
    cache_key = str(path)
    if cache_key in _pepper_cache:
        return _pepper_cache[cache_key]
    with _lock:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as handle:
                handle.write(secrets.token_hex(32))
        value = path.read_text().strip().encode()
    _pepper_cache[cache_key] = value
    return value


def ip_hash(settings: Settings | None, ip: str | None) -> str:
    if not ip:
        return ""
    return hmac.new(pepper(settings), ip.encode(), hashlib.sha256).hexdigest()[:32]


# --- organisations -----------------------------------------------------------

def bootstrap_personal_org(
    factory: SessionFactory, user_id: str, settings: Settings | None = None, ctx: dict[str, Any] | None = None
) -> str:
    """Create the user's personal org on first sight; returns its id. Idempotent."""
    ensure_schema(factory)
    with _lock:
        with factory() as session:
            existing = session.scalar(
                select(Organisation.id)
                .join(OrgMembership, OrgMembership.org_id == Organisation.id)
                .where(
                    OrgMembership.user_id == user_id,
                    Organisation.is_personal.is_(True),
                    Organisation.created_by == user_id,
                )
                .order_by(Organisation.created_at)
            )
            if existing:
                return str(existing)
            org = Organisation(name="Personal", is_personal=True, created_by=user_id)
            session.add(org)
            session.flush()
            session.add(OrgMembership(org_id=org.id, user_id=user_id, role="owner"))
            session.commit()
            org_id = str(org.id)
    audit_record(factory, org_id, user_id, "org.create", f"org:{org_id}", "success", settings=settings, **(ctx or {}))
    audit_record(factory, org_id, user_id, "auth.login", f"user:{user_id}", "success", settings=settings, **(ctx or {}))
    return org_id


def memberships_of(factory: SessionFactory, user_id: str) -> list[dict[str, Any]]:
    with factory() as session:
        rows = session.execute(
            select(Organisation, OrgMembership.role)
            .join(OrgMembership, OrgMembership.org_id == Organisation.id)
            .where(OrgMembership.user_id == user_id)
            .order_by(Organisation.is_personal.desc(), Organisation.created_at)
        ).all()
        return [
            {"id": o.id, "name": o.name, "isPersonal": bool(o.is_personal), "role": role} for o, role in rows
        ]


def resolve_org_role(
    factory: SessionFactory, user_id: str, org_hint: str | None = None, settings: Settings | None = None,
    ctx: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """(org_id, role) for a user, bootstrapping the personal org. A hint must be a real membership."""
    personal = bootstrap_personal_org(factory, user_id, settings, ctx)
    with factory() as session:
        if org_hint:
            role = session.scalar(
                select(OrgMembership.role).where(OrgMembership.org_id == org_hint, OrgMembership.user_id == user_id)
            )
            if role is None:
                raise HinaaError("ORG_NOT_A_MEMBER", "You are not a member of that organisation.", 403)
            return org_hint, str(role)
        role = session.scalar(
            select(OrgMembership.role).where(OrgMembership.org_id == personal, OrgMembership.user_id == user_id)
        )
        return personal, str(role or "viewer")


def create_org(
    factory: SessionFactory, user_id: str, name: str, settings: Settings | None = None, ctx: dict[str, Any] | None = None
) -> dict[str, Any]:
    ensure_schema(factory)
    with factory() as session:
        org = Organisation(name=name.strip()[:200] or "Organisation", is_personal=False, created_by=user_id)
        session.add(org)
        session.flush()
        session.add(OrgMembership(org_id=org.id, user_id=user_id, role="owner"))
        session.commit()
        org_id = str(org.id)
        result = {"id": org_id, "name": org.name, "isPersonal": False, "role": "owner"}
    audit_record(factory, org_id, user_id, "org.create", f"org:{org_id}", "success", settings=settings, **(ctx or {}))
    return result


# --- members -----------------------------------------------------------------

def _member_dict(row: OrgMembership, subject: str | None) -> dict[str, Any]:
    return {
        "userId": row.user_id,
        "authSubject": subject,
        "role": row.role,
        "joinedAt": row.created_at.isoformat() if row.created_at else None,
    }


def list_members(factory: SessionFactory, org_id: str) -> list[dict[str, Any]]:
    with factory() as session:
        rows = session.execute(
            select(OrgMembership, User.auth_subject)
            .outerjoin(User, User.id == OrgMembership.user_id)
            .where(OrgMembership.org_id == org_id)
            .order_by(OrgMembership.created_at, OrgMembership.user_id)
        ).all()
        return [_member_dict(m, s) for m, s in rows]


def _check_role(role: str) -> None:
    if role not in ROLES:
        raise HinaaError("INVALID_ROLE", f"Role must be one of: {', '.join(ROLES)}.", 422)


def _owner_count(session: Session, org_id: str) -> int:
    return int(
        session.scalar(
            select(func.count()).select_from(OrgMembership).where(OrgMembership.org_id == org_id, OrgMembership.role == "owner")
        )
        or 0
    )


def _guard_owner_changes(actor_role: str, target_role: str | None, new_role: str | None) -> None:
    # Only owners may touch the owner tier, so an admin cannot escalate or evict.
    if actor_role != "owner" and ("owner" in (target_role, new_role)):
        raise HinaaError("OWNER_ONLY", "Only an owner can grant, change or remove the owner role.", 403)


def add_member(factory: SessionFactory, org_id: str, actor_role: str, user_id: str, role: str) -> dict[str, Any]:
    _check_role(role)
    _guard_owner_changes(actor_role, None, role)
    with factory() as session:
        user = session.get(User, user_id)
        if user is None:
            raise HinaaError("USER_NOT_FOUND", "No such user.", 404)
        row = OrgMembership(org_id=org_id, user_id=user_id, role=role)
        session.add(row)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise HinaaError("ALREADY_A_MEMBER", "That user is already a member.", 409) from None
        session.refresh(row)
        return _member_dict(row, user.auth_subject)


def set_member_role(factory: SessionFactory, org_id: str, actor_role: str, user_id: str, role: str) -> dict[str, Any]:
    _check_role(role)
    with _lock, factory() as session:
        row = session.scalar(select(OrgMembership).where(OrgMembership.org_id == org_id, OrgMembership.user_id == user_id))
        if row is None:
            raise HinaaError("MEMBER_NOT_FOUND", "No such member.", 404)
        _guard_owner_changes(actor_role, row.role, role)
        if row.role == "owner" and role != "owner" and _owner_count(session, org_id) <= 1:
            raise HinaaError("LAST_OWNER", "An organisation must keep at least one owner.", 409)
        row.role = role
        session.commit()
        user = session.get(User, user_id)
        return _member_dict(row, user.auth_subject if user else None)


def remove_member(factory: SessionFactory, org_id: str, actor_role: str, user_id: str) -> None:
    with _lock, factory() as session:
        row = session.scalar(select(OrgMembership).where(OrgMembership.org_id == org_id, OrgMembership.user_id == user_id))
        if row is None:
            raise HinaaError("MEMBER_NOT_FOUND", "No such member.", 404)
        _guard_owner_changes(actor_role, row.role, None)
        if row.role == "owner" and _owner_count(session, org_id) <= 1:
            raise HinaaError("LAST_OWNER", "An organisation must keep at least one owner.", 409)
        session.delete(row)
        session.commit()


# --- API keys ----------------------------------------------------------------

def _hash_key(settings: Settings | None, salt: str, secret: str) -> str:
    return hmac.new(pepper(settings), f"{salt}:{secret}".encode(), hashlib.sha256).hexdigest()


def _key_dict(row: OrgApiKey) -> dict[str, Any]:
    now = _now()
    return {
        "id": row.id,
        "name": row.name,
        "prefix": f"{KEY_PREFIX}{row.prefix}",
        "scopes": [s for s in row.scopes.split(",") if s],
        "createdBy": row.created_by,
        "createdAt": row.created_at.isoformat() + "Z" if row.created_at else None,
        "expiresAt": row.expires_at.isoformat() + "Z" if row.expires_at else None,
        "lastUsedAt": row.last_used_at.isoformat() + "Z" if row.last_used_at else None,
        "revokedAt": row.revoked_at.isoformat() + "Z" if row.revoked_at else None,
        "active": row.revoked_at is None and (row.expires_at is None or row.expires_at > now),
    }


def create_api_key(
    factory: SessionFactory,
    settings: Settings | None,
    org_id: str,
    created_by: str,
    grantable: frozenset[str],
    name: str,
    scopes: list[str],
    expires_in_days: int | None,
) -> dict[str, Any]:
    scope_set = set(scopes)
    unknown = scope_set - ALL_PERMISSIONS
    if not scope_set or unknown:
        raise HinaaError("INVALID_SCOPES", f"Scopes must be a non-empty subset of {sorted(ALL_PERMISSIONS)}.", 422)
    if not scope_set <= grantable:
        raise HinaaError("SCOPE_NOT_GRANTABLE", "A key cannot carry permissions you do not hold.", 403)
    prefix = secrets.token_hex(4)
    secret = secrets.token_urlsafe(32)
    salt = secrets.token_hex(16)
    expires = _now() + timedelta(days=expires_in_days) if expires_in_days else None
    with factory() as session:
        row = OrgApiKey(
            org_id=org_id,
            created_by=created_by,
            name=name.strip()[:120] or "API key",
            prefix=prefix,
            salt=salt,
            key_hash=_hash_key(settings, salt, secret),
            scopes=",".join(sorted(scope_set)),
            expires_at=expires,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return {**_key_dict(row), "key": f"{KEY_PREFIX}{prefix}_{secret}"}


def list_api_keys(factory: SessionFactory, org_id: str) -> list[dict[str, Any]]:
    with factory() as session:
        rows = session.scalars(select(OrgApiKey).where(OrgApiKey.org_id == org_id).order_by(OrgApiKey.created_at.desc())).all()
        return [_key_dict(r) for r in rows]


def revoke_api_key(factory: SessionFactory, org_id: str, key_id: str) -> dict[str, Any]:
    with factory() as session:
        row = session.scalar(select(OrgApiKey).where(OrgApiKey.id == key_id, OrgApiKey.org_id == org_id))
        if row is None:
            raise HinaaError("API_KEY_NOT_FOUND", "No such API key.", 404)
        if row.revoked_at is None:
            row.revoked_at = _now()
            session.commit()
        return _key_dict(row)


@dataclass(frozen=True, slots=True)
class KeyIdentity:
    key_id: str
    org_id: str
    user_id: str
    auth_subject: str
    role: str
    scopes: frozenset[str]


def authenticate_api_key(factory: SessionFactory, settings: Settings | None, token: str) -> KeyIdentity:
    invalid = HinaaError("AUTH_INVALID", "The API key is invalid, expired or revoked.", 401, False, True)
    ensure_schema(factory)
    body = token[len(KEY_PREFIX):] if token.startswith(KEY_PREFIX) else ""
    prefix, _, secret = body.partition("_")
    if not prefix or not secret or len(token) > 200:
        raise invalid
    with factory() as session:
        row = session.scalar(select(OrgApiKey).where(OrgApiKey.prefix == prefix))
        if row is None:
            # Burn comparable time so unknown prefixes are not distinguishable.
            hmac.compare_digest(_hash_key(settings, "x", secret), "0" * 64)
            raise invalid
        if not hmac.compare_digest(_hash_key(settings, row.salt, secret), row.key_hash):
            raise invalid
        now = _now()
        if row.revoked_at is not None or (row.expires_at is not None and row.expires_at <= now):
            raise invalid
        role = session.scalar(
            select(OrgMembership.role).where(OrgMembership.org_id == row.org_id, OrgMembership.user_id == row.created_by)
        )
        if role is None:  # creator left the org: the key dies with their membership
            raise invalid
        user = session.get(User, row.created_by)
        row.last_used_at = now
        scopes = frozenset(s for s in row.scopes.split(",") if s) & permissions_for(str(role))
        session.commit()
        return KeyIdentity(
            key_id=row.id,
            org_id=row.org_id,
            user_id=row.created_by,
            auth_subject=user.auth_subject if user else row.created_by,
            role=str(role),
            scopes=scopes,
        )


# --- audit chain -------------------------------------------------------------

def _row_hash(prev_hash: str, fields: dict[str, Any]) -> str:
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256((prev_hash + canonical).encode()).hexdigest()


def _hash_fields(e: OrgAuditEntry) -> dict[str, Any]:
    return {
        "seq": e.seq,
        "org_id": e.org_id,
        "user_id": e.user_id,
        "action": e.action,
        "target": e.target,
        "outcome": e.outcome,
        "request_id": e.request_id,
        "ip_hash": e.ip_hash,
        "ts": e.ts,
    }


def audit_record(
    factory: SessionFactory,
    org_id: str,
    user_id: str,
    action: str,
    target: str,
    outcome: str,
    *,
    request_id: str | None = None,
    ip: str | None = None,
    settings: Settings | None = None,
) -> None:
    if request_id is None:
        from ..ops.context import request_id_var

        request_id = request_id_var.get()
    ensure_schema(factory)
    with _lock:
        with factory() as session:
            last = session.execute(
                select(OrgAuditEntry.seq, OrgAuditEntry.row_hash)
                .where(OrgAuditEntry.org_id == org_id)
                .order_by(OrgAuditEntry.seq.desc())
                .limit(1)
            ).first()
            seq, prev = (last[0] + 1, last[1]) if last else (1, GENESIS_HASH)
            entry = OrgAuditEntry(
                org_id=org_id,
                seq=seq,
                user_id=user_id[:64],
                action=action[:80],
                target=target[:200],
                outcome=outcome[:20],
                request_id=(request_id or "-")[:80],
                ip_hash=ip_hash(settings, ip),
                ts=datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                prev_hash=prev,
                row_hash="",
            )
            entry.row_hash = _row_hash(prev, _hash_fields(entry))
            session.add(entry)
            session.commit()


def _audit_dict(e: OrgAuditEntry) -> dict[str, Any]:
    return {
        "seq": e.seq,
        "userId": e.user_id,
        "action": e.action,
        "target": e.target,
        "outcome": e.outcome,
        "requestId": e.request_id,
        "ipHash": e.ip_hash,
        "timestamp": e.ts,
        "hash": e.row_hash,
    }


def list_audit(
    factory: SessionFactory,
    org_id: str,
    *,
    limit: int,
    offset: int,
    action: str | None = None,
    user_id: str | None = None,
    outcome: str | None = None,
) -> dict[str, Any]:
    query = select(OrgAuditEntry).where(OrgAuditEntry.org_id == org_id)
    if action:
        query = query.where(OrgAuditEntry.action == action)
    if user_id:
        query = query.where(OrgAuditEntry.user_id == user_id)
    if outcome:
        query = query.where(OrgAuditEntry.outcome == outcome)
    with factory() as session:
        total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = session.scalars(query.order_by(OrgAuditEntry.seq.desc()).limit(limit).offset(offset)).all()
        return {"items": [_audit_dict(r) for r in rows], "total": int(total), "limit": limit, "offset": offset}


def verify_audit(factory: SessionFactory, org_id: str) -> dict[str, Any]:
    prev = GENESIS_HASH
    expected_seq = 1
    checked = 0
    with factory() as session:
        for e in session.scalars(select(OrgAuditEntry).where(OrgAuditEntry.org_id == org_id).order_by(OrgAuditEntry.seq)):
            if e.seq != expected_seq or e.prev_hash != prev or _row_hash(prev, _hash_fields(e)) != e.row_hash:
                return {"ok": False, "checked": checked, "firstInvalidSeq": e.seq, "headHash": None}
            prev = e.row_hash
            expected_seq += 1
            checked += 1
    return {"ok": True, "checked": checked, "firstInvalidSeq": None, "headHash": prev}
