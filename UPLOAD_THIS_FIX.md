# Browser upload instructions

1. Extract `wuwa-mediawiki-source-fix.zip`.
2. Open `Innocent254/wuwa-database-server` on GitHub.
3. Click **Add file → Upload files**.
4. Open the extracted `wuwa-mediawiki-source-fix` folder.
5. Select and drag everything inside it into the GitHub upload area.
6. Commit directly to `main` with:

   `Use MediaWiki API for structured WuWa data`

7. Start a new workflow run; do not use **Re-run failed jobs**.
8. Use:
   - Mode: `dry-run`
   - Maximum records per dataset: `250`
   - Include images: disabled
   - Version override: blank

Do not use `publish` until the new artifact has been inspected.
