import io

from PIL import Image

from wuwa_builder.assets import image_url_is_allowed, optimize_image_bytes


def test_only_expected_fandom_image_hosts_are_allowed() -> None:
    assert image_url_is_allowed("https://static.wikia.nocookie.net/wutheringwaves/a.png")
    assert image_url_is_allowed("https://wutheringwaves.fandom.com/a.png")
    assert not image_url_is_allowed("http://static.wikia.nocookie.net/a.png")
    assert not image_url_is_allowed("https://evil.example/a.png")


def test_image_conversion_outputs_metadata_free_webp() -> None:
    source = io.BytesIO()
    image = Image.new("RGBA", (64, 32), (255, 0, 0, 128))
    image.save(source, format="PNG", exif=b"Exif\x00\x00example")

    optimized, width, height = optimize_image_bytes(source.getvalue())

    assert (width, height) == (64, 32)
    with Image.open(io.BytesIO(optimized)) as converted:
        assert converted.format == "WEBP"
        assert "exif" not in converted.info
