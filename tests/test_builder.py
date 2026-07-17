from datetime import datetime, timezone

import pytest

from wuwa_builder.builder import build_release
from wuwa_builder.models import NewsRecord, SourceReference
from wuwa_builder.sources.official import OfficialSiteSource


@pytest.mark.asyncio
async def test_empty_official_result_fails_build(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    async def empty_news(self, max_items: int = 30):
        return []

    monkeypatch.setattr(OfficialSiteSource, "collect_news", empty_news)

    with pytest.raises(RuntimeError, match="zero records"):
        await build_release(tmp_path / "release", "0.1.0", 30, True)


@pytest.mark.asyncio
async def test_empty_assets_are_not_advertised(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    record = NewsRecord(
        id="news_test",
        title="Official test announcement",
        category="announcement",
        published_at=datetime(2026, 7, 16, tzinfo=timezone.utc),
        body_text="Validated official announcement.",
        image_urls=[],
        source=SourceReference(
            source_id="kurogames-official",
            source_url="https://wutheringwaves.kurogames.com/en/announcement/451",
            trust_tier="official",
        ),
    )

    async def one_news(self, max_items: int = 30):
        return [record]

    monkeypatch.setattr(OfficialSiteSource, "collect_news", one_news)

    manifest = await build_release(tmp_path / "release", "0.1.0", 30, True)

    assert manifest.database.available is True
    assert manifest.assets.available is False
    assert manifest.assets.url is None
    assert manifest.assets.sha256 is None
    assert manifest.assets.size_bytes == 0
