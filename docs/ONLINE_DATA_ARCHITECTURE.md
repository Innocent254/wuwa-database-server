# Online Data Architecture — Phase 1

## Goal

Move `wuwa-database-server` from a static/manual catalog model toward an online,
multi-source, normalized and cached data service without deleting the existing
builder.

## Migration rule

The current `wuwa_builder/` remains in place during migration. The new API is
additive. Do not remove `wuwa_master_data.json`, `catalog_overrides.json`, or
the existing publishing workflow until the new pipeline has parity tests.

## Target flow

Online sources
→ source adapters
→ normalization
→ field validation
→ source priority/conflict resolution
→ SQLite cache/index
→ REST query API
→ `wuwa-companion-unofficial`

## Phase 1 endpoints

- `GET /health`
- `GET /v1/characters`
- `GET /v1/characters/{id}`
- `GET /v1/weapons`
- `GET /v1/weapons/{id}`
- `GET /v1/echoes`
- `GET /v1/materials`
- `GET /v1/search?q=...`

The list endpoints already define the intended filter contract for element,
faction, rarity, weapon type and release version. The persistent catalog index
will be connected in the next phase.

## Source policy

Adapters must use permitted public interfaces. Do not bypass robots.txt,
CAPTCHA, authentication, rate limits, anti-bot controls or private APIs.

## Provenance

Records support field-level provenance so the final application can distinguish
where identity, stats, release information and other fields came from.

## Next phases

1. Connect the existing Fandom/MediaWiki acquisition code to `FandomSource`.
2. Add a second permitted structured source.
3. Implement persistent normalized entity tables and indexed filters.
4. Add character level-1/max-level stat and skill endpoints.
5. Add weapon level-1/max-level stats and availability.
6. Add echoes, materials, patches and banners.
7. Add scheduled refresh plus stale-while-revalidate caching.
8. Add contract/parity tests against the existing builder.
9. Migrate the Android client from static `.wupack` reads to the API.
10. Retire obsolete manual/static layers only after parity is proven.
