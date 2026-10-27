import json
from pathlib import Path
from typing import Any

from evals.builders.build_hint import LEVELS, build, build_split, select


def _query(identifier: str, source: str, category: str) -> dict[str, Any]:
    return {"id": identifier, "source": source, "category": category, "expected": "M001"}


def _queries() -> list[dict[str, Any]]:
    rows = [_query(f"hand/{n}", "handwritten", "fractions") for n in range(3)]
    for category in ("fractions", "factoring", "radicals"):
        for n in range(6):
            rows.append(_query(f"wrap/{category}{n}", "generated_wrapped", category))
            rows.append(_query(f"gen/{category}{n}", "generated", category))
    return rows


def test_all_handwritten_queries_are_kept_and_the_rest_fill_up_to_the_size() -> None:
    chosen = select(_queries(), 12)
    assert len(chosen) == 12
    assert {q["id"] for q in chosen} >= {"hand/0", "hand/1", "hand/2"}


def test_the_generated_ones_are_spread_over_categories_and_sources() -> None:
    generated = [q for q in select(_queries(), 15) if q["source"] != "handwritten"]
    assert {q["category"] for q in generated} == {"fractions", "factoring", "radicals"}
    assert {q["source"] for q in generated} == {"generated_wrapped", "generated"}


def test_a_size_above_what_exists_returns_everything_available() -> None:
    assert len(select(_queries(), 1000)) == len(_queries())


def test_the_choice_is_deterministic() -> None:
    assert select(_queries(), 10) == select(list(reversed(_queries())), 10)


def test_levels_are_dealt_in_turn() -> None:
    cases = build_split(_queries(), 16)
    counts = [sum(1 for case in cases if case["level"] == level) for level in range(1, 5)]
    assert counts == [4, 4, 4, 4]
    assert {case["level"] for case in cases} == set(range(1, LEVELS + 1))


def test_the_builder_writes_each_split_and_keeps_the_query_fields(tmp_path: Path) -> None:
    for split in ("dev", "test"):
        (tmp_path / split).mkdir()
        (tmp_path / split / "retrieve.jsonl").write_text(
            "".join(json.dumps(q) + "\n" for q in _queries()), encoding="utf-8"
        )
    built = build(tmp_path, ["dev"], 8)
    assert not (tmp_path / "test" / "hint.jsonl").exists()
    written = [json.loads(line) for line in (tmp_path / "dev" / "hint.jsonl").open()]
    assert written == sorted(built["dev"], key=lambda record: str(record["id"]))
    assert all(record["expected"] == "M001" and "level" in record for record in written)
