# Upload this licensed-image patch

Upload the contents of this folder to the root of `Innocent254/wuwa-database-server`, preserving the `.github`, `wuwa_builder`, and `tests` directories.

Suggested commit message:

```text
Add license-filtered Fandom image pipeline
```

Then start a **new** manual workflow run with:

- Mode: `dry-run`
- Maximum records per dataset: `250`
- Include images: enabled
- Version override: blank

The builder uses the Wuthering Waves Wiki and its MediaWiki API. It selects representative page images, checks each file's own metadata, and packages only files declaring CC0, Public Domain, CC BY, or CC BY-SA. Fair-use, unknown-license, non-commercial, and no-derivatives files are skipped.

A successful run may still contain zero images if no representative files have an explicit reusable license. That is a licensing result, not a workflow error.
