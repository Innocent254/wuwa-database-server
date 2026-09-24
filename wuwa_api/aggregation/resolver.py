from collections.abc import Iterable
from wuwa_api.models import EntityRecord
from wuwa_api.aggregation.normalizer import utc_now

# Field-level merge: the first non-empty value wins according to adapter priority.
# This is intentionally conservative in Phase 1; conflict policies can become
# field-specific once more source adapters are introduced.

def merge_records(records: Iterable[EntityRecord]) -> EntityRecord | None:
    ordered = sorted(records, key=lambda r: min(
        (p.confidence for p in r.provenance.values()), default=1.0
    ), reverse=True)
    if not ordered:
        return None

    base = ordered[0].model_copy(deep=True)
    for candidate in ordered[1:]:
        for field in ("description", "rarity", "element", "faction",
                      "weapon_type", "release_version", "release_date", "obtainable"):
            if getattr(base, field) is None and getattr(candidate, field) is not None:
                setattr(base, field, getattr(candidate, field))
        for key, value in candidate.stats.items():
            base.stats.setdefault(key, value)
        for key, value in candidate.images.items():
            base.images.setdefault(key, value)
        for key, value in candidate.extra.items():
            base.extra.setdefault(key, value)
        for key, value in candidate.provenance.items():
            base.provenance.setdefault(key, value)
        if not base.skills:
            base.skills = candidate.skills
        if not base.materials:
            base.materials = candidate.materials
    base.retrieved_at = utc_now()
    return base
