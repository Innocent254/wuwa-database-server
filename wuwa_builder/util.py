from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_id(prefix: str, value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    suffix = hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{normalized[:60]}-{suffix}"


def safe_extension(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix in {".png", ".jpg", ".jpeg", ".webp"} else ".img"
