from wuwa_api.aggregation.resolver import merge_records
from wuwa_api.cache.sqlite import SQLiteCache
from wuwa_api.config import settings
from wuwa_api.models import EntityPage, EntityRecord
from wuwa_api.sources.fandom import FandomSource

class DataService:
    def __init__(self):
        self.cache = SQLiteCache(settings.cache_path, settings.cache_ttl_seconds)
        # Add future adapters here. They should be ordered/weighted by the resolver.
        self.sources = [FandomSource()]

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
        for source in self.sources:
            results.extend(await source.search(query, entity_type))
            if len(results) >= limit:
                break
        return results[:limit]

    async def list_entities(self, entity_type, element, faction, rarity,
                            weapon_type, release_version, limit, offset):
        # Phase 1 intentionally exposes the filter contract. Full indexed listing
        # is added when the persistent catalog/index is connected.
        results = []
        return EntityPage(items=results[offset:offset+limit],
                          total=len(results), limit=limit, offset=offset)
