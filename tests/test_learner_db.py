"""Learner DB tools on a temp SQLite file."""

from pathlib import Path

import pytest

from tutor.config import ConfigError
from tutor.state import MisconceptionRecord
from tutor.tools import learner_db


def _record(db: str, student: str, topic: str | None, ids: list[str], solved: bool = True) -> int:
    seen = [
        MisconceptionRecord(misconception_id=i, error_type="algebraic_transformation") for i in ids
    ]
    return learner_db.record_attempt(db, student, "3(x+2)=15", topic, 1, 3, 1, solved, seen)


def test_empty_profile_for_unknown_student(tmp_path: Path) -> None:
    profile = learner_db.get_profile(str(tmp_path / "l.db"), "nobody")
    assert profile.weak_topics == []
    assert profile.misconception_counts == {}


def test_counts_accumulate_across_attempts(tmp_path: Path) -> None:
    db = str(tmp_path / "l.db")
    _record(db, "s1", "Algebra", ["M001"])
    _record(db, "s1", "Algebra", ["M001", "M002"])
    profile = learner_db.get_profile(db, "s1")
    assert profile.misconception_counts == {"M001": 2, "M002": 1}
    assert profile.weak_topics == ["Algebra"]


def test_profiles_are_per_student(tmp_path: Path) -> None:
    db = str(tmp_path / "l.db")
    _record(db, "s1", "Algebra", ["M001"])
    assert learner_db.get_profile(db, "s2").misconception_counts == {}


def test_weak_topics_ordered_by_mistakes_and_skip_clean_attempts(tmp_path: Path) -> None:
    db = str(tmp_path / "l.db")
    _record(db, "s1", "Prealgebra", ["M001"])
    _record(db, "s1", "Algebra", ["M002"])
    _record(db, "s1", "Algebra", ["M003"])
    _record(db, "s1", "Intermediate Algebra", [])
    assert learner_db.get_profile(db, "s1").weak_topics == ["Algebra", "Prealgebra"]


def test_record_attempt_returns_increasing_ids_and_allows_no_topic(tmp_path: Path) -> None:
    db = str(tmp_path / "l.db")
    first = _record(db, "s1", None, [])
    second = _record(db, "s1", None, ["M001"], solved=False)
    assert second > first
    assert learner_db.get_profile(db, "s1").weak_topics == []


def test_path_must_be_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("MODEL_NAME", "m")
    monkeypatch.delenv("LEARNER_DB_PATH", raising=False)
    with pytest.raises(ConfigError):
        learner_db.learner_db_path()
