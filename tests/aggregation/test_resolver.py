from wuwa_api.aggregation.resolver import merge_records
from wuwa_api.models import EntityRecord

def test_merge_fills_missing_fields():
    a = EntityRecord(id="jiyan", name="Jiyan", entity_type="character", element="Aero")
    b = EntityRecord(id="jiyan", name="Jiyan", entity_type="character", faction="Midnight Rangers")
    result = merge_records([a, b])
    assert result.element == "Aero"
    assert result.faction == "Midnight Rangers"
