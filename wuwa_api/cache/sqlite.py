import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from wuwa_api.models import EntityRecord

class SQLiteCache:
    def __init__(self, path: str, ttl_seconds: int):
        self.path = Path(path)
        self.ttl_seconds = ttl_seconds
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    cached_at INTEGER NOT NULL,
                    PRIMARY KEY(entity_type, entity_id)
                )
            """)

    def get(self, entity_type: str, entity_id: str) -> EntityRecord | None:
        with sqlite3.connect(self.path) as db:
            row = db.execute(
                "SELECT payload, cached_at FROM entities WHERE entity_type=? AND entity_id=?",
                (entity_type, entity_id),
            ).fetchone()
        if not row:
            return None
        age = int(datetime.now(timezone.utc).timestamp()) - row[1]
        if age > self.ttl_seconds:
            return None
        return EntityRecord.model_validate_json(row[0])

    def put(self, record: EntityRecord) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute(
                """INSERT INTO entities(entity_type, entity_id, payload, cached_at)
                   VALUES(?,?,?,?)
                   ON CONFLICT(entity_type, entity_id)
                   DO UPDATE SET payload=excluded.payload, cached_at=excluded.cached_at""",
                (
                    record.entity_type,
                    record.id,
                    record.model_dump_json(),
                    int(datetime.now(timezone.utc).timestamp()),
                ),
            )
