import json
from pathlib import Path

import pytest

from evals.runner import (
    dataset_path,
    file_hash,
    load_jsonl,
    parse_split,
    write_result,
)


def test_split_defaults_to_dev_and_accepts_test() -> None:
    assert parse_split("x", []) == "dev"
    assert parse_split("x", ["--split", "test"]) == "test"


def test_split_rejects_other_values() -> None:
    with pytest.raises(SystemExit):
        parse_split("x", ["--split", "train"])


def test_dataset_path(tmp_path: Path) -> None:
    assert dataset_path("verify", "dev", tmp_path) == tmp_path / "dev" / "verify.jsonl"


def test_load_jsonl_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "d.jsonl"
    path.write_text('{"a": 1}\n\n{"a": 2}\n', encoding="utf-8")
    assert load_jsonl(path) == [{"a": 1}, {"a": 2}]


def test_write_result_has_the_fields_the_run_eval_skill_requires(tmp_path: Path) -> None:
    prompt = tmp_path / "p.md"
    prompt.write_text("Role: x", encoding="utf-8")
    path = write_result(
        "verify",
        "dev",
        12,
        {"accuracy": 0.5},
        model_name="m",
        prompt_path=prompt,
        results_dir=tmp_path / "results",
        commit="abc1234",
    )
    assert path.parent == tmp_path / "results" / "verify"
    assert path.name.endswith("_abc1234.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["split"] == "dev" and data["n_examples"] == 12
    assert data["metrics"] == {"accuracy": 0.5} and data["model_name"] == "m"
    assert data["prompt_hash"] == file_hash(prompt)


def test_deterministic_node_result_has_no_prompt_hash(tmp_path: Path) -> None:
    path = write_result("verify", "dev", 1, {"a": 1.0}, results_dir=tmp_path, commit="abc1234")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["prompt_hash"] is None and data["model_name"] is None
