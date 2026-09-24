# Drag-and-Drop Installation

Copy the contents of this ZIP into the root of `wuwa-database-server`.

Expected new paths:

wuwa_api/
tests/api/
tests/aggregation/
docs/ONLINE_DATA_ARCHITECTURE.md
docs/DRAG_AND_DROP.md

## Important

This is an additive Phase 1 scaffold. It does not replace the existing
`wuwa_builder/` and does not delete or modify your existing catalog data.

## Dependencies

The API uses FastAPI and Uvicorn. Add these to the project's dependencies:

    fastapi>=0.115,<1
    uvicorn[standard]>=0.30,<1

Then install the development dependencies and run tests.

## Local run

    uvicorn wuwa_api.api:app --reload

Open:

    http://127.0.0.1:8000/docs

The source adapter is deliberately a safe integration point. The next step is
to connect the existing permitted Fandom MediaWiki acquisition code rather than
introducing arbitrary scraping.
