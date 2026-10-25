"""Configuration read from the environment (and .env). No secrets live in code."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class ConfigError(RuntimeError):
    """A required setting is missing."""


@dataclass(frozen=True)
class Config:
    openrouter_api_key: str
    model_name: str
    learner_db_path: str | None = None


def load_config() -> Config:
    """Read settings from .env / the environment. Raise ConfigError if a required one is missing."""
    load_dotenv()
    missing = [name for name in ("OPENROUTER_API_KEY", "MODEL_NAME") if not os.environ.get(name)]
    if missing:
        raise ConfigError(f"Missing required settings: {', '.join(missing)} (see .env.example)")
    return Config(
        openrouter_api_key=os.environ["OPENROUTER_API_KEY"],
        model_name=os.environ["MODEL_NAME"],
        learner_db_path=os.environ.get("LEARNER_DB_PATH") or None,
    )
