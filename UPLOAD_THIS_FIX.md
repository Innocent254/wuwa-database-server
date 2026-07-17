# Upload this redirect fix

Upload the contents of this folder to the root of `Innocent254/wuwa-database-server` using GitHub's **Add file → Upload files** page.

The upload replaces only:

- `wuwa_builder/sources/official.py`
- `tests/test_official_source.py`

Commit message:

`Handle official-site redirects during data discovery`

After committing, start a fresh **Build WuWa database manually** run in `dry-run` mode. Do not use **Re-run failed jobs**, because that would use the old commit.
