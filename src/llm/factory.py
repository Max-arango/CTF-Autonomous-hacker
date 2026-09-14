"""LLM Provider Factory"""
from typing import Optional
from .base import LLMProvider, LLMConfig
from .nemotron import NemotronProvider
from .ollama import OllamaProvider
from .openai import OpenAIProvider
from ..config.settings import get_settings


class LLMProviderFactory:
    """Factory for creating LLM providers."""

    _providers = {
        "nemotron": NemotronProvider,
        "ollama": OllamaProvider,
        "openai": OpenAIProvider,
        "vllm": OpenAIProvider,  # vLLM is OpenAI-compatible
    }

    @classmethod
    def register_provider(cls, name: str, provider_class: type):
        """Register a new provider."""
        cls._providers[name] = provider_class

    @classmethod
    def create_provider(cls, provider_name: str, config: LLMConfig) -> LLMProvider:
        """Create a provider instance."""
        provider_class = cls._providers.get(provider_name.lower())
        if not provider_class:
            raise ValueError(f"Unknown provider: {provider_name}. Available: {list(cls._providers.keys())}")
        return provider_class(config)

    @classmethod
    def get_available_providers(cls) -> list:
        """Get list of available provider names."""
        return list(cls._providers.keys())


_provider_instance: Optional[LLMProvider] = None


async def get_llm_provider(
    provider_name: Optional[str] = None,
    config: Optional[LLMConfig] = None,
) -> LLMProvider:
    """Get or create the global LLM provider instance."""
    global _provider_instance

    settings = get_settings()

    if provider_name is None:
        provider_name = settings.llm.provider

    if config is None:
        config = LLMConfig(
            model=settings.llm.nemotron_model if provider_name == "nemotron" else settings.llm.openai_model,
            max_tokens=settings.llm.max_tokens,
            temperature=settings.llm.temperature,
            top_p=settings.llm.top_p,
            timeout=settings.llm.timeout,
        )

    if _provider_instance is None or _provider_instance.get_provider_name() != provider_name:
        if _provider_instance:
            await _provider_instance.close()
        _provider_instance = LLMProviderFactory.create_provider(provider_name, config)
        await _provider_instance.initialize()

    return _provider_instance


async def close_llm_provider():
    """Close the global LLM provider."""
    global _provider_instance
    if _provider_instance:
        await _provider_instance.close()
        _provider_instance = None