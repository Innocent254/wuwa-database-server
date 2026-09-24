from datetime import datetime, timezone
from typing import Any

def normalize_id(value: str) -> str:
    return "-".join(value.strip().lower().split())

def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

def utc_now() -> datetime:
    return datetime.now(timezone.utc)
