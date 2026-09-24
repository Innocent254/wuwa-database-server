from fastapi import APIRouter, HTTPException, Query
from wuwa_api.models import EntityPage, EntityRecord
from wuwa_api.service import DataService

router = APIRouter()

def service() -> DataService:
    return DataService()

@router.get("/characters", response_model=EntityPage)
async def characters(
    element: str | None = None,
    faction: str | None = None,
    rarity: int | None = Query(default=None, ge=1, le=5),
    weapon_type: str | None = None,
    release_version: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    return await service().list_entities("character", element, faction, rarity, weapon_type,
                                          release_version, limit, offset)

@router.get("/characters/{entity_id}", response_model=EntityRecord)
async def character(entity_id: str):
    result = await service().get("character", entity_id)
    if result is None:
        raise HTTPException(404, "Character not found")
    return result

@router.get("/weapons", response_model=EntityPage)
async def weapons(
    rarity: int | None = Query(default=None, ge=1, le=5),
    weapon_type: str | None = None,
    release_version: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    return await service().list_entities("weapon", None, None, rarity, weapon_type,
                                          release_version, limit, offset)

@router.get("/weapons/{entity_id}", response_model=EntityRecord)
async def weapon(entity_id: str):
    result = await service().get("weapon", entity_id)
    if result is None:
        raise HTTPException(404, "Weapon not found")
    return result

@router.get("/echoes", response_model=EntityPage)
async def echoes(limit: int = Query(default=50, ge=1, le=200),
                 offset: int = Query(default=0, ge=0)):
    return await service().list_entities("echo", None, None, None, None, None, limit, offset)

@router.get("/materials", response_model=EntityPage)
async def materials(limit: int = Query(default=50, ge=1, le=200),
                    offset: int = Query(default=0, ge=0)):
    return await service().list_entities("material", None, None, None, None, None, limit, offset)
