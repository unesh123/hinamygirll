"""Tables for organisations, memberships, API keys and the audit chain (migration 0018)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, event, func
from sqlalchemy.orm import Mapped, mapped_column

from ..persistence.orm import Base


def _uuid() -> str:
    return str(uuid4())


class Organisation(Base):
    __tablename__ = "organisations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    is_personal: Mapped[bool] = mapped_column(default=False)
    created_by: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrgMembership(Base):
    __tablename__ = "org_memberships"
    __table_args__ = (UniqueConstraint("org_id", "user_id", name="uq_org_membership"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrgApiKey(Base):
    __tablename__ = "org_api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"), index=True)
    created_by: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(120))
    prefix: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    salt: Mapped[str] = mapped_column(String(64))
    key_hash: Mapped[str] = mapped_column(String(64))
    scopes: Mapped[str] = mapped_column(Text())  # comma separated permissions
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)  # naive UTC
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


class OrgAuditEntry(Base):
    """Append-only; each row's hash covers the previous row's hash in the same org."""

    __tablename__ = "org_audit_log"
    __table_args__ = (UniqueConstraint("org_id", "seq", name="uq_org_audit_seq"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    org_id: Mapped[str] = mapped_column(String(36), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    target: Mapped[str] = mapped_column(String(200), default="")
    outcome: Mapped[str] = mapped_column(String(20))
    request_id: Mapped[str] = mapped_column(String(80), default="-")
    ip_hash: Mapped[str] = mapped_column(String(64), default="")
    ts: Mapped[str] = mapped_column(String(32))  # ISO-8601 UTC, stored verbatim so the hash is reproducible
    prev_hash: Mapped[str] = mapped_column(String(64))
    row_hash: Mapped[str] = mapped_column(String(64))


@event.listens_for(OrgAuditEntry, "before_update")
@event.listens_for(OrgAuditEntry, "before_delete")
def _audit_is_append_only(*_args) -> None:  # type: ignore[no-untyped-def]
    raise RuntimeError("The audit log is append-only.")


IDENTITY_TABLES = (
    Organisation.__table__,
    OrgMembership.__table__,
    OrgApiKey.__table__,
    OrgAuditEntry.__table__,
)
