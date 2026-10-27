import json
from pathlib import Path
from typing import Any

import pytest

from evals.builders.build_retrieve import _split, build
from evals.builders.handwritten_queries import HANDWRITTEN, UNREACHABLE
from tutor.state import Step, TutorState
from tutor.tools.catalogue import load_catalogue

IDS = {entry.id for entry in load_catalogue()}


def _read(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


Built = tuple[Path, dict[str, list[dict[str, Any]]]]


def _build(tmp_path: Path) -> Built:
    out = tmp_path / "datasets"
    build(out, per_rule=2, wrapped_per_rule=1, seed=0)
    return out, {s: _read(out / s / "retrieve.jsonl") for s in ("dev", "test")}


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Built:
    """One build shared by the tests that only read it (a build solves hundreds of equations)."""
    return _build(tmp_path_factory.mktemp("retrieve"))


def test_entries_alternate_between_dev_and_test_so_none_is_in_both(built: Built) -> None:
    _, splits = built
    entries = {s: {r["expected"] for r in records} for s, records in splits.items()}
    assert entries["dev"].isdisjoint(entries["test"])
    assert all(_split(e) == "dev" for e in entries["dev"])
    assert all(_split(e) == "test" for e in entries["test"])


def test_every_catalogue_entry_has_queries_in_exactly_one_split(built: Built) -> None:
    out, splits = built
    covered = {r["expected"] for records in splits.values() for r in records}
    assert covered == IDS - UNREACHABLE
    report = json.loads((out / "review" / "retrieve_build_report.json").read_text("utf-8"))
    assert report["entries_without_any_query"] == []
    assert report["unreachable_entries"] == sorted(UNREACHABLE)


def test_both_splits_cover_every_category(built: Built) -> None:
    _, splits = built
    categories = {e.category for e in load_catalogue()}
    for records in splits.values():
        assert {r["category"] for r in records} == categories


def test_a_generated_query_is_a_state_that_retrieve_can_read(built: Built) -> None:
    _, splits = built
    for records in splits.values():
        for record in (r for r in records if r["source"].startswith("generated")):
            assert record["focus_step"] == 1 and len(record["steps"]) == 1
            assert record["error_type"] == "algebraic_transformation"
            state: TutorState = {
                "problem": record["problem"],
                "student_steps": [Step(claim=s["claim"]) for s in record["steps"]],
                "focus_step": record["focus_step"],
            }
            assert state["student_steps"][0].claim != state["problem"]


def test_generated_queries_per_entry_are_distinct(built: Built) -> None:
    _, splits = built
    for records in splits.values():
        pairs = [
            (r["expected"], r["problem"], r["steps"][0]["claim"])
            for r in records
            if r["source"].startswith("generated")
        ]
        assert len(set(pairs)) == len(pairs)


def test_the_build_is_reproducible(built: Built, tmp_path: Path) -> None:
    first = built[0]
    second, _ = _build(tmp_path)
    for split in ("dev", "test"):
        name = f"{split}/retrieve.jsonl"
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_the_hand_written_queries_are_well_formed() -> None:
    assert len(HANDWRITTEN) >= 35
    seen = set()
    for query in HANDWRITTEN:
        assert query["expected"] in IDS
        assert 1 <= query["focus_step"] <= len(query["steps"])
        assert query["error_type"] in {
            "algebraic_transformation",
            "omission_extraneous_root",
            "reasoning_result_mismatch",
        }
        key = (query["problem"], query["steps"][query["focus_step"] - 1]["claim"])
        assert key not in seen
        seen.add(key)
    examples = {entry.example for entry in load_catalogue()}
    for query in HANDWRITTEN:
        line = f"{query['problem']} -> {query['steps'][query['focus_step'] - 1]['claim']}"
        assert line not in examples  # the queries do not copy the catalogue's examples


def test_wrapped_queries_exist_and_are_marked(built: Built) -> None:
    _, splits = built
    for records in splits.values():
        wrapped = [r for r in records if r["source"] == "generated_wrapped"]
        assert len(wrapped) > 20
        assert all(r["id"].startswith("wrap/") for r in wrapped)


def test_the_unreachable_entries_have_no_query_and_are_real_entries(built: Built) -> None:
    _, splits = built
    assert UNREACHABLE <= IDS
    queried = {r["expected"] for records in splits.values() for r in records}
    assert queried.isdisjoint(UNREACHABLE)
    assert all(q["expected"] not in UNREACHABLE for q in HANDWRITTEN)
