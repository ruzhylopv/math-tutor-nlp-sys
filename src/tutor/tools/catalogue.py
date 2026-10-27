"""Load the hand-written misconception catalogue (src/tutor/data/misconceptions.json)."""

import json
from functools import lru_cache
from pathlib import Path

from tutor.state import CatalogueEntry

CATALOGUE_PATH = Path(__file__).resolve().parents[1] / "data" / "misconceptions.json"


@lru_cache(maxsize=1)
def load_catalogue() -> tuple[CatalogueEntry, ...]:
    """All entries, validated. Raises ValueError on a duplicate id."""
    rows = json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))
    entries = tuple(CatalogueEntry.model_validate(row) for row in rows)
    ids = [entry.id for entry in entries]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate misconception id in the catalogue")
    return entries
