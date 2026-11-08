"""URL canonicalisation, near-duplicate detection and clustering."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PARAMS = frozenset(
    {
        "fbclid",
        "gclid",
        "dclid",
        "msclkid",
        "mc_cid",
        "mc_eid",
        "igshid",
        "ref",
        "ref_src",
        "cmpid",
        "spm",
        "ocid",
    }
)
_STOPWORDS = frozenset(
    "a an and are as at be by for from has have in is it its of on or that the to was were will with after over new says say".split()
)
_DEFAULT_PORTS = {"http": 80, "https": 443}


@dataclass
class Article:
    title: str
    url: str
    source: str = ""
    published: datetime | None = None
    summary: str = ""
    origin: str = "feed"  # feed | search
    score: float = 0.0
    also: list[str] = field(default_factory=list)  # canonical URLs of merged duplicates


def canonicalize_url(url: str) -> str | None:
    """Stable form of an http(s) URL for dedupe; None when it is not a usable web link."""
    try:
        parts = urlsplit(url.strip())
        host = (parts.hostname or "").lower()
        port = parts.port
    except ValueError:
        return None
    scheme = parts.scheme.lower()
    if scheme not in _DEFAULT_PORTS or not host:
        return None
    host = host.removeprefix("www.")
    netloc = host if port in (None, _DEFAULT_PORTS[scheme]) else f"{host}:{port}"
    query = sorted(
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_PARAMS
    )
    path = re.sub(r"/{2,}", "/", parts.path).rstrip("/") or "/"
    return urlunsplit((scheme, netloc, path, urlencode(query), ""))


def title_tokens(title: str) -> frozenset[str]:
    words = re.findall(r"[^\W_]+", title.lower())
    return frozenset(w for w in words if w not in _STOPWORDS and len(w) > 1)


def title_similarity(a: str, b: str) -> float:
    """Jaccard overlap of significant title words, 0..1."""
    ta, tb = title_tokens(a), title_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def dedupe(articles: list[Article], threshold: float = 0.6) -> list[Article]:
    """Collapse identical canonical URLs and near-duplicate titles.

    The first article of each group is kept (callers pass them best-first); the
    URLs of what it absorbed stay on `also` so a digest can cite every source.
    """
    kept: list[Article] = []
    seen_urls: set[str] = set()
    for article in articles:
        canonical = canonicalize_url(article.url)
        if canonical is None or canonical in seen_urls:
            continue
        seen_urls.add(canonical)
        article.url = canonical
        match = next(
            (k for k in kept if title_similarity(k.title, article.title) >= threshold), None
        )
        if match is not None:
            match.also.append(canonical)
        else:
            kept.append(article)
    return kept

# ruff: noqa: E501
