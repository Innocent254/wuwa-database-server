from __future__ import annotations
from wuwa_api.aggregation.resolver import merge_records
from wuwa_api.cache.sqlite import SQLiteCache
from wuwa_api.config import settings
from wuwa_api.models import EntityPage, EntityRecord
from wuwa_api.sources.fandom import FandomSource

class DataService:
    def __init__(self):
        self.cache = SQLiteCache(settings.cache_path, settings.cache_ttl_seconds)
        self.sources = [FandomSource()]

    async def _refresh_type(self, entity_type: str) -> list[EntityRecord]:
        results = []
        for source in self.sources:
            results.extend(await source.search("", entity_type))
        if results:
            self.cache.put_many(results)
        return results

    async def get(self, entity_type: str, entity_id: str) -> EntityRecord | None:
        cached = self.cache.get(entity_type, entity_id)
        if cached:
            return cached
        records = []
        for source in self.sources:
            record = await source.get_entity(entity_type, entity_id)
            if record:
                records.append(record)
        merged = merge_records(records)
        if merged:
            self.cache.put(merged)
        return merged

    async def search(self, query: str, entity_type: str | None, limit: int):
        results = []
        types = [entity_type] if entity_type else ["character","weapon","echo","material"]
        for kind in types:
            records = self.cache.list(kind) or await self._refresh_type(kind)
            results.extend(self._match(records, query))
        return results[:limit]

    async def list_entities(self, entity_type, element, faction, rarity, weapon_type,
                            release_version, limit, offset):
        records = self.cache.list(entity_type) or await self._refresh_type(entity_type)
        filtered = []
        for r in records:
            if element and r.element != element: continue
            if faction and r.faction != faction: continue
            if rarity is not None and r.rarity != rarity: continue
            if weapon_type and r.weapon_type != weapon_type: continue
            if release_version and r.release_version != release_version: continue
            filtered.append(r)
        filtered.sort(key=lambda r: r.name.casefold())
        return EntityPage(items=filtered[offset:offset+limit], total=len(filtered),
                          limit=limit, offset=offset)

    @staticmethod
    def _match(records, query):
        if not query: return records
        q = query.casefold()
        return [r for r in records if q in r.name.casefold() or q in (r.description or "").casefold()
                or q in (r.faction or "").casefold() or q in (r.element or "").casefold()
                or q in (r.weapon_type or "").casefold()]
