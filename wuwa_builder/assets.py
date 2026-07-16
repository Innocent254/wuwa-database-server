from __future__ import annotations

import asyncio
import io
import logging
from pathlib import Path

import aiohttp
from PIL import Image

from wuwa_builder.models import AssetRecord
from wuwa_builder.util import sha256_bytes, stable_id

LOGGER = logging.getLogger(__name__)

MAX_SOURCE_IMAGE_BYTES = 20 * 1024 * 1024
MAX_CONCURRENT_DOWNLOADS = 4


async def build_assets(image_urls: list[str], output_dir: Path) -> list[AssetRecord]:
    output_dir.mkdir(parents=True, exist_ok=True)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
    timeout = aiohttp.ClientTimeout(total=45)
    headers = {"User-Agent": "WuWaCompanionDataBuilder/0.1"}

    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        tasks = [
            _download_convert(session, semaphore, url, output_dir)
            for url in dict.fromkeys(image_urls)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    records: list[AssetRecord] = []
    for result in results:
        if isinstance(result, Exception):
            LOGGER.warning("Asset processing failed: %s", result)
        elif result is not None:
            records.append(result)
    return records


async def _download_convert(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    url: str,
    output_dir: Path,
) -> AssetRecord | None:
    async with semaphore:
        async with session.get(url, allow_redirects=True) as response:
            response.raise_for_status()
            content_length = int(response.headers.get("Content-Length", "0") or "0")
            if content_length > MAX_SOURCE_IMAGE_BYTES:
                raise ValueError(f"Image is too large: {url}")
            data = await response.read()
            if len(data) > MAX_SOURCE_IMAGE_BYTES:
                raise ValueError(f"Image exceeded the maximum size: {url}")

    with Image.open(io.BytesIO(data)) as image:
        image.load()
        if image.width * image.height > 40_000_000:
            raise ValueError(f"Image dimensions are too large: {url}")
        converted = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        converted.thumbnail((2048, 2048), Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        converted.save(buffer, format="WEBP", quality=84, method=6)
        optimized = buffer.getvalue()

        digest = sha256_bytes(optimized)
        relative_path = f"images/{digest[:2]}/{digest}.webp"
        path = output_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(optimized)

        return AssetRecord(
            id=stable_id("asset", url),
            source_url=url,
            relative_path=relative_path,
            sha256=digest,
            size_bytes=len(optimized),
            media_type="image/webp",
            width=converted.width,
            height=converted.height,
        )
