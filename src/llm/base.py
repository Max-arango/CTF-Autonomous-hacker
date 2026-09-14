"""Base LLM Provider Interface"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, AsyncIterator
from enum import Enum


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class LLMMessage:
    role: MessageRole
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMConfig:
    model: str
    max_tokens: int = 8192
    temperature: float = 0.3
    top_p: float = 0.9
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    timeout: int = 60
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    content: str
    role: MessageRole = MessageRole.ASSISTANT
    tool_calls: Optional[List[Dict[str, Any]]] = None
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    model: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self._client = None

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the provider client."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the provider client."""
        pass

    @abstractmethod
    async def complete(
        self,
        messages: List[LLMMessage],
        config: Optional[LLMConfig] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        """Complete a chat conversation."""
        pass

    @abstractmethod
    async def stream_complete(
        self,
        messages: List[LLMMessage],
        config: Optional[LLMConfig] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[LLMResponse]:
        """Stream a chat completion."""
        pass

    @abstractmethod
    async def count_tokens(self, messages: List[LLMMessage]) -> int:
        """Count tokens in messages."""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Get the model name."""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the provider name."""
        pass

    def _merge_config(self, config: Optional[LLMConfig]) -> LLMConfig:
        """Merge provided config with default config."""
        if config is None:
            return self.config

        return LLMConfig(
            model=config.model or self.config.model,
            max_tokens=config.max_tokens or self.config.max_tokens,
            temperature=config.temperature if config.temperature is not None else self.config.temperature,
            top_p=config.top_p if config.top_p is not None else self.config.top_p,
            frequency_penalty=config.frequency_penalty if config.frequency_penalty is not None else self.config.frequency_penalty,
            presence_penalty=config.presence_penalty if config.presence_penalty is not None else self.config.presence_penalty,
            timeout=config.timeout or self.config.timeout,
            extra_params={**self.config.extra_params, **config.extra_params},
        )