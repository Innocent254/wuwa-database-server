from __future__ import annotations

import asyncio
import html
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import quote, unquote, urlparse
from urllib.robotparser import RobotFileParser

import aiohttp

from wuwa_builder.assets import build_assets
from wuwa_builder.models import (
    AssetRecord,
    LicensedImageCandidate,
    SourceReference,
    WikiEntityRecord,
)
from wuwa_builder.util import stable_id

LOGGER = logging.getLogger(__name__)

BASE_URL = "https://wutheringwaves.fandom.com"
WIKI_HOME_URL = f"{BASE_URL}/wiki/Wuthering_Waves_Wiki"
API_URL = f"{BASE_URL}/api.php"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
SOURCE_ID = "wuthering-waves-fandom-mediawiki"
USER_AGENT = (
    "WuWaCompanionDataBuilder/0.3 "
    "(+https://github.com/Innocent254/wuwa-database-server; contact via GitHub issues)"
)
REQUEST_INTERVAL_SECONDS = 2.0
REQUEST_TIMEOUT_SECONDS = 45
MAX_RETRIES = 3
PAGE_QUERY_BATCH_SIZE = 25
IMAGEINFO_BATCH_SIZE = 20
MAX_LICENSED_IMAGES = 500

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

ELEMENTS = ("Aero", "Electro", "Fusion", "Glacio", "Havoc", "Spectro")
WEAPON_TYPES = ("Broadblade", "Gauntlets", "Pistols", "Rectifier", "Sword")
ECHO_CLASSES = ("Calamity", "Overlord", "Elite", "Common")
KNOWN_REGIONS = ("Huanglong", "Jinzhou", "Rinascita", "Septimont", "Black Shores", "New Federation")
KNOWN_FACTIONS = (
    "Jinzhou", "The Black Shores", "Black Shores", "New Federation", "Fractsidus",
    "Order of the Deep", "Septimont", "Rinascita",
)

FREE_LICENSE_MARKERS = (
    "cc0",
    "public domain",
    "cc-by-sa",
    "cc by-sa",
    "cc-by ",
    "cc by ",
    "creative commons attribution",
)
NON_REUSABLE_LICENSE_MARKERS = (
    "fair use",
    "fairuse",
    "non-free",
    "nonfree",
    "all rights reserved",
    "no license",
    "nolicense",
    "unknown",
    "noncommercial",
    "non-commercial",
    "cc-by-nc",
    "cc by-nc",
    "cc-by-nd",
    "cc by-nd",
    "no derivatives",
)
SUPPORTED_IMAGE_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/gif",
}


@dataclass(frozen=True)
class PageImageCandidate:
    entity_id: str
    file_title: str
    preview_url: str


@dataclass(frozen=True)
class ReusableImageLicense:
    name: str
    url: str


def robots_allows_api(robots_text: str) -> bool:
    parser = RobotFileParser()
    parser.parse(robots_text.splitlines())
    return parser.can_fetch(USER_AGENT, API_URL)


def robots_status_is_unavailable(status: int) -> bool:
    """Return True when RFC 9309 treats robots.txt as unavailable.

    HTTP 4xx responses mean the robots file is unavailable and automated
    clients may continue. HTTP 429 remains a deliberate local safety stop
    because it explicitly signals rate limiting.
    """

    return 400 <= status < 500 and status != 429


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


def article_url(title: str) -> str:
    encoded = quote(title.replace(" ", "_"), safe="/_()'.,-")
    return f"{BASE_URL}/wiki/{encoded}"


def article_title_from_url(url: str) -> str:
    path = urlparse(url).path
    marker = "/wiki/"
    if marker not in path:
        return ""
    return unquote(path.split(marker, 1)[1]).replace("_", " ")


def metadata_text(extmetadata: dict[str, Any], key: str) -> str:
    raw = extmetadata.get(key)
    if isinstance(raw, dict):
        raw = raw.get("value")
    if raw is None:
        return ""
    text = re.sub(r"<[^>]+>", " ", str(raw))
    return " ".join(html.unescape(text).split())


def reusable_image_license(extmetadata: dict[str, Any]) -> ReusableImageLicense | None:
    """Accept only an explicit free-license declaration from the file metadata.

    A global disclaimer, non-commercial status, or EXIF removal does not grant
    permission. Fair-use, unknown, non-commercial, and no-derivatives files are
    deliberately excluded from automated packaging.
    """

    short_name = metadata_text(extmetadata, "LicenseShortName")
    usage_terms = metadata_text(extmetadata, "UsageTerms")
    license_url = metadata_text(extmetadata, "LicenseUrl")
    combined = " ".join((short_name, usage_terms, license_url)).casefold()

    if not short_name and not usage_terms:
        return None
    if any(marker in combined for marker in NON_REUSABLE_LICENSE_MARKERS):
        return None
    if not any(marker in combined for marker in FREE_LICENSE_MARKERS):
        return None

    if "cc0" in combined or "publicdomain/zero" in combined:
        return ReusableImageLicense(
            name="CC0-1.0",
            url=license_url or "https://creativecommons.org/publicdomain/zero/1.0/",
        )
    if "public domain" in combined or "publicdomain/mark" in combined:
        return ReusableImageLicense(
            name="Public-Domain",
            url=license_url or "https://creativecommons.org/publicdomain/mark/1.0/",
        )

    share_alike = "by-sa" in combined or "by sa" in combined or "share alike" in combined
    version_match = re.search(r"(?:licenses/(?:by-sa|by)/|\b)([234]\.0)\b", combined)
    version = version_match.group(1) if version_match else "3.0"
    license_code = "CC-BY-SA" if share_alike else "CC-BY"
    path_code = "by-sa" if share_alike else "by"
    return ReusableImageLicense(
        name=f"{license_code}-{version}",
        url=license_url or f"https://creativecommons.org/licenses/{path_code}/{version}/",
    )


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


def _category_value(categories: list[str], suffix: str, choices: Sequence[str]) -> str | None:
    folded = [(category.casefold(), category) for category in categories]
    for choice in choices:
        needles = {f"{choice} {suffix}".casefold()}
        if choice.endswith("s"):
            needles.add(f"{choice[:-1]} {suffix}".casefold())
        if any(needle in category for category, _ in folded for needle in needles):
            return choice
    return None


def structured_metadata(categories: list[str], entity_type: str) -> dict[str, Any]:
    """Turn stable wiki classifications into portable catalog fields.

    Category names are preferable to brittle visual-page scraping and remain attached
    to the record for attribution and future reprocessing.
    """
    joined = " | ".join(categories)
    rarity_match = re.search(r"\b([1-5])-Star\b", joined, re.IGNORECASE)
    version_match = re.search(r"Released in Version\s+([0-9]+(?:\.[0-9]+)*)", joined, re.IGNORECASE)
    element = _category_value(categories, "Resonators", ELEMENTS)
    weapon_type = _category_value(categories, "Resonators", WEAPON_TYPES)
    if entity_type == "weapon":
        weapon_type = next((choice for choice in WEAPON_TYPES if any(category.casefold() == choice.casefold() for category in categories)), None)
    faction = None
    if entity_type == "resonator":
        faction = next((
            category.removesuffix(" Resonators")
            for category in categories
            if category.endswith(" Resonators")
            and category.removesuffix(" Resonators") in KNOWN_FACTIONS
        ), None)
    region = next((region for region in KNOWN_REGIONS if any(region.casefold() in category.casefold() for category in categories)), None)
    echo_class = next((choice for choice in ECHO_CLASSES if any(f"{choice} Class".casefold() in category.casefold() for category in categories)), None)
    material_type = next((
        label for label in ("Ascension", "Forte", "Weapon Ascension", "Cooking", "Crafting", "Currency", "Local Specialty")
        if any(label.casefold() in category.casefold() for category in categories)
    ), None) if entity_type == "material" else None
    sources = sorted({
        category.removesuffix(" Source")
        for category in categories
        if category.endswith(" Source") and len(category) <= 80
    })
    return {
        "rarity": int(rarity_match.group(1)) if rarity_match else None,
        "element": element,
        "weapon_type": weapon_type,
        "echo_class": echo_class,
        "faction": faction,
        "region": region,
        "release_version": version_match.group(1) if version_match else None,
        "material_type": material_type,
        "acquisition_sources": sources,
    }


def fallback_summary(name: str, entity_type: str, metadata: dict[str, Any]) -> str:
    parts: list[str] = []
    qualifiers = [
        f"{metadata['rarity']}-star" if metadata.get("rarity") else None,
        metadata.get("element"),
        metadata.get("weapon_type"),
        metadata.get("echo_class") and f"{metadata['echo_class']} Class",
        metadata.get("material_type"),
    ]
    label = " ".join(str(value) for value in qualifiers if value)
    noun = f"{label} {entity_type}".strip()
    article = "an" if noun[:1].casefold() in "aeiou" else "a"
    parts.append(f"{name} is {article} {noun} in Wuthering Waves.")
    if metadata.get("faction"):
        parts.append(f"Faction: {metadata['faction']}.")
    elif metadata.get("region"):
        parts.append(f"Region: {metadata['region']}.")
    if metadata.get("release_version"):
        parts.append(f"Introduced in Version {metadata['release_version']}.")
    if metadata.get("acquisition_sources"):
        parts.append("Source: " + ", ".join(metadata["acquisition_sources"]) + ".")
    return " ".join(parts)


def enrich_from_extract(metadata: dict[str, Any], extract: str) -> dict[str, Any]:
    enriched = dict(metadata)
    release_match = re.search(
        r"Release Date\s+([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
        extract,
    )
    if release_match:
        enriched["release_date"] = release_match.group(1)
    source_match = re.search(
        r"(?:How to Obtain|Acquisition Method)\s+([^\n]{2,160})",
        extract,
        re.IGNORECASE,
    )
    if source_match and not enriched.get("acquisition_sources"):
        enriched["acquisition_sources"] = [source_match.group(1).strip()]
    return enriched


def readable_extract_summary(name: str, extract: str) -> str:
    normalized = " ".join(extract.split())
    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    relevant = [
        sentence for sentence in sentences
        if name.casefold() in sentence.casefold()
        and (" is " in sentence.casefold() or " serves " in sentence.casefold())
        and len(sentence) <= 700
    ]
    return " ".join(relevant[:3])[:4000]


def records_from_query_pages(
    pages: list[dict[str, Any]],
    entity_type: str,
    retrieved_at: datetime | None = None,
) -> list[WikiEntityRecord]:
    now = retrieved_at or datetime.now(timezone.utc)
    output: list[WikiEntityRecord] = []

    for page in pages:
        title = str(page.get("title") or "").strip()
        page_id = page.get("pageid")
        if not title or not isinstance(page_id, int):
            LOGGER.warning("Skipping malformed MediaWiki page payload: %r", page)
            continue

        source_url = str(page.get("fullurl") or article_url(title)).strip()
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

        extract = str(page.get("extract") or "").strip()
        metadata = enrich_from_extract(structured_metadata(categories, entity_type), extract)
        summary = readable_extract_summary(normalize_entity_name(title, entity_type), extract)
        if not summary:
            summary = fallback_summary(normalize_entity_name(title, entity_type), entity_type, metadata)

        output.append(
            WikiEntityRecord(
                id=stable_id(entity_type, f"{page_id}:{source_url}"),
                name=normalize_entity_name(title, entity_type),
                entity_type=entity_type,
                summary=summary,
                categories=sorted(set(categories)),
                **metadata,
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


def _title_key(value: str) -> str:
    return " ".join(value.replace("_", " ").split()).casefold()


def _batched(items: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


class FandomMediaWikiSource:
    """Polite reader for Fandom's public MediaWiki API.

    Text is imported under the wiki's declared CC BY-SA license. Image files
    are included only after their own file metadata declares an accepted free
    license. Fair-use and unknown-license images are never packaged.
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

    async def collect_licensed_assets(
        self,
        records: Sequence[WikiEntityRecord],
        output_dir: Path,
        max_images: int = MAX_LICENSED_IMAGES,
    ) -> list[AssetRecord]:
        if not records or max_images <= 0:
            return []

        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            await self._assert_robots_permission(session)
            page_candidates = await self._discover_page_images(
                session,
                list(records),
                max_images=max_images,
            )
            licensed_candidates = await self._resolve_image_licenses(session, page_candidates)

        LOGGER.info(
            "Image pipeline accepted %d of %d representative-image candidates",
            len(licensed_candidates),
            len(page_candidates),
        )
        return await build_assets(licensed_candidates, output_dir)

    async def _assert_robots_permission(self, session: aiohttp.ClientSession) -> None:
        await self._throttle()
        try:
            async with session.get(ROBOTS_URL, allow_redirects=True) as response:
                if robots_status_is_unavailable(response.status):
                    LOGGER.warning(
                        "Fandom robots.txt returned HTTP %s. RFC 9309 classifies "
                        "HTTP 4xx robots responses as unavailable, so the public "
                        "MediaWiki API check may continue.",
                        response.status,
                    )
                    return
                if response.status == 429:
                    retry_after = response.headers.get("Retry-After", "unknown")
                    raise RuntimeError(
                        "Fandom rate-limited the robots.txt request with HTTP 429 "
                        f"(Retry-After: {retry_after}). Try the workflow again later."
                    )
                if response.status >= 500:
                    raise RuntimeError(
                        f"Fandom robots.txt returned HTTP {response.status}; "
                        "RFC 9309 requires treating the site as disallowed while "
                        "robots.txt is unreachable."
                    )
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
                "explaintext": "1",
                "exchars": "4000",
                "cllimit": "max",
                "rvprop": "ids|timestamp",
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

    async def _discover_page_images(
        self,
        session: aiohttp.ClientSession,
        records: list[WikiEntityRecord],
        max_images: int,
    ) -> list[PageImageCandidate]:
        candidates: list[PageImageCandidate] = []

        for batch in _batched(records, PAGE_QUERY_BATCH_SIZE):
            title_to_record: dict[str, WikiEntityRecord] = {}
            titles: list[str] = []
            for record in batch:
                title = article_title_from_url(str(record.attribution_url)) or record.name
                titles.append(title)
                title_to_record[_title_key(title)] = record

            payload = await self._request_json(
                session,
                {
                    "action": "query",
                    "format": "json",
                    "formatversion": "2",
                    "titles": "|".join(titles),
                    "prop": "pageimages",
                    "piprop": "name|thumbnail|original",
                    "pithumbsize": "1024",
                    "pilicense": "any",
                    "redirects": "1",
                    "maxlag": "5",
                },
            )
            query = payload.get("query", {})
            for normal in query.get("normalized", []) or []:
                source = title_to_record.get(_title_key(str(normal.get("from") or "")))
                if source:
                    title_to_record[_title_key(str(normal.get("to") or ""))] = source
            for redirect in query.get("redirects", []) or []:
                source = title_to_record.get(_title_key(str(redirect.get("from") or "")))
                if source:
                    title_to_record[_title_key(str(redirect.get("to") or ""))] = source

            pages = query.get("pages", [])
            if not isinstance(pages, list):
                continue
            for page in pages:
                record = title_to_record.get(_title_key(str(page.get("title") or "")))
                pageimage = str(page.get("pageimage") or "").strip()
                preview = page.get("thumbnail") or page.get("original") or {}
                preview_url = str(preview.get("source") or "").strip()
                if not record or not pageimage or not preview_url:
                    continue
                file_title = pageimage if pageimage.startswith("File:") else f"File:{pageimage}"
                candidates.append(
                    PageImageCandidate(
                        entity_id=record.id,
                        file_title=file_title,
                        preview_url=preview_url,
                    )
                )
                if len(candidates) >= max_images:
                    return candidates

        return candidates

    async def _resolve_image_licenses(
        self,
        session: aiohttp.ClientSession,
        candidates: list[PageImageCandidate],
    ) -> list[LicensedImageCandidate]:
        by_title: dict[str, list[PageImageCandidate]] = {}
        for candidate in candidates:
            by_title.setdefault(_title_key(candidate.file_title), []).append(candidate)

        accepted: list[LicensedImageCandidate] = []
        file_titles = sorted({candidate.file_title for candidate in candidates})
        metadata_filter = (
            "LicenseShortName|LicenseUrl|UsageTerms|Artist|Credit|Attribution|"
            "Copyrighted|Restrictions"
        )

        for batch in _batched(file_titles, IMAGEINFO_BATCH_SIZE):
            payload = await self._request_json(
                session,
                {
                    "action": "query",
                    "format": "json",
                    "formatversion": "2",
                    "titles": "|".join(batch),
                    "prop": "imageinfo",
                    "iiprop": "url|size|mime|extmetadata",
                    "iiurlwidth": "1024",
                    "iiextmetadatafilter": metadata_filter,
                    "iiextmetadataversion": "latest",
                    "maxlag": "5",
                },
            )
            pages = payload.get("query", {}).get("pages", [])
            if not isinstance(pages, list):
                continue

            for page in pages:
                title = str(page.get("title") or "").strip()
                linked = by_title.get(_title_key(title), [])
                imageinfo = page.get("imageinfo") or []
                info = imageinfo[0] if imageinfo and isinstance(imageinfo[0], dict) else {}
                extmetadata = info.get("extmetadata") or {}
                license_info = reusable_image_license(extmetadata)
                mime = str(info.get("mime") or "").casefold()
                source_url = str(info.get("thumburl") or info.get("url") or "").strip()
                attribution_url = str(info.get("descriptionurl") or article_url(title)).strip()

                if not linked or not license_info or mime not in SUPPORTED_IMAGE_MIME_TYPES:
                    continue
                if not source_url or not attribution_url:
                    continue

                author = metadata_text(extmetadata, "Artist")
                credit = metadata_text(extmetadata, "Credit") or metadata_text(
                    extmetadata, "Attribution"
                )
                for candidate in linked:
                    accepted.append(
                        LicensedImageCandidate(
                            entity_id=candidate.entity_id,
                            file_title=title,
                            source_url=source_url,
                            attribution_url=attribution_url,
                            license_name=license_info.name,
                            license_url=license_info.url,
                            author=author,
                            credit=credit,
                        )
                    )

        return accepted

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
