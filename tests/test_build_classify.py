import json
from pathlib import Path

import pytest

from evals.builders.build_classify import build

SUBJECTS = [
    "Prealgebra",
    "Algebra",
    "Intermediate Algebra",
    "Geometry",
    "Number Theory",
    "Counting & Probability",
    "Precalculus",
]


def _math_dir(tmp_path: Path, per_subject: int = 10) -> Path:
    rows = [
        {
            "unique_id": f"train/{subject}/{i}.json",
            "subject": subject,
            "level": 1 + i % 5,
            "problem": f"{subject} problem number {i}",
            "solution": "irrelevant",
        }
        for subject in SUBJECTS
        for i in range(per_subject)
    ]
    folder = tmp_path / "math"
    folder.mkdir(exist_ok=True)
    (folder / "train.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )
    (folder / "test.jsonl").write_text("", encoding="utf-8")
    return folder


def _read(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_each_split_has_the_same_number_of_problems_per_subject(tmp_path: Path) -> None:
    out = tmp_path / "datasets"
    build(_math_dir(tmp_path), out, per_subject=3, seed=0)
    for split in ("dev", "test"):
        records = _read(out / split / "classify.jsonl")
        assert len(records) == 21
        for subject in SUBJECTS:
            assert sum(1 for r in records if r["subject"] == subject) == 3


def test_dev_and_test_are_disjoint(tmp_path: Path) -> None:
    out = tmp_path / "datasets"
    build(_math_dir(tmp_path), out, per_subject=3, seed=0)
    dev = {str(r["id"]) for r in _read(out / "dev" / "classify.jsonl")}
    test = {str(r["id"]) for r in _read(out / "test" / "classify.jsonl")}
    assert dev.isdisjoint(test)


def test_the_labels_are_the_originals_and_the_build_is_reproducible(tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    build(_math_dir(tmp_path), first, per_subject=3, seed=1)
    build(_math_dir(tmp_path), second, per_subject=3, seed=1)
    for split in ("dev", "test"):
        name = Path(split) / "classify.jsonl"
        assert (first / name).read_text() == (second / name).read_text()
    for record in _read(first / "dev" / "classify.jsonl"):
        assert set(record) == {"id", "problem", "subject", "level"}
        assert record["level"] in {1, 2, 3, 4, 5}


def test_another_seed_picks_other_problems(tmp_path: Path) -> None:
    one, two = tmp_path / "a", tmp_path / "b"
    build(_math_dir(tmp_path), one, per_subject=3, seed=0)
    build(_math_dir(tmp_path), two, per_subject=3, seed=1)
    assert (one / "dev" / "classify.jsonl").read_text() != (
        two / "dev" / "classify.jsonl"
    ).read_text()


def test_identical_problem_texts_are_kept_once(tmp_path: Path) -> None:
    folder = _math_dir(tmp_path, per_subject=4)
    rows = [json.loads(line) for line in (folder / "train.jsonl").read_text().splitlines()]
    rows.append({**rows[0], "unique_id": "train/dup.json"})
    (folder / "train.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )
    out = tmp_path / "datasets"
    build(folder, out, per_subject=2, seed=0)
    problems = [
        str(r["problem"])
        for split in ("dev", "test")
        for r in _read(out / split / "classify.jsonl")
    ]
    assert len(problems) == len(set(problems))


def test_too_few_problems_for_a_subject_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="need 8"):
        build(_math_dir(tmp_path, per_subject=5), tmp_path / "out", per_subject=4, seed=0)


def test_the_report_counts_subjects_and_levels(tmp_path: Path) -> None:
    out = tmp_path / "datasets"
    build(_math_dir(tmp_path), out, per_subject=3, seed=0)
    report = json.loads((out / "review" / "classify_build_report.json").read_text(encoding="utf-8"))
    assert report["dev"]["n"] == 21 and report["test"]["by_subject"]["Algebra"] == 3
    assert sum(report["dev"]["by_level"].values()) == 21
