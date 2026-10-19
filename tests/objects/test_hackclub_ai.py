"""The Hack Club AI client: request shapes, parsing and error mapping.

The transport is replaced with a fake `_post` or `_get`, so these run offline
and check what the client makes of a body rather than what the proxy does.
"""

import base64

import pytest
import requests

from bot.core import global_state
from bot.objects.hackclub_ai import AIError, HackClubAI

MODELS = {
    "data": [
        {
            "id": "deepseek/deepseek-v4.1-flash",
            "architecture": {"output_modalities": ["text"]},
            "pricing": {"prompt": "0.0000001", "completion": "0.0000002"},
        },
        {
            "id": "qwen/qwen3-32b:batch",
            "architecture": {"output_modalities": ["text"]},
        },
        {
            "id": "openai/text-embedding-3-large",
            "architecture": {"output_modalities": ["embedding"]},
        },
        {
            "id": "openrouter/auto",
            "architecture": {"output_modalities": ["text", "image"]},
            "pricing": {"image_output": "-1"},
        },
        {
            "id": "google/gemini-3-pro-image",
            "architecture": {"output_modalities": ["image", "text"]},
            "pricing": {"image_output": "0.00012"},
        },
        {
            "id": "google/gemini-2.5-flash-image",
            "architecture": {"output_modalities": ["image", "text"]},
            "pricing": {"image_output": "0.00003"},
        },
    ]
}


@pytest.fixture
def client():
    return HackClubAI(api_key="test-key")


def answer(text="hello"):
    return {
        "model": "deepseek/deepseek-v4.1-flash",
        "choices": [{"message": {"content": text}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 3},
    }


def image_body(*pictures: bytes):
    return {
        "model": "google/gemini-2.5-flash-image",
        "choices": [
            {
                "message": {
                    "content": "here you go",
                    "images": [
                        {
                            "image_url": {
                                "url": "data:image/png;base64,"
                                + base64.b64encode(picture).decode()
                            }
                        }
                        for picture in pictures
                    ],
                }
            }
        ],
    }


class FakeResponse:
    """The parts of requests.Response the client reads."""

    def __init__(self, status, body=None, headers=None):
        self.status_code = status
        self._body = body
        self.headers = headers or {}

    def json(self):
        if self._body is None:
            raise ValueError("no json")
        return self._body


# ------------------------------------------------------------------ chat


async def test_a_chat_reply_carries_the_text_and_the_token_usage(client):
    client._post = lambda *args, **kwargs: answer("Hi there")

    reply = await client.chat("deepseek/deepseek-v4.1-flash", [])

    assert reply.text == "Hi there"
    assert reply.model == "deepseek/deepseek-v4.1-flash"
    assert (reply.prompt_tokens, reply.completion_tokens) == (12, 3)


async def test_a_chat_request_asks_for_a_bounded_non_streamed_answer(client):
    calls = []
    client._post = lambda path, payload, **kwargs: (
        calls.append((path, payload)) or answer()
    )

    await client.chat(
        "deepseek/deepseek-v4.1-flash", [{"role": "user", "content": "hi"}]
    )

    path, payload = calls[0]
    assert path == "/chat/completions"
    assert payload["model"] == "deepseek/deepseek-v4.1-flash"
    assert payload["max_tokens"] == global_state.AI_MAX_ANSWER_TOKENS
    assert payload["stream"] is False


@pytest.mark.parametrize("body", [{}, {"choices": []}, {"choices": [{"message": {}}]}])
async def test_an_answer_with_no_text_is_an_error(client, body):
    client._post = lambda *args, **kwargs: body

    with pytest.raises(AIError, match="empty answer"):
        await client.chat("deepseek/deepseek-v4.1-flash", [])


async def test_a_truncated_answer_is_reported_as_a_budget_problem(client):
    client._post = lambda *args, **kwargs: {
        "choices": [{"message": {"content": None}, "finish_reason": "length"}],
        "usage": {
            "completion_tokens": 1500,
            "completion_tokens_details": {"reasoning_tokens": 1490},
        },
    }

    with pytest.raises(AIError, match="reply budget"):
        await client.chat("deepseek/deepseek-v4.1-flash", [])


# ----------------------------------------------------------------- image


async def test_image_payloads_are_decoded_from_their_data_urls(client):
    client._post = lambda *args, **kwargs: image_body(b"first", b"second")

    reply = await client.image("google/gemini-2.5-flash-image", "a cat", "1:1")

    assert reply.images == [b"first", b"second"]
    assert reply.text == "here you go"


async def test_an_image_request_asks_for_image_and_text_modalities(client):
    calls = []
    client._post = lambda path, payload, **kwargs: (
        calls.append(payload) or image_body(b"png")
    )

    await client.image("google/gemini-2.5-flash-image", "a cat", "16:9")

    assert calls[0]["modalities"] == ["image", "text"]
    assert calls[0]["image_config"] == {"aspect_ratio": "16:9"}


async def test_a_reply_with_no_image_is_an_error(client):
    client._post = lambda *args, **kwargs: {
        "choices": [{"message": {"content": "sorry"}}]
    }

    with pytest.raises(AIError, match="no image"):
        await client.image("google/gemini-2.5-flash-image", "a cat", "1:1")


# ------------------------------------------------------------- moderation


async def test_a_flagged_prompt_is_reported(client):
    client._post = lambda *args, **kwargs: {"results": [{"flagged": True}]}

    assert await client.is_flagged("bad") is True


async def test_a_clean_prompt_is_not_flagged(client):
    client._post = lambda *args, **kwargs: {"results": [{"flagged": False}]}

    assert await client.is_flagged("a cat") is False


# ----------------------------------------------------------------- models


async def test_the_model_list_keeps_chat_and_image_models_only(client):
    client._get = lambda *args, **kwargs: MODELS

    count = await client.load_models()

    assert global_state.ai_text_models == ["deepseek/deepseek-v4.1-flash"]
    assert global_state.ai_image_models == [
        "google/gemini-2.5-flash-image",
        "google/gemini-3-pro-image",
    ]
    assert count == 3


async def test_image_prices_become_credits(client):
    client._get = lambda *args, **kwargs: MODELS

    await client.load_models()

    assert global_state.ai_image_credits == {
        "google/gemini-2.5-flash-image": 1,
        "google/gemini-3-pro-image": 4,
    }


async def test_an_empty_model_list_is_an_error_and_changes_nothing(client, monkeypatch):
    monkeypatch.setattr(global_state, "ai_text_models", ["kept"])
    client._get = lambda *args, **kwargs: {"data": []}

    with pytest.raises(AIError, match="no usable models"):
        await client.load_models()

    assert global_state.ai_text_models == ["kept"]


# ----------------------------------------------------------------- errors


def test_the_daily_limit_status_is_preserved(monkeypatch, client):
    monkeypatch.setattr(
        requests,
        "request",
        lambda *args, **kwargs: FakeResponse(
            402, {"error": {"message": "Daily limit reached"}}
        ),
    )

    with pytest.raises(AIError) as raised:
        client._post("/chat/completions", {}, timeout=1)

    assert raised.value.status == 402
    assert str(raised.value) == "Daily limit reached"


def test_a_retry_after_header_is_carried_through(monkeypatch, client):
    monkeypatch.setattr(
        requests,
        "request",
        lambda *args, **kwargs: FakeResponse(
            429, {"error": {"message": "Slow down"}}, {"Retry-After": "17"}
        ),
    )

    with pytest.raises(AIError) as raised:
        client._post("/chat/completions", {}, timeout=1)

    assert raised.value.status == 429
    assert raised.value.retry_after == 17


def test_an_error_without_a_json_body_falls_back_to_the_status(monkeypatch, client):
    monkeypatch.setattr(requests, "request", lambda *args, **kwargs: FakeResponse(500))

    with pytest.raises(AIError, match="HTTP 500"):
        client._post("/chat/completions", {}, timeout=1)


def test_a_connection_failure_is_an_ai_error(monkeypatch, client):
    def refuse(*args, **kwargs):
        raise requests.ConnectionError("no route")

    monkeypatch.setattr(requests, "request", refuse)

    with pytest.raises(AIError, match="Could not reach"):
        client._post("/chat/completions", {}, timeout=1)


def test_the_key_is_only_sent_when_there_is_one():
    assert HackClubAI(api_key="").configured is False
    assert HackClubAI(api_key="k")._headers()["Authorization"] == "Bearer k"
    assert "Authorization" not in HackClubAI(api_key="")._headers()
