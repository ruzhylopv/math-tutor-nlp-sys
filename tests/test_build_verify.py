import json
from pathlib import Path

from evals.builders.build_verify import build, split_of
from tests.test_build_mine_math import SIMPLIFY_SOLUTION

TYPO_SOLUTION = r"\begin{align*}(x-r)(x-s) &= x^2 - (r+s) + rs \\ &= x^2 - (r+s)x + rs\end{align*}"


def _math_dir(tmp_path: Path) -> Path:
    rows = [
        {"unique_id": "train/algebra/1.json", "subject": "Algebra", "level": 3,
         "problem": "Simplify $(2x-5)(x+7) - (x+5)(2x-1)$.", "solution": SIMPLIFY_SOLUTION},
        {"unique_id": "train/algebra/2.json", "subject": "Algebra", "level": 2,
         "problem": "Simplify $(x-r)(x-s)$.", "solution": TYPO_SOLUTION},
        {"unique_id": "train/geometry/3.json", "subject": "Geometry", "level": 2,
         "problem": "Simplify $(x+1)^2$.", "solution": SIMPLIFY_SOLUTION},
        {"unique_id": "train/algebra/4.json", "subject": "Algebra", "level": 5,
         "problem": "Simplify $(x+1)^2$.", "solution": SIMPLIFY_SOLUTION},
        {"unique_id": "train/algebra/5.json", "subject": "Algebra", "level": 1,
         "problem": "If $f(x)=x+1$, find $f(2)$.", "solution": SIMPLIFY_SOLUTION},
    ]  # fmt: skip
    folder = tmp_path / "math"
    folder.mkdir(exist_ok=True)
    (folder / "train.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )
    (folder / "test.jsonl").write_text("", encoding="utf-8")
    return folder


def _read(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_build_writes_the_splits_and_the_review_file(tmp_path: Path) -> None:
    out = tmp_path / "datasets"
    counts = build(_math_dir(tmp_path), out, seed=0)
    dev = _read(out / "dev" / "verify_steps.jsonl")
    test = _read(out / "test" / "verify_steps.jsonl")
    review = _read(out / "review" / "verify_steps_disagreements.jsonl")
    assert (
        counts["mined positives"] == 7
    )  # only the simplify problem; others are filtered or review
    assert any(item["source"] == "handwritten" for item in dev + test)
    assert all(item["relation"] in {"equivalent", "not_valid", "implies", "narrows", "unparsable"}
               for item in dev + test)  # fmt: skip
    assert review and review[0]["checker_says"] == "not_valid"  # the typo'd chain
    assert review[0]["prev"] == "(x-r)(x-s)"


def test_the_filters_skip_other_subjects_levels_and_function_notation(tmp_path: Path) -> None:
    out = tmp_path / "datasets"
    build(_math_dir(tmp_path), out, seed=0)
    both = _read(out / "dev" / "verify_steps.jsonl") + _read(out / "test" / "verify_steps.jsonl")
    mined = [item for item in both if item["source"] != "handwritten"]
    ids = {str(item["provenance"]["unique_id"]) for item in mined}  # type: ignore[index]
    assert ids == {"train/algebra/1.json"}


def test_a_mined_problem_is_never_in_both_splits(tmp_path: Path) -> None:
    out = tmp_path / "datasets"
    build(_math_dir(tmp_path), out, seed=0)
    problems = {
        split: {
            str(item["problem"])
            for item in _read(out / split / "verify_steps.jsonl")
            if item["source"] != "handwritten"
        }
        for split in ("dev", "test")
    }
    assert problems["dev"].isdisjoint(problems["test"])


def test_generated_negatives_record_their_rule_and_seed(tmp_path: Path) -> None:
    out = tmp_path / "datasets"
    build(_math_dir(tmp_path), out, seed=3)
    both = _read(out / "dev" / "verify_steps.jsonl") + _read(out / "test" / "verify_steps.jsonl")
    generated = [item for item in both if item["source"] == "generated"]
    assert generated and all(item["relation"] == "not_valid" for item in generated)
    assert all({"rule", "seed"} <= set(item["provenance"]) for item in generated)  # type: ignore[arg-type]


def test_the_build_is_reproducible(tmp_path: Path) -> None:
    first, second = tmp_path / "a", tmp_path / "b"
    build(_math_dir(tmp_path), first, seed=0)
    build(_math_dir(tmp_path), second, seed=0)
    for split in ("dev", "test"):
        name = Path(split) / "verify_steps.jsonl"
        assert (first / name).read_text() == (second / name).read_text()


def test_split_of_is_stable_and_seed_dependent() -> None:
    assert split_of("a", 0) == split_of("a", 0)
    assert {split_of(str(i), 0) for i in range(50)} == {"dev", "test"}


def test_the_counts_add_up_to_the_records_written(tmp_path: Path) -> None:
    out = tmp_path / "datasets"
    counts = build(_math_dir(tmp_path), out, seed=0)
    written = sum(len(_read(out / split / "verify_steps.jsonl")) for split in ("dev", "test"))
    per_split = sum(value for key, value in counts.items() if key.startswith(("dev:", "test:")))
    assert per_split == written


def test_every_relation_is_in_both_splits_for_the_handwritten_cases(tmp_path: Path) -> None:
    out = tmp_path / "datasets"
    build(_math_dir(tmp_path), out, seed=0)
    for split in ("dev", "test"):
        relations = {
            item["relation"]
            for item in _read(out / split / "verify_steps.jsonl")
            if item["source"] == "handwritten"
        }
        assert relations == {"equivalent", "implies", "narrows", "not_valid", "unparsable"}


def test_the_build_report_has_the_agreement_numbers(tmp_path: Path) -> None:
    out = tmp_path / "datasets"
    counts = build(_math_dir(tmp_path), out, seed=0)
    report = json.loads((out / "review" / "verify_build_report.json").read_text(encoding="utf-8"))
    assert report["agreed"] == counts["mined positives"]
    assert report["disagreed"] == counts["mined pairs sent to review"] >= 1
    parseable = report["agreed"] + report["disagreed"]
    assert report["agreement_rate_on_parseable"] == report["agreed"] / parseable
