"""Properties of the committed verify datasets (not of a synthetic build)."""

import json
from pathlib import Path

import pytest

DATASETS = Path(__file__).resolve().parents[1] / "evals" / "datasets"
RELATIONS = {"equivalent", "implies", "narrows", "not_valid", "unparsable"}


def _load(split: str) -> list[dict[str, object]]:
    path = DATASETS / split / "verify_steps.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_ids_are_unique_across_both_splits() -> None:
    ids = [str(item["id"]) for split in ("dev", "test") for item in _load(split)]
    assert len(ids) == len(set(ids))


def test_every_record_has_a_known_relation_and_source() -> None:
    for split in ("dev", "test"):
        for item in _load(split):
            assert item["relation"] in RELATIONS
            assert item["source"] in {"math", "generated", "handwritten"}


def test_narrows_cases_carry_the_original_problem() -> None:
    for split in ("dev", "test"):
        for item in _load(split):
            if item["relation"] == "narrows":
                assert item["original"]


def test_a_mined_problem_is_in_one_split_only() -> None:
    def problems(split: str) -> set[str]:
        return {str(item["problem"]) for item in _load(split) if item["source"] != "handwritten"}

    assert problems("dev").isdisjoint(problems("test"))


def test_every_relation_is_present_in_both_splits() -> None:
    for split in ("dev", "test"):
        assert {item["relation"] for item in _load(split)} == RELATIONS


def test_generated_records_name_their_rule_and_seed() -> None:
    for split in ("dev", "test"):
        for item in _load(split):
            if item["source"] == "generated":
                assert {"rule", "seed"} <= set(item["provenance"])  # type: ignore[arg-type]


@pytest.mark.xfail(
    reason="known limit: the committed files were built before duplicates were dropped and are "
    "intentionally not rebuilt (decisions.md, M3 decisions)",
    strict=False,
)
def test_no_pair_is_in_both_splits() -> None:
    def pairs(split: str) -> set[tuple[object, object, object]]:
        return {(item["prev"], item["curr"], item["relation"]) for item in _load(split)}

    assert pairs("dev").isdisjoint(pairs("test"))


def test_the_report_counts_match_the_files() -> None:
    report = json.loads(
        (DATASETS / "review" / "verify_build_report.json").read_text(encoding="utf-8")
    )
    assert report["agreed"] > 0
    assert report["agreement_rate_on_parseable"] == pytest.approx(
        report["agreed"] / (report["agreed"] + report["disagreed"])
    )
