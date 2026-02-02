from __future__ import annotations

from dataclasses import dataclass
import logging

from openai import AsyncOpenAI


@dataclass
class OpenAIClient:
    api_key: str
    model: str = "gpt-5.2"
    fast_reasoning_effort: str | None = "minimal"
    _logger: logging.Logger = logging.getLogger(__name__)

    def _client(self) -> AsyncOpenAI:
        return AsyncOpenAI(api_key=self.api_key)

    def _choose_reasoning_effort(
        self, user_text: str | None, messages: list[dict[str, str]]
    ) -> str | None:
        if not self.fast_reasoning_effort:
            return None
        if not user_text:
            return None
        text = user_text.strip()
        if not text:
            return None
        lowered = text.lower()
        asks_standard_model = any(
            phrase in lowered
            for phrase in (
                "standard model",
                "full model",
                "slow model",
                "обычную модель",
                "стандартную модель",
                "полную модель",
                "медленную модель",
            )
        )
        if len(text) < 160 and (not asks_standard_model or len(messages) < 6):
            return self.fast_reasoning_effort
        return None

    async def generate_reply(
        self, messages: list[dict[str, str]], user_text: str | None = None
    ) -> tuple[str, str, str | None]:
        client = self._client()
        model = self.model
        reasoning_effort = self._choose_reasoning_effort(user_text, messages)
        extra_args = {}
        if reasoning_effort:
            extra_args["reasoning"] = {"effort": reasoning_effort}
        try:
            response = await client.responses.create(
                model=model,
                input=messages,
                **extra_args,
            )
            content = response.output_text
            return content.strip(), model, reasoning_effort
        except AttributeError:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
            )
            content = response.choices[0].message.content or ""
            return content.strip(), model, None
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
