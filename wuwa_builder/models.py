from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)


class SourceReference(StrictModel):
    source_id: str
    source_url: HttpUrl
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    trust_tier: Literal["official", "trusted_structured", "community_reviewed"] = "official"


class NewsRecord(StrictModel):
    id: str
    title: str = Field(min_length=1, max_length=300)
    category: Literal["patch_notes", "version_preview", "event", "announcement", "other"]
    published_at: datetime | None = None
    body_text: str = ""
    image_urls: list[HttpUrl] = Field(default_factory=list)
    source: SourceReference


class WikiEntityRecord(StrictModel):
    """Validated text-only record sourced from a structured community wiki API."""

    id: str
    name: str = Field(min_length=1, max_length=300)
    entity_type: Literal["resonator", "weapon", "echo", "material"]
    summary: str = Field(default="", max_length=4000)
    categories: list[str] = Field(default_factory=list)
    revision_id: int | None = Field(default=None, ge=1)
    revision_timestamp: datetime | None = None
    license_name: Literal["CC-BY-SA-3.0"] = "CC-BY-SA-3.0"
    license_url: HttpUrl = "https://creativecommons.org/licenses/by-sa/3.0/"
    attribution_url: HttpUrl
    source: SourceReference


class AssetRecord(StrictModel):
    id: str
    source_url: HttpUrl
    relative_path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(ge=0)
    media_type: Literal["image/webp"]
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class PackageInfo(StrictModel):
    version: str
    available: bool = True
    url: HttpUrl | None = None
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(default=0, ge=0)


class UpdateManifest(StrictModel):
    manifest_version: int = 1
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    game_patch: str | None = None
    database: PackageInfo
    assets: PackageInfo
    changelog_url: HttpUrl | None = None
    minimum_app_version_code: int = Field(default=1, ge=1)
    source_summary: dict[str, int] = Field(default_factory=dict)
