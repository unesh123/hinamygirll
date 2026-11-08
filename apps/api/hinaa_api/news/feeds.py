"""RSS 2.0 / Atom fetching and parsing. Pure stdlib; DTD and entity declarations are refused."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from xml.etree import ElementTree as ET

import httpx

from ..autopilot.security import SSRFGuard
from .text import Article, canonicalize_url

MAX_FEED_BYTES = 2_000_000
_TAG = re.compile(r"<[^>]+>")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _clean(text: str | None) -> str:
    return re.sub(r"\s+", " ", unescape(_TAG.sub(" ", text or ""))).strip()


def _when(raw: str | None) -> datetime | None:
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    try:
        moment = parsedate_to_datetime(raw)
    except TypeError, ValueError:
        try:
            moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def parse_feed(xml: str | bytes, feed_url: str = "") -> list[Article]:
    raw = xml.encode("utf-8") if isinstance(xml, str) else xml
    upper = raw.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("Feed rejected: DTD/entity declarations are not allowed")
    root = ET.fromstring(raw)  # noqa: S314 - DTD/entity declarations rejected above
    channel_title = ""
    for node in root.iter():
        if _local(node.tag) == "title":
            channel_title = _clean(node.text)
            break
    articles: list[Article] = []
    for entry in root.iter():
        if _local(entry.tag) not in ("item", "entry"):
            continue
        fields: dict[str, str] = {}
        link = ""
        for child in entry:
            name = _local(child.tag)
            if name == "link":
                href = child.get("href")
                if href and child.get("rel", "alternate") == "alternate":
                    link = link or href
                elif child.text and child.text.strip():
                    link = link or child.text.strip()
            elif name in (
                "title",
                "description",
                "summary",
                "content",
                "pubdate",
                "published",
                "updated",
                "date",
            ):
                fields.setdefault(name, child.text or "")
        canonical = canonicalize_url(link) if link else None
        title = _clean(fields.get("title"))
        if not canonical or not title:
            continue
        stamp = (
            fields.get("pubdate")
            or fields.get("published")
            or fields.get("updated")
            or fields.get("date")
        )
        articles.append(
            Article(
                title=title,
                url=canonical,
                source=channel_title or feed_url,
                published=_when(stamp),
                summary=_clean(
                    fields.get("description") or fields.get("summary") or fields.get("content")
                )[:600],
                origin="feed",
            )
        )
    return articles


async def fetch_feed(client: httpx.AsyncClient, url: str) -> list[Article]:
    safe, reason = SSRFGuard.is_safe_url(url)
    if not safe:
        raise ValueError(f"Feed URL refused: {reason}")
    response = await client.get(
        url, headers={"Accept": "application/rss+xml, application/atom+xml, text/xml, */*"}
    )
    response.raise_for_status()
    if len(response.content) > MAX_FEED_BYTES:
        raise ValueError("Feed too large")
    return parse_feed(response.content, url)
