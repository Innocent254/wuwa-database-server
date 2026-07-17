from __future__ import annotations

import logging
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import orjson

from wuwa_builder.assets import build_assets
from wuwa_builder.models import PackageInfo, UpdateManifest
from wuwa_builder.sources.official import OfficialSiteSource
from wuwa_builder.util import sha256_file

LOGGER = logging.getLogger(__name__)

REPOSITORY = "Innocent254/wuwa-database-server"


async def build_release(
    output_dir: Path,
    version: str,
    max_news_items: int,
    include_images: bool,
) -> UpdateManifest:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    source = OfficialSiteSource()
    news = await source.collect_news(max_items=max_news_items)
    if not news:
        raise RuntimeError(
            "Refusing to create a database release because the official source returned zero records."
        )

    image_urls = [str(url) for item in news for url in item.image_urls]
    asset_records = (
        await build_assets(image_urls, output_dir / "assets")
        if include_images and image_urls
        else []
    )

    catalog = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            "kurogames-official": {
                "base_url": "https://wutheringwaves.kurogames.com/en/",
                "trust_tier": "official",
            }
        },
        "news": [item.model_dump(mode="json") for item in news],
        "assets": [item.model_dump(mode="json") for item in asset_records],
        "resonators": [],
        "weapons": [],
        "echoes": [],
        "materials": [],
    }

    catalog_path = output_dir / "catalog.json"
    catalog_path.write_bytes(orjson.dumps(catalog, option=orjson.OPT_INDENT_2))

    database_package = output_dir / "database-full.wupack"
    with zipfile.ZipFile(database_package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(catalog_path, arcname="catalog.json")

    # Keep an artifact file for diagnostics, but never advertise it to clients
    # unless at least one image was downloaded, validated, and optimized.
    assets_package = output_dir / "assets-full.wupack"
    with zipfile.ZipFile(assets_package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        assets_root = output_dir / "assets"
        if assets_root.exists():
            for path in assets_root.rglob("*"):
                if path.is_file():
                    archive.write(path, arcname=path.relative_to(assets_root).as_posix())

    release_base = f"https://github.com/{REPOSITORY}/releases/download/data-v{version}"
    if asset_records:
        assets_info = PackageInfo(
            version=version,
            available=True,
            url=f"{release_base}/assets-full.wupack",
            sha256=sha256_file(assets_package),
            size_bytes=assets_package.stat().st_size,
        )
    else:
        assets_info = PackageInfo(
            version=version,
            available=False,
            url=None,
            sha256=None,
            size_bytes=0,
        )

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
        source_summary={
            "news": len(news),
            "assets": len(asset_records),
            "resonators": 0,
            "weapons": 0,
            "echoes": 0,
            "materials": 0,
        },
    )
    (output_dir / "version.json").write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (output_dir / "CHANGELOG.md").write_text(
        _changelog(version, len(news), len(asset_records)),
        encoding="utf-8",
    )
    return manifest


def _changelog(version: str, news_count: int, asset_count: int) -> str:
    assets_status = (
        f"{asset_count} optimized official-source images"
        if asset_count
        else "No image package published because no images passed validation"
    )
    return (
        f"# WuWa data {version}\n\n"
        f"- Official news/announcement records: {news_count}\n"
        f"- Assets: {assets_status}\n"
        "- Resonator, weapon, Echo, and material datasets remain disabled until "
        "their source adapters and validators are verified.\n"
    )
