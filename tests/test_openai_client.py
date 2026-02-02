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

    reply, model_used = await openai_client.generate_reply(
        [{"role": "user", "content": "hi"}],
        user_text="hi",
    )

    assert reply == "Hello"
    assert model_used == openai_client.model
    client.responses.create.assert_awaited_once()


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

    reply, model_used = await openai_client.generate_reply(
        [{"role": "user", "content": "hi"}],
        user_text="hi",
    )

    assert reply == "Hey"
    assert model_used == openai_client.model


@pytest.mark.asyncio
async def test_generate_reply_uses_fast_reasoning_for_short_prompt():
    response = SimpleNamespace(output_text="ok")
    create = AsyncMock(return_value=response)
    client = SimpleNamespace(
        responses=SimpleNamespace(create=create)
    )
    openai_client = OpenAIClient(
        api_key="key",
        model="gpt-5.2",
        fast_reasoning_effort="minimal",
    )
    openai_client._client = lambda: client

    await openai_client.generate_reply(
        [{"role": "user", "content": "ping"}],
        user_text="ping",
    )

    create.assert_awaited_once()
    assert create.await_args.kwargs["model"] == "gpt-5.2"
    assert create.await_args.kwargs["reasoning"] == {"effort": "minimal"}


@pytest.mark.asyncio
async def test_generate_reply_omits_reasoning_when_requested_and_long_history():
    response = SimpleNamespace(output_text="ok")
    create = AsyncMock(return_value=response)
    client = SimpleNamespace(
        responses=SimpleNamespace(create=create)
    )
    openai_client = OpenAIClient(
        api_key="key",
        model="gpt-5.2",
        fast_reasoning_effort="minimal",
    )
    openai_client._client = lambda: client
    messages = [{"role": "user", "content": "hi"}] * 6

    await openai_client.generate_reply(
        messages,
        user_text="Используй стандартную модель, пожалуйста",
    )

    assert create.await_args.kwargs["model"] == "gpt-5.2"
    assert "reasoning" not in create.await_args.kwargs
