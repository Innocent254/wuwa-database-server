# Third-Party Notices

Last updated: 23 July 2026

This repository uses components and data governed by licences separate from the
repository's MIT License. The version ranges below match `pyproject.toml` at the
date above. Installed transitive dependencies remain subject to the notices
distributed by their respective authors.

## Python runtime dependencies

| Package | Declared version | Licence / attribution |
| --- | --- | --- |
| aiohttp | `>=3.10,<4` | Apache License 2.0; aiohttp contributors |
| orjson | `>=3.10,<4` | Apache License 2.0 OR MIT; ijl/orjson contributors |
| Pillow | `>=10.4,<12` | HPND License; Pillow contributors |
| Playwright for Python | `>=1.45,<2` | Apache License 2.0; Microsoft Corporation |
| Pydantic | `>=2.8,<3` | MIT License; Pydantic contributors |
| Rich | `>=13.7,<15` | MIT License; Will McGugan and contributors |
| Typer | `>=0.12,<1` | MIT License; Sebastián Ramírez and contributors |

## Build and development dependencies

| Package | Declared version | Licence / attribution |
| --- | --- | --- |
| Hatchling | `>=1.25` | MIT License; Hatch contributors |
| pytest | `>=8.2,<9` | MIT License; pytest contributors |
| pytest-asyncio | `>=0.23,<1` | Apache License 2.0; pytest-asyncio contributors |
| Ruff | `>=0.6,<1` | MIT License; Astral Software Inc. and contributors |

## Standard licence notices

Apache License 2.0 components:

> Licensed under the Apache License, Version 2.0 (the “License”); you may not
> use these files except in compliance with the License. You may obtain a copy
> of the License at <https://www.apache.org/licenses/LICENSE-2.0>. Unless
> required by applicable law or agreed to in writing, software distributed
> under the License is distributed on an “AS IS” BASIS, WITHOUT WARRANTIES OR
> CONDITIONS OF ANY KIND, either express or implied.

MIT-licensed components:

> Permission is hereby granted, free of charge, to any person obtaining a copy
> of the applicable software and associated documentation files, to deal in the
> software without restriction, subject to preservation of the applicable
> copyright and permission notice. THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT
> WARRANTY OF ANY KIND.

The full licence texts, copyright notices, and any component-specific `NOTICE`
files supplied with installed distributions control over this summary and must
be retained where their licences require it. Pillow's HPND terms and orjson's
dual-licence terms must be preserved from their distributed licence files.

## Community-derived catalog content

The database builder currently obtains structured catalog records from the
Wuthering Waves Wiki through its public MediaWiki API.

- Source: <https://wutheringwaves.fandom.com/>
- API: <https://wutheringwaves.fandom.com/api.php>
- Applicable text licence: CC BY-SA 3.0, as declared by the source
- Licence: <https://creativecommons.org/licenses/by-sa/3.0/>

Generated packages must retain `ATTRIBUTION.md`, `DATA_LICENSE.md`, source page
URLs, retrieval timestamps, and revision metadata when available.

The wiki's text licence must not be assumed to cover uploaded images, video, or
other media. This project does not currently download or publish those files.

## Wuthering Waves

Wuthering Waves and all associated visual and audio assets are trademarks,
copyrights, or other intellectual property of Kuro Games and/or its licensors.
They are not licensed under this repository's MIT License.

No official game assets may be included in a public database package unless
written permission or another valid legal basis covering that exact
distribution has been verified.

## Corrections

Report missing attribution, licensing concerns, or takedown requests to
**chengoleinnocent@gmail.com**.
