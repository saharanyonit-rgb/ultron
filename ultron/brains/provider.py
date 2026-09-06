"""Brain Provider Factory - creates LLM providers for specialized brains.

This module provides a factory for creating LLM providers based on configuration.
It supports multiple providers (Gemini, OpenRouter) and model configurations
without hardcoding model IDs.
"""

from __future__ import annotations

import logging
from typing import Optional

from ultron.config import BrainModelConfig, LLMConfig
from ultron.llm.base import LLMProvider
from ultron.llm.gemini import GeminiProvider
from ultron.llm.grok import GrokProvider
from ultron.llm.openrouter import OpenRouterProvider

logger = logging.getLogger("ultron.brains.provider")


class BrainProviderFactory:
    """Factory for creating LLM providers for specialized brains."""

    def __init__(self, llm_config: LLMConfig) -> None:
        self._llm_config = llm_config

    def create_provider(
        self,
        model_config: BrainModelConfig,
        system_prompt: Optional[str] = None,
    ) -> LLMProvider:
        """Create an LLM provider based on brain model configuration.

        Args:
            model_config: The brain-specific model configuration
            system_prompt: Optional system prompt override

        Returns:
            An LLMProvider instance

        Raises:
            ValueError: If provider is not supported
        """
        provider = model_config.provider.lower()
        model = model_config.model
        temperature = model_config.temperature

        if provider == "gemini":
            return self._create_gemini_provider(model, temperature, system_prompt)
        elif provider == "openrouter":
            return self._create_openrouter_provider(model, temperature, system_prompt)
        elif provider == "openai":
            return self._create_openai_provider(model, temperature, system_prompt)
        elif provider == "nvidia":
            return self._create_nvidia_provider(model, temperature, system_prompt)
        elif provider == "anthropic":
            return self._create_anthropic_provider(model, temperature, system_prompt)
        elif provider == "grok":
            return self._create_grok_provider(model, temperature, system_prompt)
        else:
            logger.warning("Unknown provider '%s', falling back to gemini", provider)
            return self._create_gemini_provider(model, temperature, system_prompt)

    def _create_gemini_provider(
        self,
        model: str,
        temperature: float,
        system_prompt: Optional[str],
    ) -> GeminiProvider:
        api_key = self._llm_config.gemini_api_key
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not configured")
        return GeminiProvider(
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            temperature=temperature,
        )

    def _create_openrouter_provider(
        self,
        model: str,
        temperature: float,
        system_prompt: Optional[str],
    ) -> OpenRouterProvider:
        api_key = self._llm_config.openrouter_api_key
        if not api_key:
            raise ValueError("ULTRON_OPENROUTER_API_KEY is not configured")
        return OpenRouterProvider(
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            temperature=temperature,
        )

    def _create_openai_provider(
        self,
        model: str,
        temperature: float,
        system_prompt: Optional[str],
    ) -> OpenRouterProvider:
        api_key = self._llm_config.openai_api_key
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not configured")
        return OpenRouterProvider(
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            temperature=temperature,
        )

    def _create_nvidia_provider(
        self,
        model: str,
        temperature: float,
        system_prompt: Optional[str],
    ) -> OpenRouterProvider:
        api_key = self._llm_config.nvidia_api_key
        if not api_key:
            raise ValueError("ULTRON_NVIDIA_API_KEY is not configured")
        return OpenRouterProvider(
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            temperature=temperature,
        )

    def _create_anthropic_provider(
        self,
        model: str,
        temperature: float,
        system_prompt: Optional[str],
    ) -> OpenRouterProvider:
        api_key = self._llm_config.anthropic_api_key
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not configured")
        return OpenRouterProvider(
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            temperature=temperature,
        )

    def _create_grok_provider(
        self,
        model: str,
        temperature: float,
        system_prompt: Optional[str],
    ) -> GrokProvider:
        api_key = self._llm_config.grok_api_key
        if not api_key:
            raise ValueError("ULTRON_GROK_API_KEY is not configured")
        return GrokProvider(
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            temperature=temperature,
        )

    def create_provider_with_fallback(
        self,
        primary_config: BrainModelConfig,
        fallback_config: BrainModelConfig,
        system_prompt: Optional[str] = None,
    ) -> LLMProvider:
        """Create a provider with automatic fallback.

        If the primary provider fails, the fallback will be tried.
        """
        try:
            return self.create_provider(primary_config, system_prompt)
        except Exception as primary_error:
            logger.warning(
                "Primary provider %s failed: %s, trying fallback %s",
                primary_config.provider,
                primary_error,
                fallback_config.provider,
            )
            try:
                return self.create_provider(fallback_config, system_prompt)
            except Exception as fallback_error:
                logger.error(
                    "Both providers failed. Primary: %s, Fallback: %s",
                    primary_error,
                    fallback_error,
                )
                raise ValueError(
                    f"Both primary ({primary_config.provider}) and "
                    f"fallback ({fallback_config.provider}) providers failed"
                ) from primary_error


__all__ = ["BrainProviderFactory"]
