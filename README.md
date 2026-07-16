# WuWa Database Server

Manual data-builder and public update feed for the unofficial WuWa Companion Android app.

> This is an unofficial community project. It is not affiliated with, endorsed by, or sponsored by Kuro Games. Wuthering Waves and its assets belong to their respective owners.

## Responsibility

This repository contains the backend and hosted data only:

- manually triggered Python scraping/build pipeline;
- trusted-source adapters, beginning with the official Wuthering Waves website;
- validation, normalization, image optimization, and package generation;
- public `version.json` and immutable GitHub Release artifacts;
- checksums used by the Android app before applying an update.

The Android client lives in `Innocent254/wuwa-companion-unofficial`.

## Manual workflow

Nothing runs on a schedule.

1. Open **Actions**.
2. Select **Build WuWa database manually**.
3. Click **Run workflow**.
4. Choose `dry-run` to inspect the generated artifact or `publish` to update `public/latest` and create a GitHub Release.

A dry run never changes the public update feed.

## Public update contract

The Android app checks:

```text
https://raw.githubusercontent.com/Innocent254/wuwa-database-server/main/public/latest/version.json
```

Published packages are attached to GitHub Releases. The app verifies the declared SHA-256 checksum before importing a package.

## Initial source coverage

The first-party adapter targets:

```text
https://wutheringwaves.kurogames.com/en/main/
```

The official site is client-rendered, so the adapter uses Playwright. Initial coverage is announcements, patch notes, version previews, and source-linked images. Full resonator, weapon, Echo, and material records should only be published after a verified source adapter and schema validator exist for that entity.

## Local run

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e .
playwright install chromium
python -m wuwa_builder.cli build --output build/release --max-news-items 30
```

## Data policy

- Prefer official sources.
- Respect rate limits, terms, and robots directives.
- Never publish unvalidated scraped records.
- Preserve source URLs and retrieval timestamps.
- Treat generated data as staged until manually published.
- Do not use leaked or private data.
