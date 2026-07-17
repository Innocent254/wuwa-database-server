import json
import zipfile
from datetime import datetime, timezone

import pytest

from wuwa_builder.builder import build_release
from wuwa_builder.models import SourceReference, WikiEntityRecord
from wuwa_builder.sources.fandom import FandomMediaWikiSource


def sample_record(entity_type: str, name: str) -> WikiEntityRecord:
    url = f"https://wutheringwaves.fandom.com/wiki/{name.replace(' ', '_')}"
    return WikiEntityRecord(
        id=f"{entity_type}_{name.lower().replace(' ', '_')}",
        name=name,
        entity_type=entity_type,
        summary=f"{name} test summary.",
        revision_id=1,
        revision_timestamp=datetime(2026, 7, 17, tzinfo=timezone.utc),
        attribution_url=url,
        source=SourceReference(
            source_id="wuthering-waves-fandom-mediawiki",
            source_url=url,
            trust_tier="community_reviewed",
        ),
    )


@pytest.mark.asyncio
async def test_empty_all_sources_fails(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    async def empty_catalog(self, max_items_per_dataset: int = 250):
        return {"resonators": [], "weapons": [], "echoes": [], "materials": []}

    monkeypatch.setattr(FandomMediaWikiSource, "collect_catalog", empty_catalog)
    with pytest.raises(RuntimeError, match="zero records"):
        await build_release(tmp_path / "release", "0.2.0", 250, False)


@pytest.mark.asyncio
async def test_structured_community_data_builds_attributed_package(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    async def catalog(self, max_items_per_dataset: int = 250):
        return {
            "resonators": [sample_record("resonator", "Jiyan")],
            "weapons": [sample_record("weapon", "Verdant Summit")],
            "echoes": [sample_record("echo", "Crownless")],
            "materials": [sample_record("material", "Pecok Flower")],
        }

    monkeypatch.setattr(FandomMediaWikiSource, "collect_catalog", catalog)
    release = tmp_path / "release"
    manifest = await build_release(release, "0.2.0", 250, True)

    assert manifest.database.available is True
    assert manifest.assets.available is False
    assert manifest.source_summary["resonators"] == 1
    assert manifest.source_summary["weapons"] == 1
    assert manifest.source_summary["echoes"] == 1
    assert manifest.source_summary["materials"] == 1

    catalog_data = json.loads((release / "catalog.json").read_text())
    assert catalog_data["schema_version"] == 2
    assert catalog_data["resonators"][0]["license_name"] == "CC-BY-SA-3.0"

    with zipfile.ZipFile(release / "database-full.wupack") as archive:
        assert set(archive.namelist()) == {"catalog.json", "ATTRIBUTION.md", "DATA_LICENSE.md"}
