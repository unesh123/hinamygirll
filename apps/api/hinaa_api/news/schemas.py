"""Validated request shapes for the news REST routes and agent tools."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from .text import canonicalize_url

Cadence = Literal["manual", "hourly", "daily"]
Word = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class _Body(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


def _feed_urls(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        canonical = canonicalize_url(value)
        if canonical is None:
            raise ValueError(f"{value!r} is not an http(s) feed URL")
        if canonical not in out:
            out.append(canonical)
    return out


class WatchlistCreate(_Body):
    name: str = Field(min_length=1, max_length=120)
    topics: list[Word] = Field(default_factory=list, max_length=20)
    keywords: list[Word] = Field(default_factory=list, max_length=30)
    sources: list[str] = Field(default_factory=list, max_length=20)
    cadence: Cadence = "daily"
    dailyHour: int = Field(8, ge=0, le=23, description="Hour in Nepal time for daily runs")
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name is required")
        return value

    @field_validator("sources")
    @classmethod
    def _sources(cls, value: list[str]) -> list[str]:
        return _feed_urls(value)


class WatchlistPatch(_Body):
    name: str | None = Field(None, min_length=1, max_length=120)
    topics: list[Word] | None = Field(None, max_length=20)
    keywords: list[Word] | None = Field(None, max_length=30)
    sources: list[str] | None = Field(None, max_length=20)
    cadence: Cadence | None = None
    dailyHour: int | None = Field(None, ge=0, le=23)
    enabled: bool | None = None

    @field_validator("name", "topics", "keywords", "sources", "cadence", "dailyHour", "enabled")
    @classmethod
    def _not_null(cls, value):
        if value is None:
            raise ValueError("cannot be null")
        return value

    @field_validator("sources")
    @classmethod
    def _sources(cls, value: list[str]) -> list[str]:
        return _feed_urls(value)
