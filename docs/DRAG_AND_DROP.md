# Phase 1.1 Drag-and-Drop Upload

Upload the ZIP contents into the repository root.

### Replace

- `pyproject.toml`
- `wuwa_api/models.py`
- `wuwa_api/cache/sqlite.py`
- `wuwa_api/sources/fandom.py`
- `wuwa_api/service.py`
- `docs/ONLINE_DATA_ARCHITECTURE.md`

### Add

- `tests/api/test_service.py`

### Keep

Do not delete `wuwa_builder/`, the existing catalog data, release workflow,
legal/licensing files, or existing API scaffold files.

After upload:

```bash
pip install -e ".[dev]"
pytest -q
uvicorn wuwa_api.api:app --reload
```
