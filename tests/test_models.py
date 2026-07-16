from wuwa_builder.models import PackageInfo, UpdateManifest


def test_placeholder_manifest_is_valid() -> None:
    manifest = UpdateManifest(
        database=PackageInfo(version="0.0.0", available=False),
        assets=PackageInfo(version="0.0.0", available=False),
    )
    assert manifest.manifest_version == 1
    assert manifest.database.available is False
