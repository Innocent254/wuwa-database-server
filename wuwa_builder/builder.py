from __future__ import annotations

import logging
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import orjson

from wuwa_builder.models import AssetRecord, PackageInfo, UpdateManifest, WikiEntityRecord
from wuwa_builder.sources.fandom import FandomMediaWikiSource, WIKI_HOME_URL
from wuwa_builder.util import sha256_file

LOGGER = logging.getLogger(__name__)

REPOSITORY = "Innocent254/wuwa-database-server"
FANDOM_LICENSE_URL = "https://creativecommons.org/licenses/by-sa/3.0/"
FANDOM_WIKI_URL = WIKI_HOME_URL


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

    all_records = [*resonators, *weapons, *echoes, *materials]
    if not all_records:
        raise RuntimeError(
            "Refusing to create a database release because all sources returned zero records."
        )

    asset_records: list[AssetRecord] = []
    assets_content_dir = output_dir / "assets-content"
    if include_images:
        asset_records = await source.collect_licensed_assets(
            records=all_records,
            output_dir=assets_content_dir,
            max_images=min(len(all_records), 500),
        )
        if not asset_records:
            LOGGER.warning(
                "Image collection was enabled, but no representative images had an explicit "
                "reusable file license. The data release will remain valid without an asset update."
            )
    else:
        LOGGER.info("Image collection disabled by workflow input.")

    image_path_by_entity = {
        asset.entity_id: asset.relative_path
        for asset in asset_records
    }
    resonators = _attach_image_paths(resonators, image_path_by_entity)
    weapons = _attach_image_paths(weapons, image_path_by_entity)
    echoes = _attach_image_paths(echoes, image_path_by_entity)
    materials = _attach_image_paths(materials, image_path_by_entity)

    generated_at = datetime.now(timezone.utc).isoformat()
    catalog = {
        "schema_version": 4,
        "generated_at": generated_at,
        "data_license": {
            "name": "CC-BY-SA-3.0",
            "url": FANDOM_LICENSE_URL,
            "attribution": FANDOM_WIKI_URL,
            "note": (
                "Community-derived text retains source URLs and revision IDs. "
                "Images, when present, are independently license-filtered and carry per-file "
                "attribution records. Project code remains separately licensed under MIT."
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
                "text_license": "CC-BY-SA-3.0",
                "text_license_url": FANDOM_LICENSE_URL,
                "image_policy": "explicit-reusable-license-only",
            },
        },
        "news": [],
        "assets": [item.model_dump(mode="json") for item in asset_records],
        "resonators": [item.model_dump(mode="json", exclude_none=True) for item in resonators],
        "weapons": [item.model_dump(mode="json", exclude_none=True) for item in weapons],
        "echoes": [item.model_dump(mode="json", exclude_none=True) for item in echoes],
        "materials": [item.model_dump(mode="json", exclude_none=True) for item in materials],
    }

    catalog_path = output_dir / "catalog.json"
    catalog_path.write_bytes(orjson.dumps(catalog, option=orjson.OPT_INDENT_2))

    attribution_path = output_dir / "ATTRIBUTION.md"
    attribution_path.write_text(_attribution(), encoding="utf-8")
    data_license_path = output_dir / "DATA_LICENSE.md"
    data_license_path.write_text(_data_license(), encoding="utf-8")
    legal_notice_path = output_dir / "LEGAL_NOTICE.txt"
    legal_notice_path.write_text(_legal_notice(), encoding="utf-8")

    database_package = output_dir / "database-full.wupack"
    with zipfile.ZipFile(database_package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(catalog_path, arcname="catalog.json")
        archive.write(attribution_path, arcname="ATTRIBUTION.md")
        archive.write(data_license_path, arcname="DATA_LICENSE.md")
        archive.write(legal_notice_path, arcname="LEGAL_NOTICE.txt")

    assets_package = output_dir / "assets-full.wupack"
    if asset_records:
        image_attribution_path = output_dir / "IMAGE_ATTRIBUTION.json"
        image_attribution_path.write_bytes(
            orjson.dumps(
                [item.model_dump(mode="json") for item in asset_records],
                option=orjson.OPT_INDENT_2,
            )
        )
        with zipfile.ZipFile(assets_package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for asset_path in sorted(assets_content_dir.rglob("*")):
                if asset_path.is_file():
                    archive.write(asset_path, arcname=asset_path.relative_to(assets_content_dir))
            archive.write(image_attribution_path, arcname="IMAGE_ATTRIBUTION.json")
            archive.write(legal_notice_path, arcname="LEGAL_NOTICE.txt")
    else:
        with zipfile.ZipFile(assets_package, "w", compression=zipfile.ZIP_DEFLATED):
            pass

    release_base = f"https://github.com/{REPOSITORY}/releases/download/data-v{version}"
    assets_info = (
        PackageInfo(
            version=version,
            available=True,
            url=f"{release_base}/assets-full.wupack",
            sha256=sha256_file(assets_package),
            size_bytes=assets_package.stat().st_size,
        )
        if asset_records
        else PackageInfo(
            version=version,
            available=False,
            url=None,
            sha256=None,
            size_bytes=0,
        )
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
        _changelog(version, source_summary, include_images),
        encoding="utf-8",
    )
    return manifest


def _attach_image_paths(
    records: list[WikiEntityRecord],
    image_path_by_entity: dict[str, str],
) -> list[WikiEntityRecord]:
    return [
        record.model_copy(update={"image_path": image_path_by_entity.get(record.id)})
        for record in records
    ]


def _changelog(version: str, counts: dict[str, int], include_images: bool) -> str:
    image_line = (
        f"- License-verified images packaged: {counts['assets']}\n"
        if include_images
        else "- Image collection was disabled for this run.\n"
    )
    return (
        f"# WuWa data {version}\n\n"
        f"- Source: {FANDOM_WIKI_URL} through Fandom's public MediaWiki API.\n"
        f"- Resonators: {counts['resonators']}\n"
        f"- Weapons: {counts['weapons']}\n"
        f"- Echoes: {counts['echoes']}\n"
        f"- Materials: {counts['materials']}\n"
        f"{image_line}"
        "- Fair-use, unknown-license, non-commercial, and no-derivatives images are excluded.\n"
        "- Official Kuro news discovery remains temporarily disabled because the current site "
        "does not expose stable listing routes to GitHub Actions.\n"
    )


def _attribution() -> str:
    return (
        "# Attribution\n\n"
        "Text summaries and page metadata in this package are derived from the "
        "Wuthering Waves Wiki on Fandom. Each catalog record includes its original "
        "page URL and revision metadata.\n\n"
        f"Source: {FANDOM_WIKI_URL}\n\n"
        f"Text license: CC BY-SA 3.0 — {FANDOM_LICENSE_URL}\n\n"
        "When an image package is available, per-file credits and image-license URLs are "
        "stored in IMAGE_ATTRIBUTION.json inside assets-full.wupack.\n"
    )


def _data_license() -> str:
    return (
        "# Data license\n\n"
        "Community-derived text and metadata in catalog.json are distributed under "
        "Creative Commons Attribution-ShareAlike 3.0 Unported. Attribution is retained "
        "through source and attribution URLs on every record.\n\n"
        "Images are not covered by this blanket text license. Only files whose own Fandom "
        "metadata declares a supported reusable license are packaged, and their individual "
        "license and attribution details remain attached.\n\n"
        "The Python source code in this repository remains licensed separately under MIT.\n"
    )


def _legal_notice() -> str:
    return (
        "This application and database are unofficial fan-made resources and are not "
        "affiliated with or endorsed by Kuro Games. Wuthering Waves, its names, characters, "
        "artwork, and other original game content remain the property of their respective "
        "rights holders.\n\n"
        "Community-wiki text is attributed under its stated CC BY-SA terms. Any packaged "
        "image was included only when the image's own file metadata declared a reusable "
        "license; see IMAGE_ATTRIBUTION.json for file-by-file source and license details. "
        "Removing embedded EXIF metadata does not remove attribution or license obligations.\n"
    )
