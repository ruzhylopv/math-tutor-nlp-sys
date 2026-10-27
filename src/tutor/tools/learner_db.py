"""Learner DB (SQLite): what the tutor remembers about a student between problems.

Two tables: `attempts` (one row per finished problem) and `misconceptions_seen` (the misconceptions
diagnosed in that attempt). The orchestrator reaches it through `get_profile` and `record_attempt`.
Each call opens its own connection, so there is no module-level state.
"""

import sqlite3
from contextlib import closing

from tutor.config import ConfigError, load_config
from tutor.state import LearnerProfile, MisconceptionRecord

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    problem TEXT NOT NULL,
    topic TEXT,
    level INTEGER,
    turns INTEGER NOT NULL,
    hints_used INTEGER NOT NULL,
    solved INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS misconceptions_seen (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id INTEGER NOT NULL REFERENCES attempts(id),
    misconception_id TEXT NOT NULL,
    error_type TEXT,
    focus_step INTEGER
);
CREATE INDEX IF NOT EXISTS attempts_student ON attempts(student_id);
"""


def learner_db_path() -> str:
    """The DB file from `LEARNER_DB_PATH`; raise ConfigError when it is not set."""
    path = load_config().learner_db_path
    if path is None:
        raise ConfigError("Missing required setting: LEARNER_DB_PATH (see .env.example)")
    return path


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA)
    return conn


def get_profile(db_path: str, student_id: str) -> LearnerProfile:
    """Weak topics (topics with recorded mistakes, most first) and misconception counts."""
    with closing(_connect(db_path)) as conn:
        counts = dict(
            conn.execute(
                "SELECT m.misconception_id, COUNT(*) FROM misconceptions_seen m "
                "JOIN attempts a ON a.id = m.attempt_id WHERE a.student_id = ? "
                "GROUP BY m.misconception_id ORDER BY COUNT(*) DESC, m.misconception_id",
                (student_id,),
            ).fetchall()
        )
        topics = [
            row[0]
            for row in conn.execute(
                "SELECT a.topic FROM misconceptions_seen m JOIN attempts a ON a.id = m.attempt_id "
                "WHERE a.student_id = ? AND a.topic IS NOT NULL "
                "GROUP BY a.topic ORDER BY COUNT(*) DESC, a.topic",
                (student_id,),
            ).fetchall()
        ]
    return LearnerProfile(weak_topics=topics, misconception_counts=counts)


def record_attempt(
    db_path: str,
    student_id: str,
    problem: str,
    topic: str | None,
    level: int | None,
    turns: int,
    hints_used: int,
    solved: bool,
    misconceptions: list[MisconceptionRecord],
) -> int:
    """Insert one attempt and its misconceptions in one transaction; return the attempt id."""
    with closing(_connect(db_path)) as conn, conn:
        cursor = conn.execute(
            "INSERT INTO attempts (student_id, problem, topic, level, turns, hints_used, solved) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (student_id, problem, topic, level, turns, hints_used, int(solved)),
        )
        attempt_id = cursor.lastrowid
        assert attempt_id is not None
        conn.executemany(
            "INSERT INTO misconceptions_seen "
            "(attempt_id, misconception_id, error_type, focus_step) VALUES (?, ?, ?, ?)",
            [(attempt_id, m.misconception_id, m.error_type, m.focus_step) for m in misconceptions],
        )
    return attempt_id
