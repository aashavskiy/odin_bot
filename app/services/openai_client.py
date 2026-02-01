from __future__ import annotations

from dataclasses import dataclass
import logging

from openai import AsyncOpenAI


@dataclass
class OpenAIClient:
    api_key: str
    model: str = "gpt-5.2"
    _logger: logging.Logger = logging.getLogger(__name__)

    def _client(self) -> AsyncOpenAI:
        return AsyncOpenAI(api_key=self.api_key)

    async def generate_reply(self, messages: list[dict[str, str]]) -> str:
        client = self._client()
        try:
            response = await client.responses.create(
                model=self.model,
                input=messages,
            )
            content = response.output_text
            return content.strip()
        except AttributeError:
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            content = response.choices[0].message.content or ""
            return content.strip()
        except Exception:
            self._logger.exception("OpenAI request failed")
            raise
