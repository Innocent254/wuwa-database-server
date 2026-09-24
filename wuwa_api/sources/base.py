from abc import ABC, abstractmethod
from typing import Any
from wuwa_api.models import EntityRecord

class SourceAdapter(ABC):
    name: str
    priority: int = 100

    @abstractmethod
    async def get_entity(self, entity_type: str, entity_id: str) -> EntityRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def search(self, query: str, entity_type: str | None = None) -> list[EntityRecord]:
        raise NotImplementedError
