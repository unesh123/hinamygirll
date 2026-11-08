"""Digest building. Every bullet must cite a URL that was actually fetched; nothing else is saved."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from ..config import Settings
from .text import Article, canonicalize_url

logger = logging.getLogger("hinaa.news")

Summarizer = Callable[[str], Awaitable[str]]
_URL_IN_TEXT = re.compile(r"https?://[^\s)>\]\"'<]+")
MAX_BULLET_CHARS = 400


class DigestValidationError(ValueError):
    """A digest bullet cites nothing, or cites a URL no fetch returned."""


def fetched_urls(articles: list[Article]) -> set[str]:
    urls: set[str] = set()
    for a in articles:
        urls.add(a.url)
        urls.update(a.also)
    return urls


def validate_items(items: list[dict[str, Any]], fetched: set[str]) -> None:
    for item in items:
        text, urls = str(item.get("text", "")).strip(), item.get("urls") or []
        if not text:
            raise DigestValidationError("Digest bullet has no text")
        if not urls:
            raise DigestValidationError(f"Digest bullet cites no source: {text[:60]!r}")
        for url in [*urls, *_URL_IN_TEXT.findall(text)]:
            if canonicalize_url(url) not in fetched:
                raise DigestValidationError(f"Digest cites a URL that was never fetched: {url}")


def _first_sentence(text: str, limit: int = 220) -> str:
    sentence = re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0]
    return sentence[:limit].rstrip()


def extractive_items(articles: list[Article], limit: int) -> list[dict[str, Any]]:
    items = []
    for a in articles[:limit]:
        lead = _first_sentence(a.summary) if a.summary else ""
        text = (
            a.title
            if not lead or lead.lower().startswith(a.title.lower()[:30])
            else f"{a.title} — {lead}"
        )
        items.append(
            {"text": text[:MAX_BULLET_CHARS], "urls": [a.url, *a.also[:3]], "source": a.source}
        )
    return items


def _prompt(articles: list[Article], limit: int) -> str:
    stories = [
        {
            "n": i,
            "title": a.title,
            "summary": a.summary[:300],
            "source": a.source,
            "urls": [a.url, *a.also[:3]],
        }
        for i, a in enumerate(articles[:limit])
    ]
    return (
        "Write a news digest from ONLY the stories below. Return a JSON array; each element is "
        '{"text": one factual sentence, "urls": [urls copied verbatim from that story]}. '
        "Never add facts, numbers or URLs that are not in the stories. Merge stories about the same event.\n\n"
        + json.dumps(stories, ensure_ascii=False)
    )


def _parse_llm(raw: str) -> list[dict[str, Any]]:
    start, end = raw.find("["), raw.rfind("]")
    data = json.loads(raw[start : end + 1]) if start != -1 and end > start else []
    return [x for x in data if isinstance(x, dict)]


async def build_items(
    articles: list[Article], summarizer: Summarizer | None, limit: int = 8
) -> tuple[list[dict[str, Any]], str]:
    """(bullets, generated_by). LLM output is accepted per bullet only if it cites fetched URLs."""
    fetched = fetched_urls(articles)
    if summarizer is not None and articles:
        try:
            accepted = []
            for item in _parse_llm(await summarizer(_prompt(articles, limit))):
                candidate = {
                    "text": str(item.get("text", "")).strip()[:MAX_BULLET_CHARS],
                    "urls": [
                        canonicalize_url(u) or str(u)
                        for u in (item.get("urls") or [])
                        if isinstance(u, str)
                    ],
                }
                try:
                    validate_items([candidate], fetched)
                except DigestValidationError as error:
                    logger.warning("Dropped LLM bullet: %s", error)
                    continue
                accepted.append(candidate)
            if accepted:
                return accepted[:limit], "llm"
        except Exception:
            logger.warning("LLM summarizer failed; using extractive digest", exc_info=True)
    items = extractive_items(articles, limit)
    validate_items(items, fetched)
    return items, "extractive"


def default_summarizer(settings: Settings) -> Summarizer | None:
    """OpenAI-compatible chat call using the configured OpenAI or Groq key; None when neither is set."""
    if settings.openai_api_key and settings.openai_api_key.get_secret_value().strip():
        url, key, model = (
            "https://api.openai.com/v1/chat/completions",
            settings.openai_api_key,
            settings.openai_fast_model,
        )
    elif settings.groq_api_key and settings.groq_api_key.get_secret_value().strip():
        url, key, model = (
            "https://api.groq.com/openai/v1/chat/completions",
            settings.groq_api_key,
            settings.groq_model,
        )
    else:
        return None

    async def summarize(prompt: str) -> str:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {key.get_secret_value()}"},
                json={"model": model, "messages": [{"role": "user", "content": prompt}]},
            )
            response.raise_for_status()
            return str(response.json()["choices"][0]["message"]["content"])

    return summarize

# ruff: noqa: E501
