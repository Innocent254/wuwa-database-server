from __future__ import annotations

import asyncio
import io
import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
from PIL import Image, ImageOps

from wuwa_builder.models import AssetRecord, LicensedImageCandidate
from wuwa_builder.util import sha256_bytes, stable_id

LOGGER = logging.getLogger(__name__)

MAX_SOURCE_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MAX_CONCURRENT_DOWNLOADS = 2
DOWNLOAD_START_INTERVAL_SECONDS = 0.5
MAX_DOWNLOAD_RETRIES = 3
ALLOWED_IMAGE_HOST_SUFFIXES = (
    ".wikia.nocookie.net",
    ".fandom.com",
    ".wikia.com",
)


@dataclass(frozen=True)
class ProcessedImage:
    relative_path: str
    sha256: str
    size_bytes: int
    width: int
    height: int


class RequestPacer:
    def __init__(self, interval_seconds: float) -> None:
        self._interval_seconds = interval_seconds
        self._lock = asyncio.Lock()
        self._last_started_at = 0.0

    async def wait(self) -> None:
        async with self._lock:
            loop = asyncio.get_running_loop()
            elapsed = loop.time() - self._last_started_at
            if elapsed < self._interval_seconds:
                await asyncio.sleep(self._interval_seconds - elapsed)
            self._last_started_at = loop.time()


def image_url_is_allowed(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    return parsed.scheme == "https" and any(
        host == suffix.removeprefix(".") or host.endswith(suffix)
        for suffix in ALLOWED_IMAGE_HOST_SUFFIXES
    )


def optimize_image_bytes(data: bytes) -> tuple[bytes, int, int]:
    """Strip embedded metadata and convert an image to a bounded WebP file."""

    with Image.open(io.BytesIO(data)) as opened:
        opened.load()
        if opened.width * opened.height > MAX_IMAGE_PIXELS:
            raise ValueError("Image dimensions exceed the configured safety limit.")

        try:
            transposed = ImageOps.exif_transpose(opened)
        except (SyntaxError, ValueError, OSError):
            # Corrupt EXIF must not block pixel extraction; saving a fresh WebP below
            # drops all source metadata regardless.
            transposed = opened.copy()
        has_alpha = "A" in transposed.getbands() or "transparency" in transposed.info
        converted = transposed.convert("RGBA" if has_alpha else "RGB")
        converted.thumbnail((2048, 2048), Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        converted.save(
            buffer,
            format="WEBP",
            quality=86,
            method=6,
            exact=has_alpha,
        )
        return buffer.getvalue(), converted.width, converted.height


async def build_assets(
    candidates: list[LicensedImageCandidate],
    output_dir: Path,
) -> list[AssetRecord]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if not candidates:
        return []

    by_url: dict[str, list[LicensedImageCandidate]] = defaultdict(list)
    for candidate in candidates:
        url = str(candidate.source_url)
        if not image_url_is_allowed(url):
            LOGGER.warning("Skipping image from an unapproved host: %s", url)
            continue
        by_url[url].append(candidate)

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
    pacer = RequestPacer(DOWNLOAD_START_INTERVAL_SECONDS)
    timeout = aiohttp.ClientTimeout(total=60)
    headers = {
        "User-Agent": (
            "WuWaCompanionDataBuilder/0.3 "
            "(+https://github.com/Innocent254/wuwa-database-server; contact via GitHub issues)"
        ),
        "Accept": "image/avif,image/webp,image/png,image/jpeg,*/*;q=0.5",
    }

    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        tasks = {
            url: asyncio.create_task(
                _download_convert(session, semaphore, pacer, url, output_dir)
            )
            for url in by_url
        }
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    records: list[AssetRecord] = []
    for url, result in zip(tasks, results, strict=True):
        if isinstance(result, Exception):
            LOGGER.warning("Asset processing failed for %s: %s", url, result)
            continue

        for candidate in by_url[url]:
            records.append(
                AssetRecord(
                    id=stable_id("asset", f"{candidate.entity_id}:{candidate.file_title}"),
                    entity_id=candidate.entity_id,
                    file_title=candidate.file_title,
                    source_url=candidate.source_url,
                    attribution_url=candidate.attribution_url,
                    license_name=candidate.license_name,
                    license_url=candidate.license_url,
                    author=candidate.author,
                    credit=candidate.credit,
                    relative_path=result.relative_path,
                    sha256=result.sha256,
                    size_bytes=result.size_bytes,
                    media_type="image/webp",
                    width=result.width,
                    height=result.height,
                )
            )

    records.sort(key=lambda item: (item.entity_id, item.file_title.casefold()))
    return records


async def _download_convert(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    pacer: RequestPacer,
    url: str,
    output_dir: Path,
) -> ProcessedImage:
    async with semaphore:
        data: bytes | None = None
        for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
            await pacer.wait()
            try:
                async with session.get(url, allow_redirects=True) as response:
                    if response.status in {429, 500, 502, 503, 504}:
                        retry_after = response.headers.get("Retry-After")
                        delay = (
                            float(retry_after)
                            if retry_after and retry_after.isdigit()
                            else 2.0 * attempt
                        )
                        if attempt == MAX_DOWNLOAD_RETRIES:
                            response.raise_for_status()
                        await asyncio.sleep(min(delay, 30.0))
                        continue

                    response.raise_for_status()
                    content_type = response.headers.get("Content-Type", "").casefold()
                    if content_type and not content_type.startswith("image/"):
                        raise ValueError(f"Unexpected image content type: {content_type}")

                    content_length = int(response.headers.get("Content-Length", "0") or "0")
                    if content_length > MAX_SOURCE_IMAGE_BYTES:
                        raise ValueError(f"Image is too large: {url}")
                    data = await response.read()
                    if len(data) > MAX_SOURCE_IMAGE_BYTES:
                        raise ValueError(f"Image exceeded the maximum size: {url}")
                    break
            except (aiohttp.ClientError, asyncio.TimeoutError):
                if attempt == MAX_DOWNLOAD_RETRIES:
                    raise
                await asyncio.sleep(2.0 * attempt)

        if data is None:
            raise RuntimeError(f"Image download exhausted retries: {url}")

    optimized, width, height = optimize_image_bytes(data)
    digest = sha256_bytes(optimized)
    relative_path = f"images/{digest[:2]}/{digest}.webp"
    path = output_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(optimized)

    return ProcessedImage(
        relative_path=relative_path,
        sha256=digest,
        size_bytes=len(optimized),
        width=width,
        height=height,
    )
