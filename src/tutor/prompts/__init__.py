"""Prompts live here as one Markdown file per LLM node, loaded by name."""

from pathlib import Path

_DIR = Path(__file__).resolve().parent


def load_prompt(name: str) -> str:
    """The text of `<name>.md` in this folder. Never write a prompt inline in Python."""
    if Path(name).name != name or not name.isidentifier():
        raise ValueError(f"not a prompt name: {name!r}")
    return (_DIR / f"{name}.md").read_text(encoding="utf-8")
