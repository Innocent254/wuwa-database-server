from dataclasses import dataclass
import os

@dataclass(frozen=True)
class Settings:
    cache_path: str = os.getenv("WUWA_CACHE_PATH", "data/wuwa_cache.sqlite3")
    cache_ttl_seconds: int = int(os.getenv("WUWA_CACHE_TTL_SECONDS", "86400"))
    request_timeout_seconds: float = float(os.getenv("WUWA_REQUEST_TIMEOUT", "20"))
    user_agent: str = os.getenv(
        "WUWA_USER_AGENT",
        "wuwa-companion-database/online-api (+https://github.com/Innocent254/wuwa-database-server)",
    )

settings = Settings()
