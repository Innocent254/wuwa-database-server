# Trusted-source policy

## Priority

1. Official Wuthering Waves sources remain the preferred authority for announcements and verification.
2. Fandom's public MediaWiki API may supply structured community-reviewed catalog records when the official site does not expose stable machine-readable routes.
3. Every community-derived record must retain its exact page URL, retrieval time, revision ID when available, trust tier, and license metadata.
4. No leak repositories, private APIs, bypassed authentication, CAPTCHA bypasses, proxy rotation, or anti-bot evasion.

## Responsible automation

- Read and enforce `robots.txt` before using the MediaWiki API.
- Use a transparent project-specific User-Agent rather than pretending to be a human browser.
- Make requests sequentially with at least a two-second interval.
- Respect HTTP 429/503 responses and `Retry-After`.
- Stop the build when every source returns zero validated records.
- Keep publication manual through the `publish` workflow mode.

## Fandom text licensing

Fandom wiki text is generally CC BY-SA 3.0 unless otherwise noted. Community-derived records therefore include source and attribution URLs and are packaged with `ATTRIBUTION.md` and `DATA_LICENSE.md`.

The MIT license covers repository code, not copied or derived wiki content.

## Images

Fandom-hosted images are not automatically covered by the wiki text license. This adapter deliberately does not download them. Image packaging remains unavailable until the backend validates each file's explicit license and source metadata.
