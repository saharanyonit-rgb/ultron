"""Model layer: the single, swappable provider abstraction.

V1 wires up exactly ONE implementation (Google Gemini). The interface below
is the seam where additional providers slot in later — the rest of Ultron
only ever talks to `LLMProvider`.

Providers are sessionful: they own their native conversation buffer. The
agent loop calls `complete()` to send a turn (passing new text, or `None`
to continue after `feed_tool_results()`), and `feed_tool_results()` to hand
back the outcomes of the last round of tool calls.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:  # type-only import — avoids any circular import with tools
    from ultron.tools.base import ToolSpec


@dataclass(frozen=True)
class ToolCall:
    """A tool invocation requested by the model."""

    id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    """The outcome of executing a `ToolCall`, handed back to the model."""

    call: ToolCall
    output: str  # serialized JSON


@dataclass(frozen=True)
class ProviderResult:
    """Normalized model output."""

    text: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)


class LLMProvider(ABC):
    """Abstract interface every provider implementation must satisfy."""

    name: str

    @abstractmethod
    def complete(self, text: Optional[str], tools: List["ToolSpec"]) -> ProviderResult:
        """Send the current conversation to the model.

        `text` is a new user message to append (or `None` to just continue
        the existing conversation, e.g. after feeding tool results back).
        `tools` are the currently-available tool declarations.

        Raises:
            AuthenticationError: if the provider rejects the API key.
            TimeoutError: if the request exceeds the time budget.
            ProviderError: for any other provider-level failure.
        """

    @abstractmethod
    def feed_tool_results(self, results: List[ToolResult]) -> None:
        """Append the results of the most recent round of tool calls."""

    def health_check(self) -> bool:
        """Return True if the provider is reachable and authenticated.

        The default implementation returns True; providers that can
        cheaply verify connectivity should override this.
        """
        return True

    def supports_vision(self) -> bool:
        """Return True if this provider can analyze images."""
        return False

    def analyze_image(self, image_path: str, prompt: str) -> str:
        """Analyze an image with a vision-capable LLM.

        Args:
            image_path: Path to the image file.
            prompt: Question or analysis request about the image.

        Returns:
            Text analysis of the image.

        Raises:
            NotImplementedError: if the provider does not support vision.
        """
        raise NotImplementedError(f"{self.name} does not support vision analysis")
