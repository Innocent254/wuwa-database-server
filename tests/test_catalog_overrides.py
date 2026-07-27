from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from wuwa_builder.catalog_overrides import (
    CatalogOverride,
    CatalogOverrideFile,
    apply_catalog_overrides,
    load_catalog_overrides,
)
from wuwa_builder.models import SourceReference, WikiEntityRecord


def incomplete_abyss_surges() -> WikiEntityRecord:
    url = "https://wutheringwaves.fandom.com/wiki/Abyss_Surges"
    return WikiEntityRecord(
        id="weapon-abyss-surges",
        name="Abyss Surges",
        entity_type="weapon",
        summary="Abyss Surges is a 5-star Gauntlets weapon.",
        rarity=5,
        weapon_type="Gauntlets",
        release_version="1.0",
        acquisition_sources=["Weapons with Convene"],
        availability="unknown",
        revision_id=97014,
        revision_timestamp=datetime(2026, 6, 3, tzinfo=timezone.utc),
        attribution_url=url,
        source=SourceReference(
            source_id="wuthering-waves-fandom-mediawiki",
            source_url=url,
            trust_tier="community_reviewed",
        ),
    )


def test_abyss_surges_override_is_complete_and_preserves_attribution() -> None:
    original = incomplete_abyss_surges()
    result = apply_catalog_overrides(
        {
            "resonators": [],
            "weapons": [original],
            "echoes": [],
            "materials": [],
        }
    )
    weapon = result["weapons"][0]

    assert weapon.id == original.id
    assert weapon.revision_id == original.revision_id
    assert weapon.source == original.source
    assert weapon.summary.startswith("Abyss Surges is a 5-star")
    assert weapon.release_date == "May 23, 2024"
    assert weapon.availability == "permanent"
    assert weapon.is_obtainable is True
    assert weapon.acquisition_sources == [
        "Standard Weapon Convene",
        "Winter Brume Weapon Supply Chest",
    ]
    assert weapon.level_1_stats == {"Base ATK": "47", "ATK": "8.1%"}
    assert weapon.max_level == 90
    assert weapon.max_level_stats == {"Base ATK": "587", "ATK": "36.4%"}
    assert weapon.passive_name == "Stormy Resolution"
    assert "Energy Regen" in weapon.passive_description


def test_override_file_contains_verification_sources() -> None:
    overrides = load_catalog_overrides()
    abyss = next(item for item in overrides.records if item.name == "Abyss Surges")

    assert len(abyss.verification_urls) == 2
    assert all(str(url).startswith("https://") for url in abyss.verification_urls)


def test_invalid_override_value_is_rejected() -> None:
    override = CatalogOverride(
        entity_type="weapon",
        name="Abyss Surges",
        verification_urls=["https://wutheringwaves.fandom.com/wiki/Abyss_Surges"],
        required_fields=["rarity"],
        fields={"rarity": 6},
    )
    with pytest.raises(ValidationError):
        apply_catalog_overrides(
            {"weapons": [incomplete_abyss_surges()]},
            CatalogOverrideFile(version=1, records=[override]),
        )
