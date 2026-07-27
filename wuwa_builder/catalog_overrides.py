from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from wuwa_builder.models import WikiEntityRecord

LOGGER = logging.getLogger(__name__)

OVERRIDES_PATH = Path(__file__).with_name("catalog_overrides.json")
PROTECTED_FIELDS = {
    "id",
    "name",
    "entity_type",
    "source",
    "attribution_url",
    "revision_id",
    "revision_timestamp",
    "license_name",
    "license_url",
}


class CatalogOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: str
    name: str = Field(min_length=1)
    verification_urls: list[HttpUrl] = Field(min_length=1)
    required_fields: list[str] = Field(default_factory=list)
    fields: dict[str, Any]


class CatalogOverrideFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    records: list[CatalogOverride]


@lru_cache(maxsize=1)
def load_catalog_overrides(path: Path = OVERRIDES_PATH) -> CatalogOverrideFile:
    payload = json.loads(path.read_text(encoding="utf-8"))
    overrides = CatalogOverrideFile.model_validate(payload)

    seen: set[tuple[str, str]] = set()
    model_fields = set(WikiEntityRecord.model_fields)
    for override in overrides.records:
        key = (override.entity_type.casefold(), override.name.casefold())
        if key in seen:
            raise ValueError(f"Duplicate catalog override: {override.entity_type}/{override.name}")
        seen.add(key)

        protected = PROTECTED_FIELDS.intersection(override.fields)
        if protected:
            raise ValueError(
                f"Catalog override {override.name} changes protected fields: "
                f"{', '.join(sorted(protected))}"
            )

        unknown = set(override.fields).difference(model_fields)
        if unknown:
            raise ValueError(
                f"Catalog override {override.name} uses unknown fields: "
                f"{', '.join(sorted(unknown))}"
            )

        invalid_required = set(override.required_fields).difference(override.fields)
        if invalid_required:
            raise ValueError(
                f"Catalog override {override.name} requires fields it does not provide: "
                f"{', '.join(sorted(invalid_required))}"
            )

    return overrides


def apply_catalog_overrides(
    datasets: dict[str, list[WikiEntityRecord]],
    override_file: CatalogOverrideFile | None = None,
) -> dict[str, list[WikiEntityRecord]]:
    """Apply reviewed record corrections without changing record identity or attribution."""

    overrides = override_file or load_catalog_overrides()
    by_key = {
        (override.entity_type.casefold(), override.name.casefold()): override
        for override in overrides.records
    }

    applied: set[tuple[str, str]] = set()
    output: dict[str, list[WikiEntityRecord]] = {}
    for dataset_name, records in datasets.items():
        updated_records: list[WikiEntityRecord] = []
        for record in records:
            key = (record.entity_type.casefold(), record.name.casefold())
            override = by_key.get(key)
            if override is None:
                updated_records.append(record)
                continue

            values = record.model_dump(mode="python")
            values.update(override.fields)
            updated = WikiEntityRecord.model_validate(values)
            _assert_required_details(updated, override)
            updated_records.append(updated)
            applied.add(key)
            LOGGER.info(
                "Applied reviewed catalog details for %s/%s",
                record.entity_type,
                record.name,
            )
        output[dataset_name] = updated_records

    missing = sorted(
        f"{entity_type}/{name}"
        for entity_type, name in set(by_key).difference(applied)
    )
    if missing:
        LOGGER.warning(
            "Reviewed overrides were not present in this bounded catalog run: %s",
            ", ".join(missing),
        )

    return output


def _assert_required_details(record: WikiEntityRecord, override: CatalogOverride) -> None:
    missing: list[str] = []
    for field_name in override.required_fields:
        value = getattr(record, field_name)
        if value is None or value == "" or value == [] or value == {}:
            missing.append(field_name)
    if missing:
        raise ValueError(
            f"Reviewed catalog record {record.entity_type}/{record.name} is incomplete: "
            f"{', '.join(missing)}"
        )
