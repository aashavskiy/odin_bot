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

    async def summarize_history(
        self, messages: list[dict[str, str]], existing_summary: str
    ) -> str:
        prompt = (
            "Summarize the conversation so far for future context. "
            "Be concise and factual. Preserve user preferences, goals, and key facts. "
            "Omit small talk and greetings."
        )
        summary_input = []
        if existing_summary:
            summary_input.append(
                {"role": "system", "content": f"Existing summary: {existing_summary}"}
            )
        summary_input.append({"role": "system", "content": prompt})
        summary_input.extend(messages)

        client = self._client()
        try:
            response = await client.responses.create(
                model=self.model,
                input=summary_input,
            )
            return response.output_text.strip()
        except AttributeError:
            response = await client.chat.completions.create(
                model=self.model,
                messages=summary_input,
            )
            content = response.choices[0].message.content or ""
            return content.strip()
