"""DOM, ARIA Accessibility, and Structured Content Extraction.

Extracts semantic page trees, tables, forms, and headings, and converts
observations into Phase 06 CRAG Source models with provenance and sanitization.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from playwright.async_api import Page

from .policy import BrowserSecurityPolicy

# Import Phase 06 Research Models if available
try:
    from ..research.models import Source, TrustTier
except ImportError:
    Source = None
    TrustTier = None

logger = logging.getLogger("hinaa.browser.extraction")


class PageExtractor:
    """Extracts structured data, accessibility trees, tables, and sanitized content."""

    @staticmethod
    async def extract_metadata_and_text(page: Page) -> Dict[str, Any]:
        """Extracts page title, URL, headings, and clean visible text."""
        url = page.url
        title = await page.title()

        # Extract headings via static DOM evaluation
        headings = await page.evaluate(
            """() => {
                const results = [];
                document.querySelectorAll('h1, h2, h3').forEach(el => {
                    const text = el.innerText.trim();
                    if (text) results.push({ tag: el.tagName.toLowerCase(), text: text });
                });
                return results;
            }"""
        )

        # Extract visible body text
        raw_text = await page.evaluate("() => document.body ? document.body.innerText : ''")
        sanitized_text = BrowserSecurityPolicy.sanitize_untrusted_page_content(raw_text)

        return {
            "url": url,
            "title": title,
            "headings": headings,
            "raw_text_length": len(raw_text),
            "sanitized_content": sanitized_text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    async def extract_interactive_elements(page: Page) -> List[Dict[str, Any]]:
        """Extracts accessible buttons, links, inputs, and form controls."""
        elements = await page.evaluate(
            """() => {
                const items = [];
                const query = 'button, a[href], input, select, textarea, [role="button"], [role="link"], [role="checkbox"]';
                document.querySelectorAll(query).forEach((el, idx) => {
                    if (idx > 100) return; // Cap at 100 elements
                    const rect = el.getBoundingClientRect();
                    const isVisible = rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).display !== 'none';
                    if (!isVisible) return;

                    items.push({
                        tag: el.tagName.toLowerCase(),
                        role: el.getAttribute('role') || el.tagName.toLowerCase(),
                        text: (el.innerText || el.value || el.getAttribute('aria-label') || el.placeholder || '').trim().slice(0, 80),
                        id: el.id || null,
                        name: el.getAttribute('name') || null,
                        type: el.getAttribute('type') || null,
                        href: el.getAttribute('href') || null,
                        is_disabled: el.disabled || el.getAttribute('aria-disabled') === 'true',
                    });
                });
                return items;
            }"""
        )
        return elements

    @staticmethod
    async def extract_table_data(page: Page, table_selector: str = "table") -> List[Dict[str, Any]]:
        """Extracts structured rows and columns from an HTML table."""
        table_data = await page.evaluate(
            f"""(sel) => {{
                const table = document.querySelector(sel);
                if (!table) return [];
                const rows = [];
                const headers = [];
                table.querySelectorAll('th').forEach(th => headers.push(th.innerText.trim()));
                
                table.querySelectorAll('tbody tr, tr').forEach(tr => {{
                    const cells = [];
                    tr.querySelectorAll('td').forEach(td => cells.push(td.innerText.trim()));
                    if (cells.length > 0) {{
                        if (headers.length === cells.length) {{
                            const rowObj = {{}};
                            headers.forEach((h, i) => rowObj[h || `col_${{i}}`] = cells[i]);
                            rows.push(rowObj);
                        }} else {{
                            rows.push({{ cells }});
                        }}
                    }}
                }});
                return rows;
            }}""",
            table_selector,
        )
        return table_data

    @staticmethod
    def convert_to_crag_source(
        url: str,
        title: str,
        content: str,
        query: str = "",
        publisher: str = "Web Extraction",
    ) -> Any:
        """Converts extracted web content to a Phase 06 CRAG Source model with provenance."""
        if Source is None or TrustTier is None:
            return {
                "source_id": f"src-web-{hashlib.md5(url.encode()).hexdigest()[:8]}",
                "title": title,
                "url": url,
                "excerpt": content[:1200],
                "publisher": publisher,
            }

        source_id = f"src-web-{hashlib.md5(url.encode()).hexdigest()[:8]}"
        src = Source(
            source_id=source_id,
            title=title or "Web Observation",
            url=url,
            publisher=publisher,
            publication_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            excerpt=content[:1200],
            query=query,
            trust_tier=TrustTier.REPUTABLE_SECONDARY,
        )
        src.compute_hash(content)
        return src
