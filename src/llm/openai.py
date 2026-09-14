"""OpenAI-compatible LLM Provider"""
import os
from typing import List, Optional, Dict, Any, AsyncIterator
from openai import AsyncOpenAI
from .base import LLMProvider, LLMMessage, LLMResponse, LLMConfig, MessageRole


class OpenAIProvider(LLMProvider):
    """OpenAI-compatible provider (OpenAI, vLLM, etc.)."""

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    async def initialize(self) -> None:
        """Initialize the OpenAI client."""
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")

        self._client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.config.timeout,
        )

    async def close(self) -> None:
        """Close the client."""
        if self._client:
            await self._client.close()

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
        openai_messages = self._convert_messages(messages)

        try:
            response = await self._client.chat.completions.create(
                model=merged_config.model,
                messages=openai_messages,
                max_tokens=merged_config.max_tokens,
                temperature=merged_config.temperature,
                top_p=merged_config.top_p,
                frequency_penalty=merged_config.frequency_penalty,
                presence_penalty=merged_config.presence_penalty,
                tools=tools,
                tool_choice="auto" if tools else None,
                **merged_config.extra_params,
            )

            return self._parse_response(response)
        except Exception as e:
            raise RuntimeError(f"OpenAI completion failed: {e}")

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
        openai_messages = self._convert_messages(messages)

        try:
            stream = await self._client.chat.completions.create(
                model=merged_config.model,
                messages=openai_messages,
                max_tokens=merged_config.max_tokens,
                temperature=merged_config.temperature,
                top_p=merged_config.top_p,
                frequency_penalty=merged_config.frequency_penalty,
                presence_penalty=merged_config.presence_penalty,
                tools=tools,
                tool_choice="auto" if tools else None,
                stream=True,
                **merged_config.extra_params,
            )

            async for chunk in stream:
                if chunk.choices:
                    choice = chunk.choices[0]
                    if choice.delta.content:
                        yield LLMResponse(
                            content=choice.delta.content,
                            role=MessageRole.ASSISTANT,
                            finish_reason=choice.finish_reason,
                            model=chunk.model,
                        )
        except Exception as e:
            raise RuntimeError(f"OpenAI streaming failed: {e}")

    async def count_tokens(self, messages: List[LLMMessage]) -> int:
        """Estimate token count."""
        total_chars = sum(len(msg.content) for msg in messages)
        return total_chars // 4

    def get_model_name(self) -> str:
        return self.config.model

    def get_provider_name(self) -> str:
        return "openai"

    def _convert_messages(self, messages: List[LLMMessage]) -> List[Dict[str, Any]]:
        """Convert internal messages to OpenAI format."""
        openai_messages = []
        for msg in messages:
            openai_msg = {
                "role": msg.role.value,
                "content": msg.content,
            }
            if msg.name:
                openai_msg["name"] = msg.name
            if msg.tool_calls:
                openai_msg["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                openai_msg["tool_call_id"] = msg.tool_call_id
            openai_messages.append(openai_msg)
        return openai_messages

    def _parse_response(self, response) -> LLMResponse:
        """Parse OpenAI response to internal format."""
        choice = response.choices[0]
        message = choice.message

        tool_calls = None
        if message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]

        usage = None
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            content=message.content or "",
            role=MessageRole.ASSISTANT,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason,
            usage=usage,
            model=response.model,
            metadata={"provider": "openai"},
        )