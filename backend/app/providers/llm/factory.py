"""LLM provider factory."""

from app.core.config import settings
from app.providers.llm.openai_responses import OpenAIResponsesProvider


def create_llm_provider():
    provider = settings.llm_provider.strip().lower()
    if provider in {"", "disabled", "none"}:
        return None
    if provider == "openai":
        return OpenAIResponsesProvider(
            api_key=settings.llm_api_key or "",
            model=settings.llm_model,
            base_url=settings.llm_base_url or "",
        )
    raise ValueError(f"unsupported LLM_PROVIDER: {settings.llm_provider}")
