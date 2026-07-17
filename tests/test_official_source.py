from wuwa_builder.sources.official import (
    extract_supported_detail_urls,
    normalize_official_detail_url,
)


def test_normalizes_current_announcement_route() -> None:
    assert (
        normalize_official_detail_url("/en/announcement/451?utm_source=test")
        == "https://wutheringwaves.kurogames.com/en/announcement/451"
    )


def test_normalizes_legacy_mobile_news_route() -> None:
    assert (
        normalize_official_detail_url("https://wutheringwaves.kurogames.com/m/en/news/detail/599")
        == "https://wutheringwaves.kurogames.com/m/en/news/detail/599"
    )


def test_rejects_off_site_and_unrelated_routes() -> None:
    assert normalize_official_detail_url("https://example.com/en/announcement/451") is None
    assert normalize_official_detail_url("/en/character/451") is None


def test_extracts_routes_embedded_in_rendered_html() -> None:
    html = """
    <a href='/en/announcement/451'>Current</a>
    <script>window.route = '/en/news/detail/123';</script>
    <a href='/en/announcement/451?duplicate=true'>Duplicate</a>
    """
    assert extract_supported_detail_urls(html) == [
        "https://wutheringwaves.kurogames.com/en/announcement/451",
        "https://wutheringwaves.kurogames.com/en/news/detail/123",
    ]
