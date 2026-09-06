"""Model layer package — exposes the provider factory."""

from __future__ import annotations

from ultron.config import Config, ConfigError, SUPPORTED_PROVIDERS
from ultron.llm.base import LLMProvider


def build_provider(config: Config) -> LLMProvider:
    """The single wiring point for the model layer.

    One implementation per supported provider. This is NOT a router — the
    provider is chosen by config (`ULTRON_PROVIDER`) and only one branch
    exists today. Adding a provider later means adding one branch here and
    one implementation module; no orchestration changes.
    """
    if config.provider == "gemini":
        from ultron.llm.gemini import GeminiProvider

        return GeminiProvider(
            api_key=config.gemini_api_key,
            model=config.model,
            system_prompt=config.system_prompt,
            temperature=config.temperature,
        )

    if config.provider == "nvidia":
        from ultron.llm.nvidia import NVIDIAProvider

        return NVIDIAProvider(
            api_key=config.nvidia_api_key,
            model=config.model,
            system_prompt=config.system_prompt,
            temperature=config.temperature,
        )

    if config.provider == "openrouter":
        from ultron.llm.openrouter import OpenRouterProvider

        return OpenRouterProvider(
            api_key=config.openrouter_api_key,
            model=config.model,
            system_prompt=config.system_prompt,
            temperature=config.temperature,
        )

    if config.provider == "grok":
        from ultron.llm.grok import GrokProvider

        return GrokProvider(
            api_key=config.grok_api_key,
            model=config.model,
            system_prompt=config.system_prompt,
            temperature=config.temperature,
        )

    if config.provider == "openai":
        from ultron.llm.openai_ import OpenAIProvider

        base_url = config.api_base_url or "https://api.openai.com/v1"
        return OpenAIProvider(
            api_key=config.openai_api_key,
            model=config.model,
            system_prompt=config.system_prompt,
            temperature=config.temperature,
            base_url=base_url,
        )

    if config.provider == "azure_openai":
        from ultron.llm.azure_openai import AzureOpenAIProvider

        return AzureOpenAIProvider(
            api_key=config.azure_openai_api_key,
            endpoint=config.azure_openai_endpoint,
            deployment=config.azure_openai_deployment,
            version=config.azure_openai_version,
            system_prompt=config.system_prompt,
            temperature=config.temperature,
        )

    if config.provider == "anthropic":
        from ultron.llm.anthropic import AnthropicProvider

        base_url = config.api_base_url or "https://api.anthropic.com/v1"
        return AnthropicProvider(
            api_key=config.anthropic_api_key,
            model=config.model,
            system_prompt=config.system_prompt,
            temperature=config.temperature,
            base_url=base_url,
        )

    if config.provider == "cohere":
        from ultron.llm.cohere import CohereProvider

        base_url = config.api_base_url or "https://api.cohere.ai/v1"
        return CohereProvider(
            api_key=config.cohere_api_key,
            model=config.model,
            system_prompt=config.system_prompt,
            temperature=config.temperature,
            base_url=base_url,
        )

    if config.provider == "mistral":
        from ultron.llm.mistral import MistralProvider

        base_url = config.api_base_url or "https://api.mistral.ai/v1"
        return MistralProvider(
            api_key=config.mistral_api_key,
            model=config.model,
            system_prompt=config.system_prompt,
            temperature=config.temperature,
            base_url=base_url,
        )

    if config.provider == "perplexity":
        from ultron.llm.perplexity import PerplexityProvider

        base_url = config.api_base_url or "https://api.perplexity.ai"
        return PerplexityProvider(
            api_key=config.perplexity_api_key,
            model=config.model,
            system_prompt=config.system_prompt,
            temperature=config.temperature,
            base_url=base_url,
        )

    if config.provider == "bedrock":
        from ultron.llm.bedrock import BedrockProvider

        return BedrockProvider(
            region=config.bedrock_region,
            access_key=config.bedrock_access_key,
            secret_key=config.bedrock_secret_key,
            model=config.model,
            system_prompt=config.system_prompt,
            temperature=config.temperature,
        )

    raise ConfigError(
        f"ULTRON_PROVIDER={config.provider!r} is not supported. "
        f"Supported: {', '.join(SUPPORTED_PROVIDERS)}."
    )


__all__ = ["LLMProvider", "build_provider", "ConfigError"]
