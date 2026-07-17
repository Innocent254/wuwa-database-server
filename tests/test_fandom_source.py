from datetime import datetime, timezone

from wuwa_builder.sources.fandom import (
    article_title_from_url,
    is_supported_text_license,
    metadata_text,
    normalize_entity_name,
    records_from_query_pages,
    reusable_image_license,
    robots_allows_api,
    robots_status_is_unavailable,
)


def test_robots_allows_public_api() -> None:
    assert robots_allows_api("User-agent: *\nAllow: /api.php\n")
    assert not robots_allows_api("User-agent: *\nDisallow: /api.php\n")


def test_rfc9309_treats_regular_4xx_as_unavailable() -> None:
    assert robots_status_is_unavailable(401)
    assert robots_status_is_unavailable(403)
    assert robots_status_is_unavailable(404)
    assert not robots_status_is_unavailable(200)
    assert not robots_status_is_unavailable(429)
    assert not robots_status_is_unavailable(500)


def test_supported_text_license_is_verified() -> None:
    assert is_supported_text_license(
        {
            "text": "Creative Commons Attribution-Share Alike 3.0",
            "url": "https://creativecommons.org/licenses/by-sa/3.0/",
        }
    )
    assert not is_supported_text_license(
        {"text": "All rights reserved", "url": "https://example.test/license"}
    )


def test_echo_name_is_normalized() -> None:
    assert normalize_entity_name("Aero Drake/Echo", "echo") == "Aero Drake"
    assert normalize_entity_name("Jiyan", "resonator") == "Jiyan"


def test_mediawiki_pages_become_attributed_records() -> None:
    pages = [
        {
            "pageid": 451,
            "title": "Jiyan",
            "fullurl": "https://wutheringwaves.fandom.com/wiki/Jiyan",
            "extract": "Jiyan is a playable Resonator.",
            "categories": [
                {"title": "Category:5-Star Resonators"},
                {"title": "Category:Aero Resonators"},
            ],
            "revisions": [{"revid": 12345, "timestamp": "2026-07-17T00:00:00Z"}],
        }
    ]
    records = records_from_query_pages(
        pages,
        "resonator",
        retrieved_at=datetime(2026, 7, 17, tzinfo=timezone.utc),
    )
    assert len(records) == 1
    record = records[0]
    assert record.name == "Jiyan"
    assert record.entity_type == "resonator"
    assert record.revision_id == 12345
    assert record.license_name == "CC-BY-SA-3.0"
    assert str(record.attribution_url) == "https://wutheringwaves.fandom.com/wiki/Jiyan"
    assert record.source.trust_tier == "community_reviewed"


def test_missing_fullurl_is_reconstructed_instead_of_dropping_record() -> None:
    records = records_from_query_pages([{"pageid": 510, "title": "Chixia"}], "resonator")
    assert len(records) == 1
    assert str(records[0].attribution_url) == "https://wutheringwaves.fandom.com/wiki/Chixia"


def test_article_title_is_recovered_from_attribution_url() -> None:
    assert article_title_from_url(
        "https://wutheringwaves.fandom.com/wiki/Aero_Drake/Echo"
    ) == "Aero Drake/Echo"


def test_html_metadata_is_reduced_to_plain_text() -> None:
    assert metadata_text(
        {"Artist": {"value": "<a href='x'>Kuro Games</a> &amp; contributors"}},
        "Artist",
    ) == "Kuro Games & contributors"


def test_explicit_cc_by_sa_image_license_is_accepted() -> None:
    result = reusable_image_license(
        {
            "LicenseShortName": {"value": "CC-BY-SA-4.0"},
            "LicenseUrl": {
                "value": "https://creativecommons.org/licenses/by-sa/4.0/"
            },
        }
    )
    assert result is not None
    assert result.name == "CC-BY-SA-4.0"
    assert result.url == "https://creativecommons.org/licenses/by-sa/4.0/"


def test_fair_use_and_unknown_images_are_rejected() -> None:
    assert reusable_image_license(
        {"LicenseShortName": {"value": "Fair use"}}
    ) is None
    assert reusable_image_license(
        {"LicenseShortName": {"value": "No license"}}
    ) is None
    assert reusable_image_license(
        {"LicenseUrl": {"value": "https://www.fandom.com/licensing"}}
    ) is None
