"""Ollama LLM Provider"""
import os
from typing import List, Optional, Dict, Any, AsyncIterator
import httpx
from .base import LLMProvider, LLMMessage, LLMResponse, LLMConfig, MessageRole


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self._client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        """Initialize the HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.config.timeout,
        )

    async def close(self) -> None:
        """Close the client."""
        if self._client:
            await self._client.aclose()

    async def complete(
        self,
        messages: List[LLMMessage],
        config: Optional[LLMConfig] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        """Complete a chat conversation."""
        if not self._client:
            await self.initialize()

        merged_config = self._merge_config(config)
        ollama_messages = self._convert_messages(messages)

        payload = {
            "model": merged_config.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "num_predict": merged_config.max_tokens,
                "temperature": merged_config.temperature,
                "top_p": merged_config.top_p,
            },
        }

        if tools:
            payload["tools"] = tools

        try:
            response = await self._client.post("/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            return self._parse_response(data)
        except Exception as e:
            raise RuntimeError(f"Ollama completion failed: {e}")

    async def stream_complete(
        self,
        messages: List[LLMMessage],
        config: Optional[LLMConfig] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[LLMResponse]:
        """Stream a chat completion."""
        if not self._client:
            await self.initialize()

        merged_config = self._merge_config(config)
        ollama_messages = self._convert_messages(messages)

        payload = {
            "model": merged_config.model,
            "messages": ollama_messages,
            "stream": True,
            "options": {
                "num_predict": merged_config.max_tokens,
                "temperature": merged_config.temperature,
                "top_p": merged_config.top_p,
            },
        }

        if tools:
            payload["tools"] = tools

        try:
            async with self._client.stream("POST", "/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip():
                        import json
                        data = json.loads(line)
                        if "message" in data and data["message"].get("content"):
                            yield LLMResponse(
                                content=data["message"]["content"],
                                role=MessageRole.ASSISTANT,
                                finish_reason="stop" if data.get("done") else None,
                                model=data.get("model"),
                            )
        except Exception as e:
            raise RuntimeError(f"Ollama streaming failed: {e}")

    async def count_tokens(self, messages: List[LLMMessage]) -> int:
        """Estimate token count."""
        total_chars = sum(len(msg.content) for msg in messages)
        return total_chars // 4

    def get_model_name(self) -> str:
        return self.config.model

    def get_provider_name(self) -> str:
        return "ollama"

    def _convert_messages(self, messages: List[LLMMessage]) -> List[Dict[str, Any]]:
        """Convert internal messages to Ollama format."""
        ollama_messages = []
        for msg in messages:
            ollama_msg = {
                "role": msg.role.value,
                "content": msg.content,
            }
            if msg.tool_calls:
                ollama_msg["tool_calls"] = msg.tool_calls
            ollama_messages.append(ollama_msg)
        return ollama_messages

    def _parse_response(self, data: Dict[str, Any]) -> LLMResponse:
        """Parse Ollama response to internal format."""
        message = data.get("message", {})

        tool_calls = None
        if message.get("tool_calls"):
            tool_calls = message["tool_calls"]

        return LLMResponse(
            content=message.get("content", ""),
            role=MessageRole.ASSISTANT,
            tool_calls=tool_calls,
            finish_reason="stop" if data.get("done") else None,
            model=data.get("model"),
            metadata={"provider": "ollama"},
        )