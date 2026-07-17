# Upload this fix

Upload the contents of this folder to the root of `wuwa-database-server`.

This replaces:

- `wuwa_builder/sources/fandom.py`
- `tests/test_fandom_source.py`

Commit message:

`Handle unavailable robots.txt under RFC 9309`

Then run a fresh dry-run workflow with images disabled.
