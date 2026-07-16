# Trusted-source policy

## Priority

1. Official Wuthering Waves website and official announcements.
2. Official platform/store announcements when they contain release metadata.
3. Structured community sources only after their license, terms, and correction process are reviewed.
4. No leak repositories, private APIs, bypassed authentication, or data obtained from compromised clients.

## Publication rule

Scraped content is never automatically public merely because extraction succeeded. A manual `publish` workflow run is the publication decision.

Every record must preserve:

- source identifier;
- exact source URL;
- retrieval time;
- trust tier;
- schema validation result.

## Images

Only source-linked images that are needed by the app should be processed. The builder:

- caps source file size and dimensions;
- decodes the image before trusting its extension;
- removes metadata through re-encoding;
- converts to WebP;
- stores by content hash to deduplicate;
- retains the original source URL in the catalog.

The Android app imports packages into private, encrypted app storage. Public release packages are not encrypted because every client must be able to download them; protection on the phone is applied during import.
