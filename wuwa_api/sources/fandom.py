from __future__ import annotations

from datetime import date, datetime
from wuwa_builder.sources.fandom import FandomMediaWikiSource
from wuwa_builder.models import WikiEntityRecord
from wuwa_api.aggregation.normalizer import normalize_id, utc_now
from wuwa_api.models import EntityRecord, Provenance
from wuwa_api.sources.base import SourceAdapter

TYPE_MAP = {"character": "resonators", "weapon": "weapons", "echo": "echoes", "material": "materials"}

def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            pass
    return None

def _convert(record: WikiEntityRecord) -> EntityRecord:
    api_type = "character" if record.entity_type == "resonator" else record.entity_type
    now = record.source.retrieved_at or utc_now()
    return EntityRecord(
        id=normalize_id(record.name),
        name=record.name,
        entity_type=api_type,
        description=record.summary or None,
        rarity=record.rarity,
        element=record.element,
        faction=record.faction,
        weapon_type=record.weapon_type,
        release_version=record.release_version,
        release_date=_parse_date(record.release_date),
        obtainable=record.is_obtainable,
        stats={
            "level_1": record.level_1_stats,
            "max_level": record.max_level_stats,
            "max_level_cap": record.max_level,
        },
        skills=[],
        materials=[],
        images={},
        extra={
            "categories": record.categories,
            "echo_class": record.echo_class,
            "region": record.region,
            "material_type": record.material_type,
            "acquisition_sources": record.acquisition_sources,
            "availability": record.availability,
            "combat_roles": record.combat_roles,
            "associated_resonator": record.associated_resonator,
            "passive_name": record.passive_name,
            "passive_description": record.passive_description,
            "revision_id": record.revision_id,
            "revision_timestamp": record.revision_timestamp,
            "source_url": str(record.attribution_url),
        },
        provenance={"record": Provenance(source=record.source.source_id, retrieved_at=now, confidence=0.80)},
        retrieved_at=now,
    )

class FandomSource(SourceAdapter):
    """Adapter over the existing permitted MediaWiki collector."""
    name = "fandom"
    priority = 100

    def __init__(self, max_items_per_dataset: int = 500):
        self.collector = FandomMediaWikiSource()
        self.max_items_per_dataset = max_items_per_dataset

    async def _records(self) -> list[EntityRecord]:
        datasets = await self.collector.collect_catalog(self.max_items_per_dataset)
        return [_convert(item) for values in datasets.values() for item in values]

    async def get_entity(self, entity_type: str, entity_id: str) -> EntityRecord | None:
        if entity_type not in TYPE_MAP:
            return None
        wanted = normalize_id(entity_id)
        for record in await self._records():
            if record.entity_type == entity_type and record.id == wanted:
                return record
        return None

    async def search(self, query: str, entity_type: str | None = None) -> list[EntityRecord]:
        records = await self._records()
        if entity_type:
            records = [r for r in records if r.entity_type == entity_type]
        if not query:
            return records
        q = query.casefold()
        return [r for r in records if q in r.name.casefold() or q in (r.description or "").casefold()
                or q in (r.faction or "").casefold() or q in (r.element or "").casefold()
                or q in (r.weapon_type or "").casefold()]
