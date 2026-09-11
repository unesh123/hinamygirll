from __future__ import annotations

import base64
import logging
import re
from typing import Any
import httpx
from .asset_store import AssetStore, get_asset_store
from .extractors import (
    extract_csv_summary,
    extract_docx_text,
    extract_text_document,
    extract_xlsx_summary,
    inspect_zip_archive,
)
from .models import AssetKind, AssetRef, AssetSource, ProviderImageInput

logger = logging.getLogger("hinaa.media.resolver")


class ResolvedMedia:
    def __init__(
        self,
        asset_id: str,
        bytes_data: bytes,
        mime_type: str,
        sha256: str,
        width: int | None = None,
        height: int | None = None,
        source_ref: AssetRef | None = None,
        kind: AssetKind = AssetKind.IMAGE,
        role: str | None = None,
        filename: str | None = None,
        extracted_text: str | None = None,
    ) -> None:
        self.asset_id = asset_id
        self.bytes_data = bytes_data
        self.mime_type = mime_type
        self.sha256 = sha256
        self.width = width
        self.height = height
        self.source_ref = source_ref
        self.kind = kind
        self.role = role
        self.filename = filename or (source_ref.filename if source_ref else None)
        self.extracted_text = extracted_text

    def to_provider_input(self, role: str | None = None) -> ProviderImageInput:
        return ProviderImageInput(
            bytes_data=self.bytes_data,
            mime_type=self.mime_type,
            role=role or self.role,
            asset_id=self.asset_id,
        )


def _extract_media_text(raw_bytes: bytes, mime_type: str, filename: str | None) -> str | None:
    fn = (filename or "").lower()
    mt = (mime_type or "").lower()

    if mt == "text/csv" or fn.endswith(".csv"):
        return extract_csv_summary(raw_bytes)
    if "spreadsheetml" in mt or "excel" in mt or fn.endswith(".xlsx"):
        return extract_xlsx_summary(raw_bytes)
    if "wordprocessingml" in mt or fn.endswith(".docx"):
        return extract_docx_text(raw_bytes)
    if mt == "application/zip" or fn.endswith(".zip"):
        return inspect_zip_archive(raw_bytes)
    if mt.startswith("text/") or mt in ("application/json", "application/javascript") or fn.endswith((".txt", ".md", ".json", ".py", ".html", ".js")):
        return extract_text_document(raw_bytes)
    return None


class MediaResolver:
    """Resolves asset IDs, data URIs, or remote URLs into validated, canonical media bytes."""

    def __init__(self, asset_store: AssetStore | None = None) -> None:
        self.asset_store = asset_store or get_asset_store()

    async def resolve(self, reference: str, role: str | None = None) -> ResolvedMedia:
        """Resolves an asset reference (ID, data URI, or URL)."""
        ref_str = reference.strip()

        # 1. Check if it's an asset ID
        stored = self.asset_store.get_asset(ref_str)
        if stored:
            data = self.asset_store.read_bytes(ref_str)
            if not data:
                raise ValueError(f"Asset file missing on disk for ID: {ref_str}")
            extracted = _extract_media_text(data, stored.mime_type, stored.filename)
            return ResolvedMedia(
                asset_id=stored.id,
                bytes_data=data,
                mime_type=stored.mime_type,
                sha256=stored.sha256,
                width=stored.width,
                height=stored.height,
                source_ref=stored,
                kind=stored.kind,
                role=role,
                filename=stored.filename,
                extracted_text=extracted,
            )

        # 2. Check if it's a data URI (e.g. data:image/png;base64,... or data:application/pdf;base64,...)
        if ref_str.startswith("data:"):
            match = re.match(r"^data:([a-zA-Z0-9.+_/-]+);base64,(.+)$", ref_str, re.DOTALL)
            if not match:
                raise ValueError("Malformed data URI.")
            mime = match.group(1)
            b64_str = match.group(2)
            raw_bytes = base64.b64decode(b64_str)
            stored = self.asset_store.store_bytes(raw_bytes, mime_type=mime, source=AssetSource.UPLOAD)
            extracted = _extract_media_text(raw_bytes, stored.mime_type, stored.filename)
            return ResolvedMedia(
                asset_id=stored.id,
                bytes_data=raw_bytes,
                mime_type=stored.mime_type,
                sha256=stored.sha256,
                width=stored.width,
                height=stored.height,
                source_ref=stored,
                kind=stored.kind,
                role=role,
                filename=stored.filename,
                extracted_text=extracted,
            )

        # 3. Check if it's an HTTP URL
        if ref_str.startswith("http://") or ref_str.startswith("https://"):
            # SSRF check: prevent localhost / local network loops
            if any(h in ref_str.lower() for h in ("127.0.0.1", "localhost", "192.168.", "10.0.", "169.254.")):
                # If it's our own local asset endpoint, extract asset ID directly!
                local_asset_match = re.search(r"/v1/assets/([a-zA-Z0-9_-]+)", ref_str)
                if local_asset_match:
                    return await self.resolve(local_asset_match.group(1), role=role)
                raise ValueError("Restricted local network address rejected for security.")

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(ref_str)
                resp.raise_for_status()
                mime = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
                stored = self.asset_store.store_bytes(resp.content, mime_type=mime, source=AssetSource.URL)
                extracted = _extract_media_text(resp.content, stored.mime_type, stored.filename)
                return ResolvedMedia(
                    asset_id=stored.id,
                    bytes_data=resp.content,
                    mime_type=stored.mime_type,
                    sha256=stored.sha256,
                    width=stored.width,
                    height=stored.height,
                    source_ref=stored,
                    kind=stored.kind,
                    role=role,
                    filename=stored.filename,
                    extracted_text=extracted,
                )

        raise ValueError(f"Unable to resolve media reference: '{ref_str[:50]}...'")
