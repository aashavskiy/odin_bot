from __future__ import annotations

from dataclasses import dataclass

from openai import AsyncOpenAI


@dataclass
class OpenAIClient:
    api_key: str
    model: str = "gpt-5.2"

    def _client(self) -> AsyncOpenAI:
        return AsyncOpenAI(api_key=self.api_key)

    async def generate_reply(self, messages: list[dict[str, str]]) -> str:
        client = self._client()
        response = await client.responses.create(
            model=self.model,
            input=messages,
        )
        content = response.output_text
        return content.strip()
