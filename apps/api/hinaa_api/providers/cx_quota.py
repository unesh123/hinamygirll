"""CX Gateway live quota and token balance parser."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import httpx

from ..config import get_settings

logger = logging.getLogger("hinaa.cx_quota")


@dataclass
class CXQuotaSummary:
    available: bool
    tokens_used: str | None = None
    tokens_remaining: str | None = None
    total_tokens: str | None = None
    requests_count: int | None = None
    percent_used: float | None = None
    recent_activity: list[dict[str, Any]] = field(default_factory=list)
    raw_error: str | None = None
    fetched_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_quota_cache: tuple[float, CXQuotaSummary] | None = None
_CACHE_TTL_SECONDS = 60.0


async def fetch_cx_quota(force: bool = False) -> CXQuotaSummary:
    """Fetch and parse live token quota from CX Gateway."""
    global _quota_cache

    now = time.time()
    if not force and _quota_cache is not None:
        cached_time, cached_summary = _quota_cache
        if now - cached_time < _CACHE_TTL_SECONDS:
            return cached_summary

    settings = get_settings()
    base_url = (settings.cx_gateway_base_url or "").strip().rstrip("/")
    api_key_secret = getattr(settings, "cx_gateway_quota_key", None) or settings.cx_gateway_api_key
    if not base_url or not api_key_secret:
        return CXQuotaSummary(available=False, raw_error="CX Gateway base URL or API key missing.")

    api_key = api_key_secret.get_secret_value().strip()
    quota_url = getattr(settings, "cx_gateway_quota_url", None) or f"{base_url}/quota"
    full_url = f"{quota_url}?key={api_key}"

    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            resp = await client.get(full_url)
            if resp.status_code != 200:
                summary = CXQuotaSummary(
                    available=False,
                    raw_error=f"HTTP {resp.status_code} returned from quota endpoint.",
                )
                _quota_cache = (now, summary)
                return summary

            html = resp.text

            # Metric values extraction
            vals = re.findall(r'<strong class="metric-value">([^<]+)</strong>', html)
            used_str = vals[0].strip() if len(vals) > 0 else None
            remaining_str = vals[1].strip() if len(vals) > 1 else None
            total_str = vals[2].strip() if len(vals) > 2 else None
            requests_cnt = int(vals[3].strip()) if len(vals) > 3 and vals[3].strip().isdigit() else None

            # Calculate approximate percent used
            percent = None
            if used_str and total_str:
                def _to_num(val: str) -> float:
                    clean = re.sub(r"[^\d.]", "", val)
                    num = float(clean) if clean else 0.0
                    if "m" in val.lower():
                        num *= 1_000_000
                    elif "k" in val.lower():
                        num *= 1_000
                    return num

                u = _to_num(used_str)
                t = _to_num(total_str)
                if t > 0:
                    percent = round((u / t) * 100.0, 1)

            # Parse recent activity table
            recent_rows: list[dict[str, Any]] = []
            rows = re.findall(
                r'<tr>\s*<td>.*?<span[^>]*>([^<]+)</span>.*?<td>.*?<span[^>]*>([^<]+)</span>.*?<td>.*?<span[^>]*>([^<]+)</span>.*?<td>.*?<span[^>]*>([^<]+)</span>.*?</tr>',
                html,
                re.DOTALL,
            )
            for row in rows[:10]:
                recent_rows.append({
                    "model": row[0].strip(),
                    "tokens_in": row[1].strip(),
                    "tokens_out": row[2].strip(),
                    "timestamp": row[3].strip(),
                })

            summary = CXQuotaSummary(
                available=True,
                tokens_used=used_str,
                tokens_remaining=remaining_str,
                total_tokens=total_str,
                requests_count=requests_cnt,
                percent_used=percent,
                recent_activity=recent_rows,
                fetched_at=now,
            )
            _quota_cache = (now, summary)
            return summary

    except Exception as exc:
        logger.warning("Failed to fetch CX quota: %s", exc)
        summary = CXQuotaSummary(
            available=False,
            raw_error=f"Error fetching quota: {exc.__class__.__name__}",
            fetched_at=now,
        )
        _quota_cache = (now, summary)
        return summary