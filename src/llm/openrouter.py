"""OpenRouter LLM Provider"""
import os
from typing import List, Optional, Dict, Any, AsyncIterator
import httpx
from .base import LLMProvider, LLMMessage, LLMResponse, LLMConfig, MessageRole


class OpenRouterProvider(LLMProvider):
    """OpenRouter LLM provider - access to 300+ models."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self._client: Optional[httpx.AsyncClient] = None
        self._referer = os.getenv("OPENROUTER_REFERER", "https://github.com/Max-arango/CTF-Autonomous-hacker")
        self._title = os.getenv("OPENROUTER_TITLE", "CTF Autonomous Hacker")

    async def initialize(self) -> None:
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable required")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.config.timeout,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": self._referer,
                "X-Title": self._title,
            },
        )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    async def complete(
        self,
        messages: List[LLMMessage],
        config: Optional[LLMConfig] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> LLMResponse:
        if not self._client:
            await self.initialize()

        merged_config = self._merge_config(config)
        openrouter_messages = self._convert_messages(messages)

        payload = {
            "model": merged_config.model,
            "messages": openrouter_messages,
            "max_tokens": merged_config.max_tokens,
            "temperature": merged_config.temperature,
            "top_p": merged_config.top_p,
        }

        if tools:
            payload["tools"] = tools

        try:
            response = await self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            return self._parse_response(data)
        except Exception as e:
            raise RuntimeError(f"OpenRouter completion failed: {e}")

    async def stream_complete(
        self,
        messages: List[LLMMessage],
        config: Optional[LLMConfig] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[LLMResponse]:
        if not self._client:
            await self.initialize()

        merged_config = self._merge_config(config)
        openrouter_messages = self._convert_messages(messages)

        payload = {
            "model": merged_config.model,
            "messages": openrouter_messages,
            "max_tokens": merged_config.max_tokens,
            "temperature": merged_config.temperature,
            "top_p": merged_config.top_p,
            "stream": True,
        }

        if tools:
            payload["tools"] = tools

        try:
            async with self._client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip() and line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        import json
                        data = json.loads(data_str)
                        if data.get("choices") and data["choices"][0].get("delta", {}).get("content"):
                            yield LLMResponse(
                                content=data["choices"][0]["delta"]["content"],
                                role=MessageRole.ASSISTANT,
                                finish_reason=None,
                                model=data.get("model"),
                            )
        except Exception as e:
            raise RuntimeError(f"OpenRouter streaming failed: {e}")

    async def count_tokens(self, messages: List[LLMMessage]) -> int:
        total_chars = sum(len(msg.content) for msg in messages)
        return total_chars // 4

    def get_model_name(self) -> str:
        return self.config.model

    def get_provider_name(self) -> str:
        return "openrouter"

    def _convert_messages(self, messages: List[LLMMessage]) -> List[Dict[str, Any]]:
        result = []
        for msg in messages:
            m = {"role": msg.role.value, "content": msg.content}
            if msg.tool_calls:
                m["tool_calls"] = msg.tool_calls
            result.append(m)
        return result

    def _parse_response(self, data: Dict[str, Any]) -> LLMResponse:
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        tool_calls = None
        if message.get("tool_calls"):
            tool_calls = message["tool_calls"]

        return LLMResponse(
            content=message.get("content", ""),
            role=MessageRole.ASSISTANT,
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason"),
            model=data.get("model"),
            metadata={"provider": "openrouter"},
        )