"""Anthropic (Claude) LLM Provider"""
import os
from typing import List, Optional, Dict, Any, AsyncIterator
import httpx
from .base import LLMProvider, LLMMessage, LLMResponse, LLMConfig, MessageRole


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.base_url = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        self._client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable required")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.config.timeout,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
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
        anthropic_messages, system_prompt = self._convert_messages(messages)

        payload = {
            "model": merged_config.model,
            "messages": anthropic_messages,
            "max_tokens": merged_config.max_tokens,
            "temperature": merged_config.temperature,
            "top_p": merged_config.top_p,
        }

        if system_prompt:
            payload["system"] = system_prompt

        if tools:
            payload["tools"] = self._convert_tools(tools)

        try:
            response = await self._client.post("/messages", json=payload)
            response.raise_for_status()
            data = response.json()
            return self._parse_response(data)
        except Exception as e:
            raise RuntimeError(f"Anthropic completion failed: {e}")

    async def stream_complete(
        self,
        messages: List[LLMMessage],
        config: Optional[LLMConfig] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[LLMResponse]:
        if not self._client:
            await self.initialize()

        merged_config = self._merge_config(config)
        anthropic_messages, system_prompt = self._convert_messages(messages)

        payload = {
            "model": merged_config.model,
            "messages": anthropic_messages,
            "max_tokens": merged_config.max_tokens,
            "temperature": merged_config.temperature,
            "top_p": merged_config.top_p,
            "stream": True,
        }

        if system_prompt:
            payload["system"] = system_prompt

        if tools:
            payload["tools"] = self._convert_tools(tools)

        try:
            async with self._client.stream("POST", "/messages", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip() and line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        import json
                        data = json.loads(data_str)
                        if data.get("type") == "content_block_delta" and data.get("delta", {}).get("text"):
                            yield LLMResponse(
                                content=data["delta"]["text"],
                                role=MessageRole.ASSISTANT,
                                finish_reason=None,
                                model=merged_config.model,
                            )
        except Exception as e:
            raise RuntimeError(f"Anthropic streaming failed: {e}")

    async def count_tokens(self, messages: List[LLMMessage]) -> int:
        total_chars = sum(len(msg.content) for msg in messages)
        return total_chars // 4

    def get_model_name(self) -> str:
        return self.config.model

    def get_provider_name(self) -> str:
        return "anthropic"

    def _convert_messages(self, messages: List[LLMMessage]) -> tuple:
        system_prompt = None
        anthropic_messages = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system_prompt = msg.content
            else:
                role = "user" if msg.role == MessageRole.USER else "assistant"
                anthropic_messages.append({"role": role, "content": msg.content})

        return anthropic_messages, system_prompt

    def _convert_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        anthropic_tools = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool["function"]
                anthropic_tools.append({
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
                })
        return anthropic_tools

    def _parse_response(self, data: Dict[str, Any]) -> LLMResponse:
        content = ""
        tool_calls = None

        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")
            elif block.get("type") == "tool_use":
                if tool_calls is None:
                    tool_calls = []
                tool_calls.append({
                    "id": block.get("id"),
                    "type": "function",
                    "function": {
                        "name": block.get("name"),
                        "arguments": block.get("input", {}),
                    },
                })

        stop_reason = data.get("stop_reason")
        if stop_reason == "tool_use":
            finish_reason = "tool_calls"
        elif stop_reason == "max_tokens":
            finish_reason = "length"
        else:
            finish_reason = "stop"

        return LLMResponse(
            content=content,
            role=MessageRole.ASSISTANT,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            model=data.get("model"),
            metadata={"provider": "anthropic"},
        )