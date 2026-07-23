# WuWa Database Server

Manual data builder and public update feed for the unofficial WuWa Companion
Android app.

> [!IMPORTANT]
> This is an unofficial, non-commercial fan project. It is not affiliated with,
> endorsed by, sponsored by, or approved by Kuro Games. Wuthering Waves and all
> associated visual and audio assets are trademarks, copyrights, or other
> intellectual property of Kuro Games and/or its licensors. The MIT
> License covers original project code only—not official game assets or
> separately licensed data. Takedown or licensing requests may be sent to
> **chengoleinnocent@gmail.com**. See [LEGAL.md](LEGAL.md).

## Current source strategy

Official Wuthering Waves sources remain the preferred authority for
announcements and verification. The current Kuro Games website is heavily
client-rendered and its public listing routes have not exposed stable
announcement links to GitHub Actions, so it is not part of the required build
path at present.

Structured catalog records are collected through the Wuthering Waves Wiki's
public MediaWiki API:

```text
https://wutheringwaves.fandom.com/api.php
```

Current datasets:

- resonators;
- weapons;
- Echoes; and
- development materials.

Every community-derived record retains its source page URL, retrieval timestamp,
revision ID when available, revision timestamp, and attribution metadata.

## Responsible automation

The source adapter:

- checks `robots.txt` before accessing the API;
- verifies the wiki's declared text licence through MediaWiki site information;
- uses a transparent project-specific User-Agent;
- makes requests sequentially with a two-second minimum interval;
- respects HTTP 429 and 503 responses with retries and backoff;
- rejects malformed records;
- fails the build when every dataset is empty; and
- does not evade anti-bot controls, rotate proxies, bypass CAPTCHAs, or use
  private APIs.

## Images and permission status

Fandom text may be available under CC BY-SA, but uploaded images and videos are
not automatically covered by that licence. The backend therefore does not
download or publish Fandom images.

Written permission has been requested from Kuro Games for limited use of
selected official game images. A request, silence, or support correspondence is
not approval. Official-image packaging must remain disabled unless express
written permission covering repository and package redistribution is received.

If permission is not granted or is later withdrawn, the project will continue
with original placeholders and text-first records. See
[LEGAL.md](LEGAL.md), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), and
[public/assets/NOTICE.md](public/assets/NOTICE.md).

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

Published packages are attached to immutable GitHub Releases. The client
verifies the declared SHA-256 checksum before importing a package.

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

- Original repository code: [MIT License](LICENSE)
- Legal disclaimer and rights-holder process: [LEGAL.md](LEGAL.md)
- Third-party and data notices:
  [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)

Community-derived text and metadata in generated catalogs are packaged under
their applicable licence with `ATTRIBUTION.md`, `DATA_LICENSE.md`, source URLs,
and revision metadata.
