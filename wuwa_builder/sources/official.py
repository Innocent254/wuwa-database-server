from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from playwright.async_api import Browser, Page, TimeoutError as PlaywrightTimeout
from playwright.async_api import async_playwright

from wuwa_builder.models import NewsRecord, SourceReference
from wuwa_builder.util import stable_id

LOGGER = logging.getLogger(__name__)

BASE_URL = "https://wutheringwaves.kurogames.com/en/main/"
NEWS_URL = urljoin(BASE_URL, "news")
MIN_REQUEST_INTERVAL_SECONDS = 2.5
NAVIGATION_TIMEOUT_MS = 30_000


class OfficialSiteSource:
    """Conservative adapter for Kuro Games' official Wuthering Waves website.

    The site is a client-rendered application. This adapter intentionally uses
    broad, defensive selectors and skips malformed pages instead of publishing
    guessed data.
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
                records: list[NewsRecord] = []
                for detail_url in detail_urls:
                    record = await self._read_detail(page, detail_url)
                    if record is not None:
                        records.append(record)
                return records
            finally:
                await browser.close()

    async def _new_page(self, browser: Browser) -> Page:
        context = await browser.new_context(
            locale="en-US",
            user_agent=(
                "Mozilla/5.0 (compatible; WuWaCompanionDataBuilder/0.1; "
                "+https://github.com/Innocent254/wuwa-database-server)"
            ),
        )
        page = await context.new_page()
        page.set_default_timeout(NAVIGATION_TIMEOUT_MS)
        return page

    async def _discover_detail_urls(self, page: Page, max_items: int) -> list[str]:
        await self._throttle()
        await page.goto(NEWS_URL, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)

        try:
            await page.wait_for_selector(
                "a[href*='/news/detail/'], a[href*='news/detail']",
                timeout=NAVIGATION_TIMEOUT_MS,
            )
        except PlaywrightTimeout:
            LOGGER.warning("Official news links were not found; the site layout may have changed.")
            return []

        hrefs = await page.eval_on_selector_all(
            "a[href*='/news/detail/'], a[href*='news/detail']",
            "nodes => nodes.map(node => node.getAttribute('href')).filter(Boolean)",
        )

        seen: set[str] = set()
        output: list[str] = []
        for href in hrefs:
            absolute = urljoin(NEWS_URL, href)
            if absolute in seen:
                continue
            seen.add(absolute)
            output.append(absolute)
            if len(output) >= max_items:
                break
        return output

    async def _read_detail(self, page: Page, url: str) -> NewsRecord | None:
        await self._throttle()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=NAVIGATION_TIMEOUT_MS)
            await page.wait_for_timeout(1200)
        except PlaywrightTimeout:
            LOGGER.warning("Timed out loading %s", url)
            return None

        title = await self._first_text(
            page,
            ["h1", "[class*='title']", "meta[property='og:title']"],
            meta_attribute="content",
        )
        if not title or title.lower() == "wuthering waves official website":
            LOGGER.warning("Rejected detail page without a reliable title: %s", url)
            return None

        body_text = await self._first_text(
            page,
            ["article", "[class*='detail-content']", "[class*='news-detail']", "main"],
        ) or ""

        image_urls = await page.eval_on_selector_all(
            "article img, main img, [class*='detail'] img",
            """nodes => nodes
                .map(node => node.currentSrc || node.src || node.getAttribute('data-src'))
                .filter(Boolean)""",
        )
        normalized_images = []
        seen_images = set()
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
    async def _extract_date(page: Page) -> datetime | None:
        candidates = await page.eval_on_selector_all(
            "time, [class*='date'], [class*='time']",
            "nodes => nodes.map(node => node.getAttribute('datetime') || node.textContent)",
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
