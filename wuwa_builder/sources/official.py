from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urlunparse

from playwright.async_api import Browser, Page, TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright

from wuwa_builder.models import NewsRecord, SourceReference
from wuwa_builder.util import stable_id

LOGGER = logging.getLogger(__name__)

OFFICIAL_HOST = "wutheringwaves.kurogames.com"
BASE_URL = f"https://{OFFICIAL_HOST}/en/"
LISTING_URLS = (
    BASE_URL,
    urljoin(BASE_URL, "main/"),
    urljoin(BASE_URL, "main/news"),
    urljoin(BASE_URL, "news"),
)
MIN_REQUEST_INTERVAL_SECONDS = 2.5
NAVIGATION_TIMEOUT_MS = 30_000
SCROLL_PASSES = 6

SUPPORTED_DETAIL_PATH = re.compile(
    r"^/(?:m/)?en/(?:announcement|news/detail)/\d+/?$",
    re.IGNORECASE,
)
EMBEDDED_DETAIL_PATH = re.compile(
    r"/(?:m/)?en/(?:announcement|news/detail)/\d+",
    re.IGNORECASE,
)
DETAIL_LINK_SELECTOR = "a[href*='/announcement/'], a[href*='/news/detail/']"


def normalize_official_detail_url(raw_url: str, base_url: str = BASE_URL) -> str | None:
    """Return a canonical official detail URL, or None for unsupported/off-site links."""
    if not raw_url or raw_url.startswith(("javascript:", "mailto:", "tel:")):
        return None

    parsed = urlparse(urljoin(base_url, raw_url.strip()))
    if parsed.hostname is None or parsed.hostname.lower() != OFFICIAL_HOST:
        return None
    if not SUPPORTED_DETAIL_PATH.fullmatch(parsed.path):
        return None

    path = parsed.path.rstrip("/")
    return urlunparse(("https", OFFICIAL_HOST, path, "", "", ""))


def extract_supported_detail_urls(html: str, base_url: str = BASE_URL) -> list[str]:
    """Extract supported official detail routes embedded in rendered HTML or scripts."""
    output: list[str] = []
    seen: set[str] = set()
    for match in EMBEDDED_DETAIL_PATH.finditer(html):
        normalized = normalize_official_detail_url(match.group(0), base_url)
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output


class OfficialSiteSource:
    """Conservative adapter for Kuro Games' official Wuthering Waves website.

    The site is client-rendered and its routes have changed over time. Discovery
    therefore checks current announcement routes, legacy news-detail routes,
    rendered anchors, and route strings embedded in the page source. Empty
    discovery is treated as a build failure instead of a valid empty release.
    """

    source_id = "kurogames-official"
    trust_tier = "official"

    def __init__(self) -> None:
        self._last_request_at = 0.0

    async def _throttle(self) -> None:
        loop = asyncio.get_running_loop()
        elapsed = loop.time() - self._last_request_at
        if elapsed < MIN_REQUEST_INTERVAL_SECONDS:
            await asyncio.sleep(MIN_REQUEST_INTERVAL_SECONDS - elapsed)
        self._last_request_at = loop.time()

    async def collect_news(self, max_items: int = 30) -> list[NewsRecord]:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await self._new_page(browser)
                detail_urls = await self._discover_detail_urls(page, max_items)
                if not detail_urls:
                    raise RuntimeError(
                        "No supported official Wuthering Waves announcement URLs were discovered. "
                        "The official site layout or routes may have changed."
                    )

                LOGGER.info("Discovered %d official detail URLs", len(detail_urls))
                records: list[NewsRecord] = []
                for detail_url in detail_urls:
                    record = await self._read_detail(page, detail_url)
                    if record is not None:
                        records.append(record)

                if not records:
                    raise RuntimeError(
                        "Official detail URLs were discovered, but none produced a valid news record."
                    )
                LOGGER.info("Validated %d official news records", len(records))
                return records
            finally:
                await browser.close()

    async def _new_page(self, browser: Browser) -> Page:
        context = await browser.new_context(
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 1200},
        )
        page = await context.new_page()
        page.set_default_timeout(NAVIGATION_TIMEOUT_MS)
        return page

    async def _discover_detail_urls(self, page: Page, max_items: int) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []

        for listing_url in LISTING_URLS:
            if len(output) >= max_items:
                break
            await self._throttle()
            try:
                response = await page.goto(
                    listing_url,
                    wait_until="domcontentloaded",
                    timeout=NAVIGATION_TIMEOUT_MS,
                )
                if response is not None and response.status >= 400:
                    LOGGER.warning("Official listing returned HTTP %s: %s", response.status, listing_url)
                    continue
                await page.wait_for_timeout(2_000)
                await self._progressive_scroll(page)
            except PlaywrightTimeout:
                LOGGER.warning("Timed out loading official listing: %s", listing_url)
                continue

            hrefs = await page.eval_on_selector_all(
                DETAIL_LINK_SELECTOR,
                "nodes => nodes.map(node => node.getAttribute('href')).filter(Boolean)",
            )
            candidates = list(hrefs)
            candidates.extend(extract_supported_detail_urls(await page.content(), listing_url))

            for candidate in candidates:
                normalized = normalize_official_detail_url(candidate, listing_url)
                if normalized is None or normalized in seen:
                    continue
                seen.add(normalized)
                output.append(normalized)
                if len(output) >= max_items:
                    break

        if not output:
            LOGGER.error(
                "No official announcement links found across listing pages: %s",
                ", ".join(LISTING_URLS),
            )
        return output

    @staticmethod
    async def _progressive_scroll(page: Page) -> None:
        previous_height = 0
        for _ in range(SCROLL_PASSES):
            current_height = await page.evaluate("document.body.scrollHeight")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(750)
            if current_height == previous_height:
                break
            previous_height = current_height
        await page.evaluate("window.scrollTo(0, 0)")

    async def _read_detail(self, page: Page, url: str) -> NewsRecord | None:
        await self._throttle()
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
            if response is not None and response.status >= 400:
                LOGGER.warning("Rejected detail page with HTTP %s: %s", response.status, url)
                return None
            await page.wait_for_timeout(1_500)
        except PlaywrightTimeout:
            LOGGER.warning("Timed out loading %s", url)
            return None

        title = await self._first_text(
            page,
            [
                "meta[property='og:title']",
                "meta[name='twitter:title']",
                "h1",
                "[class*='title']",
                "title",
            ],
            meta_attribute="content",
        )
        if not title or title.lower() == "wuthering waves official website":
            LOGGER.warning("Rejected detail page without a reliable title: %s", url)
            return None

        body_text = await self._first_text(
            page,
            [
                "article",
                "[class*='announcement-content']",
                "[class*='detail-content']",
                "[class*='news-detail']",
                "main",
            ],
        )
        if not body_text:
            body_text = await self._first_text(
                page,
                ["meta[property='og:description']", "meta[name='description']"],
                meta_attribute="content",
            ) or ""

        image_urls = await page.eval_on_selector_all(
            "article img, main img, [class*='detail'] img, [class*='announcement'] img",
            """nodes => nodes
                .map(node => node.currentSrc || node.src || node.getAttribute('data-src'))
                .filter(Boolean)""",
        )
        social_image = await self._first_attribute(
            page,
            ["meta[property='og:image']", "meta[name='twitter:image']"],
            "content",
        )
        if social_image:
            image_urls.insert(0, social_image)

        normalized_images: list[str] = []
        seen_images: set[str] = set()
        for image_url in image_urls:
            absolute = urljoin(url, image_url)
            if absolute in seen_images:
                continue
            seen_images.add(absolute)
            normalized_images.append(absolute)

        published_at = await self._extract_date(page)
        category = self._classify(title, body_text)

        return NewsRecord(
            id=stable_id("news", url),
            title=title.strip(),
            category=category,
            published_at=published_at,
            body_text=body_text.strip(),
            image_urls=normalized_images,
            source=SourceReference(
                source_id=self.source_id,
                source_url=url,
                retrieved_at=datetime.now(timezone.utc),
                trust_tier=self.trust_tier,
            ),
        )

    @staticmethod
    async def _first_text(
        page: Page,
        selectors: list[str],
        meta_attribute: str | None = None,
    ) -> str | None:
        for selector in selectors:
            node = await page.query_selector(selector)
            if node is None:
                continue
            if meta_attribute and selector.startswith("meta"):
                value = await node.get_attribute(meta_attribute)
            else:
                value = await node.inner_text()
            if value and value.strip():
                return value.strip()
        return None

    @staticmethod
    async def _first_attribute(page: Page, selectors: list[str], attribute: str) -> str | None:
        for selector in selectors:
            node = await page.query_selector(selector)
            if node is None:
                continue
            value = await node.get_attribute(attribute)
            if value and value.strip():
                return value.strip()
        return None

    @staticmethod
    async def _extract_date(page: Page) -> datetime | None:
        meta_dates = await page.eval_on_selector_all(
            "meta[property='article:published_time'], meta[name='publishdate'], meta[name='date']",
            "nodes => nodes.map(node => node.getAttribute('content')).filter(Boolean)",
        )
        candidates = list(meta_dates)
        candidates.extend(
            await page.eval_on_selector_all(
                "time, [class*='date'], [class*='time']",
                "nodes => nodes.map(node => node.getAttribute('datetime') || node.textContent)",
            )
        )
        for value in candidates:
            if not value:
                continue
            cleaned = value.strip().replace("Z", "+00:00")
            try:
                parsed = datetime.fromisoformat(cleaned)
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                match = re.search(r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})", cleaned)
                if match:
                    year, month, day = map(int, match.groups())
                    return datetime(year, month, day, tzinfo=timezone.utc)
        return None

    @staticmethod
    def _classify(title: str, body: str) -> str:
        text = f"{title}\n{body[:800]}".lower()
        if "patch notes" in text or "update maintenance" in text:
            return "patch_notes"
        if "version preview" in text or re.search(r"\bversion\s+\d+\.\d+\b", text):
            return "version_preview"
        if "event" in text:
            return "event"
        if "announcement" in text or "notice" in text:
            return "announcement"
        return "other"
