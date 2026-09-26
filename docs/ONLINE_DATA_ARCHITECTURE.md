# Online Data Architecture — Phase 1.1

The API now wraps the existing `wuwa_builder.sources.fandom.FandomMediaWikiSource`
instead of creating a second scraper.

```text
Fandom MediaWiki API
  -> existing FandomMediaWikiSource
  -> validated WikiEntityRecord
  -> FandomSource adapter
  -> normalized EntityRecord
  -> SQLite cache/index
  -> FastAPI
  -> wuwa-companion-unofficial
```

### Included

- FastAPI/Uvicorn dependencies in `pyproject.toml`.
- Real Fandom adapter using the existing robots/license/throttle/retry controls.
- Conversion from `WikiEntityRecord` to normalized `EntityRecord`.
- SQLite bulk caching and indexed entity listing.
- Real character/weapon/echo/material filters.
- Search against cached records.
- Cache-miss online acquisition.
- Level-1/max-level stats when the existing collector supplies them.
- Provenance and source/revision metadata.

### Still intentionally incomplete

Skills, detailed material requirements, banner history, patch records, and
other fields are not invented when the source does not provide them. They remain
empty until a permitted source can supply and validate them.

The existing static builder and release workflow remain in place during migration.
