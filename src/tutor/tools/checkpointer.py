"""The persistent checkpointer: graph state saved to a SQLite file, keyed by `thread_id`."""

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver


def sqlite_checkpointer(path: str) -> SqliteSaver:
    """A saver on its own SQLite connection (`:memory:` is allowed for tests).

    The connection is opened with `check_same_thread=False` because a Streamlit rerun may use the
    graph from another thread; SqliteSaver serialises its own writes with a lock.
    """
    return SqliteSaver(sqlite3.connect(path, check_same_thread=False))
