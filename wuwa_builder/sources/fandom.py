from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.robotparser import RobotFileParser

import aiohttp

from wuwa_builder.models import SourceReference, WikiEntityRecord
from wuwa_builder.util import stable_id

LOGGER = logging.getLogger(__name__)

BASE_URL = "https://wutheringwaves.fandom.com"
API_URL = f"{BASE_URL}/api.php"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
SOURCE_ID = "wuthering-waves-fandom-mediawiki"
USER_AGENT = (
    "WuWaCompanionDataBuilder/0.2 "
    "(+https://github.com/Innocent254/wuwa-database-server; contact via GitHub issues)"
)
REQUEST_INTERVAL_SECONDS = 2.0
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 3
EXPECTED_LICENSE_MARKERS = (
    "cc-by-sa",
    "cc by-sa",
    "creative commons attribution-share alike",
    "creativecommons.org/licenses/by-sa/3.0",
)

DATASET_CATEGORIES: dict[str, str] = {
    "resonators": "Category:Resonators by Rarity and Release Date",
    "weapons": "Category:Weapons by Type and Rarity",
    "echoes": "Category:Echoes by Number",
    "materials": "Category:Development Materials",
}
ENTITY_TYPES = {
    "resonators": "resonator",
    "weapons": "weapon",
    "echoes": "echo",
    "materials": "material",
}


def robots_allows_api(robots_text: str) -> bool:
    parser = RobotFileParser()
    parser.parse(robots_text.splitlines())
    return parser.can_fetch(USER_AGENT, API_URL)


def is_supported_text_license(rights_info: dict[str, Any]) -> bool:
    combined = " ".join(
        str(rights_info.get(key) or "") for key in ("text", "url")
    ).casefold()
    return any(marker in combined for marker in EXPECTED_LICENSE_MARKERS)


def normalize_entity_name(title: str, entity_type: str) -> str:
    cleaned = title.strip()
    if entity_type == "echo" and cleaned.endswith("/Echo"):
        cleaned = cleaned[: -len("/Echo")]
    return cleaned


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(cleaned)
        except (TypeError, ValueError):
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def records_from_query_pages(
    pages: list[dict[str, Any]],
    entity_type: str,
    retrieved_at: datetime | None = None,
) -> list[WikiEntityRecord]:
    now = retrieved_at or datetime.now(timezone.utc)
    output: list[WikiEntityRecord] = []

    for page in pages:
        title = str(page.get("title") or "").strip()
        source_url = str(page.get("fullurl") or "").strip()
        page_id = page.get("pageid")
        if not title or not source_url or not isinstance(page_id, int):
            LOGGER.warning("Skipping malformed MediaWiki page payload: %r", page)
            continue

        categories = []
        for category in page.get("categories") or []:
            category_title = str(category.get("title") or "")
            if category_title.startswith("Category:"):
                category_title = category_title[len("Category:") :]
            if category_title:
                categories.append(category_title)

        revisions = page.get("revisions") or []
        revision = revisions[0] if revisions else {}
        revision_id = revision.get("revid") if isinstance(revision.get("revid"), int) else None
        revision_timestamp = _parse_datetime(revision.get("timestamp"))

        output.append(
            WikiEntityRecord(
                id=stable_id(entity_type, f"{page_id}:{source_url}"),
                name=normalize_entity_name(title, entity_type),
                entity_type=entity_type,
                summary=str(page.get("extract") or "").strip()[:4000],
                categories=sorted(set(categories)),
                revision_id=revision_id,
                revision_timestamp=revision_timestamp,
                attribution_url=source_url,
                source=SourceReference(
                    source_id=SOURCE_ID,
                    source_url=source_url,
                    retrieved_at=now,
                    trust_tier="community_reviewed",
                ),
            )
        )

    output.sort(key=lambda item: item.name.casefold())
    return output


class FandomMediaWikiSource:
    """Polite, text-only reader for Fandom's public MediaWiki API.

    The adapter uses a transparent bot User-Agent, checks robots.txt and the
    declared wiki text license before API access, performs no concurrent
    requests, waits between calls, handles throttling responses, and does not
    download Fandom-hosted media because file licenses vary.
    """

    def __init__(self) -> None:
        self._last_request_at = 0.0

    async def collect_catalog(
        self,
        max_items_per_dataset: int = 250,
    ) -> dict[str, list[WikiEntityRecord]]:
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            await self._assert_robots_permission(session)
            await self._assert_supported_text_license(session)
            output: dict[str, list[WikiEntityRecord]] = {}
            for dataset, category in DATASET_CATEGORIES.items():
                output[dataset] = await self._collect_category(
                    session=session,
                    category=category,
                    entity_type=ENTITY_TYPES[dataset],
                    max_items=max_items_per_dataset,
                )
                LOGGER.info("Collected %d %s records from MediaWiki", len(output[dataset]), dataset)
            return output

    async def _assert_robots_permission(self, session: aiohttp.ClientSession) -> None:
        await self._throttle()
        try:
            async with session.get(ROBOTS_URL, allow_redirects=True) as response:
                if response.status == 404:
                    LOGGER.warning(
                        "Fandom robots.txt was not found; proceeding with the public API."
                    )
                    return
                if response.status in {401, 403}:
                    raise RuntimeError(
                        f"Fandom denied robots.txt access with HTTP {response.status}."
                    )
                if response.status >= 500:
                    raise RuntimeError(f"Fandom robots.txt returned HTTP {response.status}.")
                response.raise_for_status()
                robots_text = await response.text()
        except aiohttp.ClientError as exc:
            raise RuntimeError(f"Could not verify Fandom robots.txt: {exc}") from exc

        if not robots_allows_api(robots_text):
            raise RuntimeError("Fandom robots.txt does not permit this builder to access api.php.")

    async def _assert_supported_text_license(self, session: aiohttp.ClientSession) -> None:
        payload = await self._request_json(
            session,
            {
                "action": "query",
                "format": "json",
                "formatversion": "2",
                "meta": "siteinfo",
                "siprop": "rightsinfo",
                "maxlag": "5",
            },
        )
        rights_info = payload.get("query", {}).get("rightsinfo", {})
        if not isinstance(rights_info, dict) or not is_supported_text_license(rights_info):
            raise RuntimeError(
                "The wiki did not declare a supported CC BY-SA text license; "
                "refusing to import data."
            )
        LOGGER.info(
            "Verified community-wiki text license: %s (%s)",
            rights_info.get("text", "unknown"),
            rights_info.get("url", "no URL"),
        )

    async def _collect_category(
        self,
        session: aiohttp.ClientSession,
        category: str,
        entity_type: str,
        max_items: int,
    ) -> list[WikiEntityRecord]:
        records: list[WikiEntityRecord] = []
        continuation: dict[str, str] = {}

        while len(records) < max_items:
            params: dict[str, str | int] = {
                "action": "query",
                "format": "json",
                "formatversion": "2",
                "generator": "categorymembers",
                "gcmtitle": category,
                "gcmnamespace": "0",
                "gcmtype": "page",
                "gcmlimit": "50",
                "prop": "info|extracts|categories|revisions",
                "inprop": "url",
                "exintro": "1",
                "explaintext": "1",
                "exsentences": "3",
                "cllimit": "max",
                "rvprop": "ids|timestamp",
                "rvlimit": "1",
                "redirects": "1",
                "maxlag": "5",
            }
            params.update(continuation)
            payload = await self._request_json(session, params)
            pages = payload.get("query", {}).get("pages", [])
            if not isinstance(pages, list):
                raise RuntimeError(f"MediaWiki returned an invalid pages payload for {category}.")

            batch = records_from_query_pages(pages, entity_type)
            existing_ids = {item.id for item in records}
            records.extend(item for item in batch if item.id not in existing_ids)
            records = records[:max_items]

            raw_continue = payload.get("continue")
            if not isinstance(raw_continue, dict) or len(records) >= max_items:
                break
            continuation = {str(key): str(value) for key, value in raw_continue.items()}

        return records

    async def _request_json(
        self,
        session: aiohttp.ClientSession,
        params: dict[str, str | int],
    ) -> dict[str, Any]:
        for attempt in range(1, MAX_RETRIES + 1):
            await self._throttle()
            try:
                async with session.get(API_URL, params=params, allow_redirects=True) as response:
                    if response.status in {429, 503}:
                        retry_after = response.headers.get("Retry-After")
                        delay = (
                            float(retry_after)
                            if retry_after and retry_after.isdigit()
                            else 5.0 * attempt
                        )
                        LOGGER.warning(
                            "MediaWiki returned HTTP %s; retrying in %.1f seconds (%d/%d)",
                            response.status,
                            delay,
                            attempt,
                            MAX_RETRIES,
                        )
                        await asyncio.sleep(min(delay, 60.0))
                        continue
                    response.raise_for_status()
                    payload = await response.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
                if attempt == MAX_RETRIES:
                    raise RuntimeError(
                        f"MediaWiki request failed after {attempt} attempts: {exc}"
                    ) from exc
                await asyncio.sleep(3.0 * attempt)
                continue

            if not isinstance(payload, dict):
                raise RuntimeError("MediaWiki returned a non-object JSON response.")
            api_error = payload.get("error")
            if isinstance(api_error, dict) and api_error.get("code") == "maxlag":
                if attempt == MAX_RETRIES:
                    raise RuntimeError(f"MediaWiki remained overloaded: {api_error}")
                await asyncio.sleep(5.0 * attempt)
                continue
            if api_error is not None:
                raise RuntimeError(f"MediaWiki API error: {api_error}")
            return payload

        raise RuntimeError("MediaWiki request exhausted all retries.")

    async def _throttle(self) -> None:
        loop = asyncio.get_running_loop()
        elapsed = loop.time() - self._last_request_at
        if elapsed < REQUEST_INTERVAL_SECONDS:
            await asyncio.sleep(REQUEST_INTERVAL_SECONDS - elapsed)
        self._last_request_at = loop.time()
