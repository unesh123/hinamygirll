"""HINAA Foundry service: multi-file site generation, WCAG/HTML quality gate, SQLite revision store, and zip export."""

from __future__ import annotations

import hashlib
import io
import json
import re
import sqlite3
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..runtime_paths import project_root
from .components import build_site_files, detect_blueprint, extract_brand_and_place
from .tokens import FoundryPalette, contrast_ratio, resolve_palette


class QualityGateResult(BaseModel):
    passed: bool
    errors: List[str] = Field(default_factory=list)
    contrast_body: float
    contrast_cta: float


class FoundrySiteRecord(BaseModel):
    site_id: str
    brand: str
    tagline: str
    address: Optional[str] = None
    palette_name: str
    archetype: str
    revision: int = 1
    size_kb: float
    files: Dict[str, str]
    quality: QualityGateResult
    updated_at: str


def run_quality_gate(files: Dict[str, str], palette: FoundryPalette) -> QualityGateResult:
    html_src = files.get("index.html", "")
    errors: List[str] = []

    body_cr = contrast_ratio(palette.text, palette.bg)
    cta_cr = contrast_ratio(palette.accent_text, palette.accent)
    if body_cr < 4.5:
        errors.append(f"body contrast {body_cr} < 4.5:1")
    if cta_cr < 4.5:
        errors.append(f"CTA contrast {cta_cr} < 4.5:1")

    h1_count = len(re.findall(r"<h1\b", html_src, flags=re.IGNORECASE))
    if h1_count != 1:
        errors.append(f"expected exactly 1 <h1>, found {h1_count}")

    low_html = html_src.lower()
    for banned in ("lorem ipsum", "placeholder copy", "todo:", "coming soon placeholder"):
        if banned in low_html:
            errors.append(f"banned placeholder copy found: {banned!r}")

    if re.search(r'<img\b[^>]+src=["\']https?://', html_src, flags=re.IGNORECASE):
        errors.append("external http(s) img assets are disallowed in Foundry bundle")

    ids = set(re.findall(r'id=["\']([A-Za-z0-9_-]+)["\']', html_src))
    for href in re.findall(r'href=["\']#([A-Za-z0-9_-]+)["\']', html_src):
        if href not in ids:
            errors.append(f"unresolved anchor #{href}")

    for tag in ("main", "header", "footer", "section"):
        opens = len(re.findall(rf"<{tag}\b", html_src, flags=re.IGNORECASE))
        closes = len(re.findall(rf"</{tag}>", html_src, flags=re.IGNORECASE))
        if opens != closes:
            errors.append(f"unbalanced <{tag}> tags ({opens} open vs {closes} close)")

    return QualityGateResult(
        passed=len(errors) == 0,
        errors=errors,
        contrast_body=body_cr,
        contrast_cta=cta_cr,
    )


class FoundryService:
    def __init__(self, db_path: Optional[Path | str] = None) -> None:
        if db_path is None:
            self.db_path = project_root() / "apps" / "api" / "data" / "foundry_sites.db"
        else:
            self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS foundry_sites (
                    site_id TEXT PRIMARY KEY,
                    brand TEXT NOT NULL,
                    palette_name TEXT NOT NULL,
                    archetype TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def create_site(
        self,
        brief: str,
        *,
        palette: Optional[str] = None,
        logos: Optional[List[str]] = None,
        features: Optional[List[str]] = None,
    ) -> FoundrySiteRecord:
        brand, address = extract_brand_and_place(brief)
        pal = resolve_palette(palette)
        bp = detect_blueprint(brief)
        tagline = " ".join((brief or "").strip().split())[:220] or f"Crafted web experience for {brand}."
        feat_list = features or [
            f"{brand} tailored customer workflow with responsive precision.",
            "Instant performance budget with accessible high-contrast UI.",
            "Production multi-file bundle ready for preview and ZIP download.",
        ]
        files = build_site_files(
            brand=brand,
            tagline=tagline,
            address=address,
            palette=pal,
            blueprint=bp,
            features=feat_list,
            client_logos=list(logos or []),
        )
        gate = run_quality_gate(files, pal)
        if not gate.passed:
            raise ValueError("Foundry quality gate blocked build: " + "; ".join(gate.errors))

        total_bytes = sum(len(v.encode("utf-8")) for v in files.values())
        record = FoundrySiteRecord(
            site_id=f"site_{uuid.uuid4().hex[:10]}",
            brand=brand,
            tagline=tagline,
            address=address,
            palette_name=pal.name,
            archetype=bp.id,
            revision=1,
            size_kb=round(max(0.1, total_bytes / 1024.0), 1),
            files=files,
            quality=gate,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._save(record)
        return record

    def _save(self, rec: FoundrySiteRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO foundry_sites (site_id, brand, palette_name, archetype, revision, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(site_id) DO UPDATE SET
                    brand=excluded.brand,
                    palette_name=excluded.palette_name,
                    archetype=excluded.archetype,
                    revision=excluded.revision,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (
                    rec.site_id,
                    rec.brand,
                    rec.palette_name,
                    rec.archetype,
                    rec.revision,
                    rec.model_dump_json(),
                    rec.updated_at,
                ),
            )

    def get_site(self, site_id: str) -> Optional[FoundrySiteRecord]:
        with self._connect() as conn:
            row = conn.execute("SELECT payload_json FROM foundry_sites WHERE site_id = ?", (site_id,)).fetchone()
        if not row:
            return None
        return FoundrySiteRecord.model_validate_json(row[0])

    def list_sites(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT site_id, brand, palette_name, archetype, revision, updated_at FROM foundry_sites ORDER BY updated_at DESC LIMIT 100"
            ).fetchall()
        return [
            {
                "site_id": r[0],
                "brand": r[1],
                "palette_name": r[2],
                "archetype": r[3],
                "revision": r[4],
                "updated_at": r[5],
            }
            for r in rows
        ]

    def revise_site(
        self,
        site_id: str,
        *,
        instructions: str = "",
        palette: Optional[str] = None,
        tagline: Optional[str] = None,
        logos: Optional[List[str]] = None,
    ) -> Optional[FoundrySiteRecord]:
        existing = self.get_site(site_id)
        if existing is None:
            return None
        # Idempotent: keep existing brand name cleanly, never stack archetype suffixes, keep named palette unless changed.
        next_palette = resolve_palette(palette if palette else existing.palette_name)
        next_tag = tagline.strip() if tagline and tagline.strip() else (instructions.strip() or existing.tagline)
        bp = detect_blueprint(existing.archetype + " " + instructions)
        files = build_site_files(
            brand=existing.brand,
            tagline=next_tag[:220],
            address=existing.address,
            palette=next_palette,
            blueprint=bp,
            features=[
                f"{existing.brand}: {next_tag[:90]}",
                "Verified contrast and zero external image dependencies.",
                "Responsive layout validated for desktop and mobile viewports.",
            ],
            client_logos=list(logos or []),
        )
        gate = run_quality_gate(files, next_palette)
        if not gate.passed:
            raise ValueError("Foundry revision quality gate blocked build: " + "; ".join(gate.errors))

        total_bytes = sum(len(v.encode("utf-8")) for v in files.values())
        updated = FoundrySiteRecord(
            site_id=existing.site_id,
            brand=existing.brand,
            tagline=next_tag[:220],
            address=existing.address,
            palette_name=next_palette.name,
            archetype=existing.archetype,
            revision=existing.revision + 1,
            size_kb=round(max(0.1, total_bytes / 1024.0), 1),
            files=files,
            quality=gate,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        self._save(updated)
        return updated

    def delete_site(self, site_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM foundry_sites WHERE site_id = ?", (site_id,))
        return cur.rowcount > 0

    def render_self_contained_preview_html(self, site_id: str) -> Optional[str]:
        rec = self.get_site(site_id)
        if rec is None:
            return None
        html_doc = rec.files.get("index.html", "")
        css_doc = rec.files.get("styles.css", "")
        js_doc = rec.files.get("app.js", "")
        html_doc = html_doc.replace('<link rel="stylesheet" href="styles.css" />', f"<style>{css_doc}</style>")
        html_doc = html_doc.replace('<script src="app.js"></script>', f"<script>{js_doc}</script>")
        return html_doc

    def build_zip_bytes(self, site_id: str) -> Optional[tuple[bytes, str]]:
        rec = self.get_site(site_id)
        if rec is None:
            return None
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for fname, content in rec.files.items():
                zf.writestr(fname, content)
        raw = buf.getvalue()
        return raw, hashlib.sha256(raw).hexdigest()


_FOUNDRY_SINGLETON: Optional[FoundryService] = None


def get_foundry_service() -> FoundryService:
    global _FOUNDRY_SINGLETON
    if _FOUNDRY_SINGLETON is None:
        _FOUNDRY_SINGLETON = FoundryService()
    return _FOUNDRY_SINGLETON
