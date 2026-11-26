"""Adaptive Response Protocol v1: typed blocks with verified asset/dataset provenance checks."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Set, Union

from pydantic import BaseModel, Field


class MarkdownBlock(BaseModel):
    id: str
    type: Literal["markdown"] = "markdown"
    content: str


class MetricItem(BaseModel):
    label: str
    value: Union[int, float, str]
    unit: Optional[str] = None
    source_ref: str


class MetricGridBlock(BaseModel):
    id: str
    type: Literal["metric_grid"] = "metric_grid"
    items: List[MetricItem]


class ChartBlock(BaseModel):
    id: str
    type: Literal["chart"] = "chart"
    title: str
    chart_type: Literal["line", "bar", "area", "scatter"] = "line"
    dataset_ref: str
    points: List[Dict[str, Union[str, int, float]]] = Field(default_factory=list)


class DiagramBlock(BaseModel):
    id: str
    type: Literal["diagram"] = "diagram"
    title: str
    mermaid: str


class ImageGalleryBlock(BaseModel):
    id: str
    type: Literal["image_gallery"] = "image_gallery"
    asset_refs: List[str]


class PreviewCardBlock(BaseModel):
    id: str
    type: Literal["preview_card"] = "preview_card"
    title: str
    preview_url: str
    verified: bool = False


ResponseBlock = Union[
    MarkdownBlock,
    MetricGridBlock,
    ChartBlock,
    DiagramBlock,
    ImageGalleryBlock,
    PreviewCardBlock,
]


class ResponseDocument(BaseModel):
    version: int = 1
    response_id: str
    blocks: List[ResponseBlock]

    def validate_provenance(
        self,
        *,
        verified_assets: Set[str],
        verified_datasets: Set[str],
        verified_sources: Set[str],
    ) -> List[str]:
        """Fail-closed check ensuring zero fabricated asset IDs or dataset refs."""
        errors: List[str] = []
        for blk in self.blocks:
            if isinstance(blk, MetricGridBlock):
                for item in blk.items:
                    if item.source_ref not in verified_sources and item.source_ref not in verified_datasets:
                        errors.append(f"unverified metric source_ref: {item.source_ref!r}")
            elif isinstance(blk, ChartBlock):
                if blk.dataset_ref not in verified_datasets:
                    errors.append(f"unverified chart dataset_ref: {blk.dataset_ref!r}")
            elif isinstance(blk, ImageGalleryBlock):
                for ref in blk.asset_refs:
                    if ref not in verified_assets:
                        errors.append(f"unverified gallery asset_ref: {ref!r}")
        return errors
