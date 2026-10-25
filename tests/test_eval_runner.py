import json
import re
import subprocess
from pathlib import Path

import pytest

from evals import runner
from evals.runner import (
    dataset_path,
    file_hash,
    git_hash,
    load_jsonl,
    parse_split,
    run_eval_stub,
    write_result,
)


def test_split_defaults_to_dev_and_accepts_test() -> None:
    assert parse_split("x", []) == "dev"
    assert parse_split("x", ["--split", "test"]) == "test"


def test_split_rejects_other_values() -> None:
    with pytest.raises(SystemExit):
        parse_split("x", ["--split", "train"])


def test_dataset_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(runner, "DATASETS_DIR", tmp_path)
    assert dataset_path("verify", "dev") == tmp_path / "dev" / "verify.jsonl"


def test_load_jsonl_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "d.jsonl"
    path.write_text('{"a": 1}\n\n{"a": 2}\n', encoding="utf-8")
    assert load_jsonl(path) == [{"a": 1}, {"a": 2}]


def test_git_hash_reads_the_repo() -> None:
    assert re.fullmatch(r"[0-9a-f]{7,40}", git_hash())


@pytest.mark.parametrize("error", [subprocess.CalledProcessError(128, "git"), FileNotFoundError()])
def test_git_hash_falls_back_instead_of_losing_the_metrics(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise error

    monkeypatch.setattr(runner.subprocess, "run", fail)
    assert git_hash() == "nogit"


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
    assert re.fullmatch(r"\d{8}T\d{6}Z_abc1234\.json", path.name)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["split"] == "dev"
    assert data["n_examples"] == 12
    assert data["metrics"] == {"accuracy": 0.5}
    assert data["model_name"] == "m"
    assert data["prompt_hash"] == file_hash(prompt)
    assert data["timestamp"].endswith("+00:00")


def test_deterministic_node_result_has_no_prompt_hash(tmp_path: Path) -> None:
    path = write_result("verify", "dev", 1, {"a": 1.0}, results_dir=tmp_path, commit="abc1234")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["prompt_hash"] is None
    assert data["model_name"] is None


def test_eval_stub_reports_a_missing_dataset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(runner, "DATASETS_DIR", tmp_path)
    caplog.set_level("INFO")
    run_eval_stub("verify", "M2", "desc", [])
    assert "missing" in caplog.text


def test_eval_stub_fails_loudly_once_a_dataset_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(runner, "DATASETS_DIR", tmp_path)
    (tmp_path / "dev").mkdir()
    (tmp_path / "dev" / "verify.jsonl").write_text("{}\n", encoding="utf-8")
    with pytest.raises(NotImplementedError, match="M2"):
        run_eval_stub("verify", "M2", "desc", [])
