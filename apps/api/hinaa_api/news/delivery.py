"""Pluggable digest delivery. Other channels implement `Deliverer` and call `register_deliverer`."""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger("hinaa.news")


@runtime_checkable
class Deliverer(Protocol):
    """A destination for finished digests (in-app, chat, email...).

    `deliver` receives the owner's id and the public digest dict (title, items with
    cited URLs). It must be idempotent per digest id and may raise; failures are
    recorded on the run and never block other channels or the saved digest.
    """

    name: str

    async def deliver(self, user_id: str, digest: dict[str, Any]) -> None: ...


class InAppDeliverer:
    """Writes an autopilot notification that the shell's notification feed already shows."""

    name = "in_app"

    def __init__(self, store: Any | None = None) -> None:
        self._store = store

    async def deliver(self, user_id: str, digest: dict[str, Any]) -> None:
        import time
        import uuid

        from ..autopilot.contracts import Notification, SeverityLevel

        store = self._store
        if store is None:
            from ..autopilot.service import autopilot_service

            store = autopilot_service.store
        key = f"news:{digest['id']}"
        if store.get_notification_by_idempotency_key("default", key):
            return
        lead = digest["items"][0]["text"] if digest["items"] else ""
        store.save_notification(
            Notification(
                notification_id=f"ntf-{uuid.uuid4().hex[:12]}",
                tenant_id="default",
                user_id=user_id,
                event_type="news.digest",
                title=digest["title"],
                message=f"{len(digest['items'])} stories. {lead}"[:500],
                severity=SeverityLevel.INFO,
                created_at_utc=time.time(),
                idempotency_key=key,
                metadata={"digestId": digest["id"], "urls": digest["sources"][:10]},
            )
        )


_registry: dict[str, Deliverer] = {}


def register_deliverer(deliverer: Deliverer) -> None:
    _registry[deliverer.name] = deliverer


def unregister_deliverer(name: str) -> None:
    _registry.pop(name, None)


def active_deliverers() -> list[Deliverer]:
    return list(_registry.values())


register_deliverer(InAppDeliverer())


async def deliver_all(
    user_id: str, digest: dict[str, Any], deliverers: list[Deliverer] | None = None
) -> list[dict[str, Any]]:
    results = []
    for d in deliverers if deliverers is not None else active_deliverers():
        try:
            await d.deliver(user_id, digest)
            results.append({"channel": d.name, "ok": True})
        except Exception as error:  # one broken channel must not hide the others
            logger.warning("News delivery via %s failed", d.name, exc_info=True)
            results.append({"channel": d.name, "ok": False, "error": str(error)[:200]})
    return results
