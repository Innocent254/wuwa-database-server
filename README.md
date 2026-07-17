# WuWa Database Server

Manual data builder and public update feed for the unofficial WuWa Companion Android app.

> This is an unofficial community project. It is not affiliated with, endorsed by, or sponsored by Kuro Games. Wuthering Waves and its assets belong to their respective owners.

## Current source strategy

Official Wuthering Waves sources remain the preferred authority for announcements and verification. The current Kuro Games website is heavily client-rendered and its public listing routes have not exposed stable announcement links to GitHub Actions, so it is not part of the required build path at present.

Structured catalog records are collected through the Wuthering Waves Wiki's public MediaWiki API:

```text
https://wutheringwaves.fandom.com/api.php
```

Current datasets:

- resonators;
- weapons;
- Echoes;
- development materials.

Every community-derived record retains its source page URL, retrieval timestamp, revision ID when available, revision timestamp, and CC BY-SA attribution metadata.

## Responsible automation

The source adapter:

- checks `robots.txt` before accessing the API;
- verifies the wiki's declared text license through MediaWiki site information;
- uses a transparent project-specific User-Agent;
- makes requests sequentially with a two-second minimum interval;
- respects HTTP 429 and 503 responses with retries and backoff;
- rejects malformed records;
- fails the build when every dataset is empty;
- does not evade anti-bot controls, rotate proxies, bypass CAPTCHAs, or use private APIs.

## Images

Fandom text is generally available under CC BY-SA, but uploaded images and videos are not automatically covered by that license. The backend therefore does not download or publish Fandom images. The assets package remains unavailable until per-file source and license validation is implemented.

## Manual workflow

Nothing runs on a schedule.

1. Open **Actions**.
2. Select **Build WuWa database manually**.
3. Click **Run workflow**.
4. Use `dry-run` to inspect an artifact.
5. Use `publish` only after the artifact has been validated.

Recommended dry-run settings:

```text
Maximum records per dataset: 250
Include images: disabled
Version override: blank
```

## Public update contract

The Android app checks:

```text
https://raw.githubusercontent.com/Innocent254/wuwa-database-server/main/public/latest/version.json
```

Published packages are attached to immutable GitHub Releases. The client verifies the declared SHA-256 checksum before importing a package.

## Local validation

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q
python -m wuwa_builder.cli \
  --output build/release \
  --max-items-per-dataset 250 \
  --no-include-images
```

## Licensing

Repository source code is MIT licensed. Community-derived text and metadata in generated catalogs are packaged under CC BY-SA 3.0 with `ATTRIBUTION.md`, `DATA_LICENSE.md`, source URLs, and revision metadata.
