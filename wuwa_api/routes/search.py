from fastapi import APIRouter, Query
from wuwa_api.service import DataService

router = APIRouter()

@router.get("/search")
async def search(
    q: str = Query(min_length=1),
    entity_type: str | None = None,
    limit: int = Query(default=25, ge=1, le=100),
):
    return {"items": await DataService().search(q, entity_type, limit)}
