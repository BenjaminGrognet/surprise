"""Normalized records produced by collectors, mirroring supabase/migrations."""

import hashlib
import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import AwareDatetime, BaseModel, Field, HttpUrl, computed_field, field_validator, model_validator

from surprise.categories import CATEGORIES

PARIS_POSTAL_CODE = re.compile(r"^750(0[1-9]|1[0-9]|20)$|^75116$")


class ActivityKind(StrEnum):
    PERMANENT = "permanent"
    TEMPORARY = "temporary"


class PriceUnit(StrEnum):
    PER_PERSON = "per_person"
    PER_COUPLE = "per_couple"
    PER_GROUP = "per_group"


class RawRecord(BaseModel):
    source_id: str
    external_id: str
    url: HttpUrl | None = None
    payload: dict[str, Any]
    fetched_at: AwareDatetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @computed_field
    @property
    def content_hash(self) -> str:
        canonical = json.dumps(self.payload, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()


class Venue(BaseModel):
    name: str
    address: str | None = None
    postal_code: str
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    website: HttpUrl | None = None
    opening_hours: dict[str, Any] | None = None

    @field_validator("postal_code")
    @classmethod
    def must_be_paris_intra_muros(cls, value: str) -> str:
        value = value.strip()
        if not PARIS_POSTAL_CODE.match(value):
            raise ValueError(f"hors Paris intra-muros : {value}")
        return value

    @computed_field
    @property
    def arrondissement(self) -> int:
        return 16 if self.postal_code == "75116" else int(self.postal_code[-2:])


class Image(BaseModel):
    url: HttpUrl
    license: str
    source_url: HttpUrl | None = None


class Occurrence(BaseModel):
    starts_at: AwareDatetime
    ends_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def ends_after_start(self) -> "Occurrence":
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("ends_at doit être après starts_at")
        return self


class Offer(BaseModel):
    label: str | None = None
    is_free: bool = False
    price_min: Decimal | None = Field(default=None, ge=0)
    price_max: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    price_unit: PriceUnit = PriceUnit.PER_PERSON
    booking_url: HttpUrl | None = None
    online_booking: bool | None = None
    paid_booking: bool | None = None
    affiliate_url: HttpUrl | None = None

    @model_validator(mode="after")
    def consistent_prices(self) -> "Offer":
        if self.price_min is not None and self.price_max is not None and self.price_max < self.price_min:
            raise ValueError("price_max < price_min")
        if self.is_free and (self.price_max or 0) > 0:
            raise ValueError("offre gratuite avec un prix")
        return self


class Activity(BaseModel):
    title: str
    description: str | None = None
    kind: ActivityKind
    starts_on: date | None = None
    ends_on: date | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    website: HttpUrl | None = None
    image: Image | None = None
    is_evening: bool | None = None
    venue: Venue | None = None
    categories: list[str] = Field(default_factory=list)
    occurrences: list[Occurrence] = Field(default_factory=list)
    offers: list[Offer] = Field(default_factory=list)

    @field_validator("categories")
    @classmethod
    def known_categories(cls, value: list[str]) -> list[str]:
        if unknown := set(value) - CATEGORIES.keys():
            raise ValueError(f"catégories inconnues : {sorted(unknown)}")
        return value

    @model_validator(mode="after")
    def consistent_dates(self) -> "Activity":
        if self.starts_on and self.ends_on and self.ends_on < self.starts_on:
            raise ValueError("ends_on < starts_on")
        return self
