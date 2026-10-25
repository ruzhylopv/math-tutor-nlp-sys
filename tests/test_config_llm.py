import pytest

from tutor import config as config_module
from tutor.config import OPENROUTER_BASE_URL, Config, ConfigError, load_config
from tutor.llm import get_llm


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests independent of a developer's real .env."""
    monkeypatch.setattr(config_module, "load_dotenv", lambda: False)
    for name in ("OPENROUTER_API_KEY", "MODEL_NAME", "LEARNER_DB_PATH"):
        monkeypatch.delenv(name, raising=False)


def test_load_config_reads_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("MODEL_NAME", "some/model")
    monkeypatch.setenv("LEARNER_DB_PATH", "data/learner.db")
    assert load_config() == Config("k", "some/model", "data/learner.db")


def test_learner_db_path_is_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setenv("MODEL_NAME", "m")
    assert load_config().learner_db_path is None


def test_missing_required_settings_are_named(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_NAME", "m")
    with pytest.raises(ConfigError, match="OPENROUTER_API_KEY"):
        load_config()


def test_get_llm_targets_openrouter_without_a_network_call() -> None:
    llm = get_llm(Config("secret-key", "some/model"))
    assert llm.model_name == "some/model"
    assert llm.openai_api_base == OPENROUTER_BASE_URL
    assert "secret-key" not in repr(llm)
