import pytest
from wuwa_api.models import EntityRecord
from wuwa_api.service import DataService

class FakeCache:
    def __init__(self, records): self.records = records
    def list(self, entity_type): return [r for r in self.records if r.entity_type == entity_type]

@pytest.mark.asyncio
async def test_list_entities_filters_cached_records():
    service = DataService()
    service.cache = FakeCache([
        EntityRecord(id="jiyan",name="Jiyan",entity_type="character",element="Aero",faction="Midnight Rangers",rarity=5,weapon_type="Broadblade"),
        EntityRecord(id="verina",name="Verina",entity_type="character",element="Spectro",faction="Jinzhou",rarity=5,weapon_type="Rectifier"),
    ])
    result = await service.list_entities("character","Aero",None,5,None,None,50,0)
    assert result.total == 1
    assert result.items[0].name == "Jiyan"

@pytest.mark.asyncio
async def test_search_cached_records():
    service = DataService()
    service.cache = FakeCache([
        EntityRecord(id="jiyan",name="Jiyan",entity_type="character"),
        EntityRecord(id="verina",name="Verina",entity_type="character"),
    ])
    result = await service.search("jiy","character",25)
    assert len(result) == 1
    assert result[0].name == "Jiyan"
