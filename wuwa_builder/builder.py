from __future__ import annotations

import logging
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import orjson

from wuwa_builder.models import PackageInfo, UpdateManifest
from wuwa_builder.sources.fandom import FandomMediaWikiSource
from wuwa_builder.util import sha256_file

LOGGER = logging.getLogger(__name__)

REPOSITORY = "Innocent254/wuwa-database-server"
FANDOM_LICENSE_URL = "https://creativecommons.org/licenses/by-sa/3.0/"
FANDOM_WIKI_URL = "https://wutheringwaves.fandom.com/"


async def build_release(
    output_dir: Path,
    version: str,
    max_items_per_dataset: int,
    include_images: bool,
) -> UpdateManifest:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    source = FandomMediaWikiSource()
    datasets = await source.collect_catalog(max_items_per_dataset=max_items_per_dataset)
    resonators = datasets.get("resonators", [])
    weapons = datasets.get("weapons", [])
    echoes = datasets.get("echoes", [])
    materials = datasets.get("materials", [])

    total_records = sum(map(len, (resonators, weapons, echoes, materials)))
    if total_records == 0:
        raise RuntimeError(
            "Refusing to create a database release because all sources returned zero records."
        )

    # Community wiki text is reusable with attribution under CC-BY-SA. Images are
    # intentionally excluded because Fandom file licenses vary page by page.
    if include_images:
        LOGGER.info(
            "Image collection requested, but community-wiki images remain disabled until "
            "per-file license validation is implemented."
        )
    asset_records: list[object] = []

    generated_at = datetime.now(timezone.utc).isoformat()
    catalog = {
        "schema_version": 2,
        "generated_at": generated_at,
        "data_license": {
            "name": "CC-BY-SA-3.0",
            "url": FANDOM_LICENSE_URL,
            "attribution": FANDOM_WIKI_URL,
            "note": (
                "Community-derived summaries and metadata retain source URLs and revision IDs. "
                "Project code remains separately licensed under MIT."
            ),
        },
        "sources": {
            "kurogames-official": {
                "base_url": "https://wutheringwaves.kurogames.com/en/",
                "trust_tier": "official",
                "status": "preferred-but-temporarily-disabled-for-automated-discovery",
            },
            "wuthering-waves-fandom-mediawiki": {
                "base_url": FANDOM_WIKI_URL,
                "api_url": "https://wutheringwaves.fandom.com/api.php",
                "trust_tier": "community_reviewed",
                "license": "CC-BY-SA-3.0",
                "license_url": FANDOM_LICENSE_URL,
            },
        },
        "news": [],
        "assets": [],
        "resonators": [item.model_dump(mode="json") for item in resonators],
        "weapons": [item.model_dump(mode="json") for item in weapons],
        "echoes": [item.model_dump(mode="json") for item in echoes],
        "materials": [item.model_dump(mode="json") for item in materials],
    }

    catalog_path = output_dir / "catalog.json"
    catalog_path.write_bytes(orjson.dumps(catalog, option=orjson.OPT_INDENT_2))

    attribution_path = output_dir / "ATTRIBUTION.md"
    attribution_path.write_text(_attribution(), encoding="utf-8")
    data_license_path = output_dir / "DATA_LICENSE.md"
    data_license_path.write_text(_data_license(), encoding="utf-8")

    database_package = output_dir / "database-full.wupack"
    with zipfile.ZipFile(database_package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(catalog_path, arcname="catalog.json")
        archive.write(attribution_path, arcname="ATTRIBUTION.md")
        archive.write(data_license_path, arcname="DATA_LICENSE.md")

    # Keep the expected artifact filename for workflow compatibility, but do not
    # advertise it to Android clients while no license-cleared images exist.
    assets_package = output_dir / "assets-full.wupack"
    with zipfile.ZipFile(assets_package, "w", compression=zipfile.ZIP_DEFLATED):
        pass

    release_base = f"https://github.com/{REPOSITORY}/releases/download/data-v{version}"
    assets_info = PackageInfo(
        version=version,
        available=False,
        url=None,
        sha256=None,
        size_bytes=0,
    )

    source_summary = {
        "news": 0,
        "assets": len(asset_records),
        "resonators": len(resonators),
        "weapons": len(weapons),
        "echoes": len(echoes),
        "materials": len(materials),
    }
    manifest = UpdateManifest(
        database=PackageInfo(
            version=version,
            available=True,
            url=f"{release_base}/database-full.wupack",
            sha256=sha256_file(database_package),
            size_bytes=database_package.stat().st_size,
        ),
        assets=assets_info,
        changelog_url=f"https://github.com/{REPOSITORY}/releases/tag/data-v{version}",
        source_summary=source_summary,
    )
    (output_dir / "version.json").write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (output_dir / "CHANGELOG.md").write_text(
        _changelog(version, source_summary),
        encoding="utf-8",
    )
    return manifest


def _changelog(version: str, counts: dict[str, int]) -> str:
    return (
        f"# WuWa data {version}\n\n"
        "- Source: Wuthering Waves Wiki through Fandom's public MediaWiki API.\n"
        f"- Resonators: {counts['resonators']}\n"
        f"- Weapons: {counts['weapons']}\n"
        f"- Echoes: {counts['echoes']}\n"
        f"- Materials: {counts['materials']}\n"
        "- Official Kuro news discovery is temporarily disabled because the current site "
        "does not expose stable listing routes to GitHub Actions.\n"
        "- No image package is published; community-wiki media requires per-file license review.\n"
    )


def _attribution() -> str:
    return (
        "# Attribution\n\n"
        "Text summaries and page metadata in this package are derived from the "
        "Wuthering Waves Wiki on Fandom. Each catalog record includes its original "
        "page URL and revision metadata.\n\n"
        f"Source: {FANDOM_WIKI_URL}\n\n"
        f"License: CC BY-SA 3.0 — {FANDOM_LICENSE_URL}\n"
    )


def _data_license() -> str:
    return (
        "# Data license\n\n"
        "Community-derived text and metadata in catalog.json are distributed under "
        "Creative Commons Attribution-ShareAlike 3.0 Unported. Attribution is retained "
        "through source and attribution URLs on every record.\n\n"
        "The Python source code in this repository remains licensed separately under MIT.\n"
    )
