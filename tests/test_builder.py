import json
import zipfile
from datetime import datetime, timezone

import pytest

from wuwa_builder.builder import build_release
from wuwa_builder.models import AssetRecord, SourceReference, WikiEntityRecord
from wuwa_builder.sources.fandom import FandomMediaWikiSource
from wuwa_builder.util import sha256_bytes


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


def sample_catalog() -> dict[str, list[WikiEntityRecord]]:
    return {
        "resonators": [sample_record("resonator", "Jiyan")],
        "weapons": [sample_record("weapon", "Verdant Summit")],
        "echoes": [sample_record("echo", "Crownless")],
        "materials": [sample_record("material", "Pecok Flower")],
    }


@pytest.mark.asyncio
async def test_empty_all_sources_fails(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    async def empty_catalog(self, max_items_per_dataset: int = 250):
        return {"resonators": [], "weapons": [], "echoes": [], "materials": []}

    monkeypatch.setattr(FandomMediaWikiSource, "collect_catalog", empty_catalog)
    with pytest.raises(RuntimeError, match="zero records"):
        await build_release(tmp_path / "release", "0.3.0", 250, False)


@pytest.mark.asyncio
async def test_structured_data_builds_without_assets_when_images_disabled(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    async def catalog(self, max_items_per_dataset: int = 250):
        return sample_catalog()

    monkeypatch.setattr(FandomMediaWikiSource, "collect_catalog", catalog)
    release = tmp_path / "release"
    manifest = await build_release(release, "0.3.0", 250, False)

    assert manifest.database.available is True
    assert manifest.assets.available is False
    assert manifest.source_summary["assets"] == 0

    catalog_data = json.loads((release / "catalog.json").read_text())
    assert catalog_data["schema_version"] == 5
    assert "image_path" not in catalog_data["resonators"][0]

    with zipfile.ZipFile(release / "database-full.wupack") as archive:
        assert set(archive.namelist()) == {
            "catalog.json",
            "ATTRIBUTION.md",
            "DATA_LICENSE.md",
            "LEGAL_NOTICE.txt",
        }


@pytest.mark.asyncio
async def test_license_verified_images_are_packaged_and_linked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    data = b"fake-webp"
    digest = sha256_bytes(data)

    async def catalog(self, max_items_per_dataset: int = 250):
        return sample_catalog()

    async def assets(self, records, output_dir, max_images=500):
        relative_path = f"images/{digest[:2]}/{digest}.webp"
        target = output_dir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return [
            AssetRecord(
                id="asset-jiyan",
                entity_id="resonator_jiyan",
                file_title="File:Jiyan.png",
                source_url="https://static.wikia.nocookie.net/wutheringwaves/jiyan.png",
                attribution_url="https://wutheringwaves.fandom.com/wiki/File:Jiyan.png",
                license_name="CC-BY-SA-4.0",
                license_url="https://creativecommons.org/licenses/by-sa/4.0/",
                author="Example author",
                credit="Example credit",
                relative_path=relative_path,
                sha256=digest,
                size_bytes=len(data),
                media_type="image/webp",
                width=64,
                height=64,
            )
        ]

    monkeypatch.setattr(FandomMediaWikiSource, "collect_catalog", catalog)
    monkeypatch.setattr(FandomMediaWikiSource, "collect_licensed_assets", assets)

    release = tmp_path / "release"
    manifest = await build_release(release, "0.3.0", 250, True)

    assert manifest.assets.available is True
    assert manifest.source_summary["assets"] == 1
    catalog_data = json.loads((release / "catalog.json").read_text())
    assert catalog_data["resonators"][0]["image_path"].endswith(".webp")
    assert catalog_data["assets"][0]["entity_id"] == "resonator_jiyan"

    with zipfile.ZipFile(release / "assets-full.wupack") as archive:
        names = set(archive.namelist())
        assert "IMAGE_ATTRIBUTION.json" in names
        assert "LEGAL_NOTICE.txt" in names
        assert any(name.startswith("images/") and name.endswith(".webp") for name in names)
