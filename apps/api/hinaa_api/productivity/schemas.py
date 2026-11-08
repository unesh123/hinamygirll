"""Validated request shapes shared by the REST routes and the agent tools."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, field_validator

Platform = Literal["instagram", "tiktok", "youtube", "x", "linkedin", "facebook", "other"]
PostStatus = Literal["idea", "draft", "scheduled", "published"]
ProjectStatus = Literal["planning", "active", "blocked", "done"]
Priority = Literal["low", "medium", "high"]
Period = Literal["day", "week", "month"]

PLATFORMS: tuple[str, ...] = ("instagram", "tiktok", "youtube", "x", "linkedin", "facebook", "other")

Text = Annotated[str, StringConstraints(strip_whitespace=True)]
Tag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]


def _local_wall_clock(value: datetime | None) -> datetime | None:
    """The calendar stores the clock he reads, so an offset is collapsed onto local time."""
    if value is not None and value.tzinfo is not None:
        value = value.astimezone().replace(tzinfo=None)
    return value


def _upper_currency(value: str | None) -> str | None:
    if value is None:
        return None
    code = value.strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise ValueError("currency must be a 3-letter code such as NPR")
    return code


WallClock = Annotated[datetime, AfterValidator(_local_wall_clock)]
Currency = Annotated[str, AfterValidator(_upper_currency)]


class _Body(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class ContentPostCreate(_Body):
    title: Text = Field(min_length=1, max_length=200)
    platform: Platform = "other"
    caption: Text = Field("", max_length=5000)
    scheduledFor: WallClock | None = None
    status: PostStatus = "idea"
    tags: list[Tag] = Field(default_factory=list, max_length=20)
    notes: Text = Field("", max_length=5000)


class ContentPostPatch(_Body):
    title: Text | None = Field(None, min_length=1, max_length=200)
    platform: Platform | None = None
    caption: Text | None = Field(None, max_length=5000)
    scheduledFor: WallClock | None = None
    status: PostStatus | None = None
    tags: list[Tag] | None = Field(None, max_length=20)
    notes: Text | None = Field(None, max_length=5000)

    @field_validator("title", "platform", "status", "tags", "caption", "notes")
    @classmethod
    def _not_null(cls, value):  # an explicit null would wipe a required column
        if value is None:
            raise ValueError("cannot be null")
        return value


class SalesRecordCreate(_Body):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2, allow_inf_nan=False)
    occurredOn: date | None = None
    currency: Currency | None = None
    source: Text = Field("", max_length=80)
    customer: Text = Field("", max_length=120)
    product: Text = Field("", max_length=120)
    notes: Text = Field("", max_length=2000)


class SalesRecordPatch(_Body):
    amount: Decimal | None = Field(None, gt=0, max_digits=14, decimal_places=2, allow_inf_nan=False)
    occurredOn: date | None = None
    currency: Currency | None = None
    source: Text | None = Field(None, max_length=80)
    customer: Text | None = Field(None, max_length=120)
    product: Text | None = Field(None, max_length=120)
    notes: Text | None = Field(None, max_length=2000)

    @field_validator("amount", "occurredOn", "currency", "source", "customer", "product", "notes")
    @classmethod
    def _not_null(cls, value):
        if value is None:
            raise ValueError("cannot be null")
        return value


class ProjectCreate(_Body):
    name: Text = Field(min_length=1, max_length=160)
    status: ProjectStatus = "planning"
    priority: Priority = "medium"
    dueDate: date | None = None
    progress: int = Field(0, ge=0, le=100)
    nextAction: Text = Field("", max_length=1000)
    notes: Text = Field("", max_length=5000)


class ProjectPatch(_Body):
    name: Text | None = Field(None, min_length=1, max_length=160)
    status: ProjectStatus | None = None
    priority: Priority | None = None
    dueDate: date | None = None
    progress: int | None = Field(None, ge=0, le=100)
    nextAction: Text | None = Field(None, max_length=1000)
    notes: Text | None = Field(None, max_length=5000)

    @field_validator("name", "status", "priority", "progress", "nextAction", "notes")
    @classmethod
    def _not_null(cls, value):
        if value is None:
            raise ValueError("cannot be null")
        return value
