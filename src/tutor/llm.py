"""The LLM client: an OpenAI-compatible chat model pointed at OpenRouter."""

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from tutor.config import OPENROUTER_BASE_URL, Config


def get_llm(config: Config) -> ChatOpenAI:
    """Build the chat model. Nodes call `.with_structured_output(<pydantic model>)` on it."""
    return ChatOpenAI(
        model=config.model_name,
        api_key=SecretStr(config.openrouter_api_key),
        base_url=OPENROUTER_BASE_URL,
        temperature=0,
    )
