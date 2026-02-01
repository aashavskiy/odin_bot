from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.openai_client import OpenAIClient


@pytest.mark.asyncio
async def test_generate_reply_uses_responses_api():
    response = SimpleNamespace(output_text=" Hello ")
    client = SimpleNamespace(
        responses=SimpleNamespace(create=AsyncMock(return_value=response))
    )
    openai_client = OpenAIClient(api_key="key")
    openai_client._client = lambda: client

    reply = await openai_client.generate_reply([{"role": "user", "content": "hi"}])

    assert reply == "Hello"


@pytest.mark.asyncio
async def test_generate_reply_falls_back_to_chat_completions():
    chat_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=" Hey "))]
    )
    client = SimpleNamespace(
        responses=None,
        chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value=chat_response))),
    )
    openai_client = OpenAIClient(api_key="key")
    openai_client._client = lambda: client

    reply = await openai_client.generate_reply([{"role": "user", "content": "hi"}])

    assert reply == "Hey"
