"""
Fandom adapter placeholder.

The existing wuwa_builder/sources/fandom.py remains the authoritative implementation
during migration. This adapter deliberately does not bypass robots.txt, CAPTCHA,
anti-bot controls, private endpoints, or access restrictions.

Phase 1 integration point:
- Reuse the builder's permitted MediaWiki acquisition logic.
- Convert its WikiEntityRecord into EntityRecord.
"""

from wuwa_api.models import EntityRecord
from wuwa_api.sources.base import SourceAdapter

class FandomSource(SourceAdapter):
    name = "fandom"
    priority = 100

    async def get_entity(self, entity_type: str, entity_id: str) -> EntityRecord | None:
        return None

    async def search(self, query: str, entity_type: str | None = None) -> list[EntityRecord]:
        return []
