from fastapi import FastAPI
from wuwa_api.routes.entities import router as entities_router
from wuwa_api.routes.search import router as search_router

app = FastAPI(
    title="Wuthering Waves Companion Data API",
    version="0.1.0",
    description="Online aggregation, normalization, caching and query API.",
)
app.include_router(entities_router, prefix="/v1")
app.include_router(search_router, prefix="/v1")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "wuwa-database-server"}
