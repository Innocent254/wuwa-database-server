from datetime import date, datetime
from typing import Any, Literal
from pydantic import BaseModel, Field

EntityType = Literal["character", "weapon", "echo", "material", "patch", "banner"]

class Provenance(BaseModel):
    source: str
    retrieved_at: datetime
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

class EntityRecord(BaseModel):
    id: str
    name: str
    entity_type: EntityType
    description: str | None = None
    rarity: int | None = Field(default=None, ge=1, le=5)
    element: str | None = None
    faction: str | None = None
    weapon_type: str | None = None
    release_version: str | None = None
    release_date: date | None = None
    obtainable: bool | None = None
    stats: dict[str, Any] = Field(default_factory=dict)
    skills: list[dict[str, Any]] = Field(default_factory=list)
    materials: list[dict[str, Any]] = Field(default_factory=list)
    images: dict[str, str] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Provenance] = Field(default_factory=dict)
    retrieved_at: datetime | None = None

class EntityPage(BaseModel):
    items: list[EntityRecord]
    total: int
    limit: int
    offset: int
