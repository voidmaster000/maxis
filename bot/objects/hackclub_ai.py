"""Client for the Hack Club AI proxy.

One class owns the parts that are easy to get subtly wrong: the bearer header,
the request shapes chat and images need, the statuses the proxy returns, and the
base64 pictures that arrive inside a chat completion.

Every call is blocking `requests` run on a worker thread, the same pattern
`/utility currconv` uses, so the event loop keeps answering Discord while the
request is in flight.
"""

import asyncio
import base64
import logging
import math
from typing import Any, NamedTuple

import requests

from bot.core import global_state

logger = logging.getLogger(__name__)


class AIError(Exception):
    """A failed call, with the status and retry hint the proxy sent."""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


class ChatReply(NamedTuple):
    """One answer, and what it cost in tokens."""

    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int


class ImageReply(NamedTuple):
    """The decoded pictures, plus any caption the model added."""

    images: list[bytes]
    text: str
    model: str


class HackClubAI:
    """The endpoints `/ai` needs, and nothing about Discord."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else global_state.HACKCLUB_AI_KEY

    @property
    def configured(self) -> bool:
        """Whether there is a key to send at all."""
        return bool(self.api_key)

    async def chat(self, model: str, messages: list[dict[str, str]]) -> ChatReply:
        """Send a conversation and return the assistant's answer."""
        data = await asyncio.to_thread(
            self._post,
            "/chat/completions",
            {
                "model": model,
                "messages": messages,
                "max_tokens": global_state.AI_MAX_ANSWER_TOKENS,
                "stream": False,
            },
            timeout=global_state.AI_TEXT_TIMEOUT,
        )
        choices = data.get("choices") or []
        message = choices[0].get("message") if choices else None
        text = str((message or {}).get("content") or "").strip()
        usage = data.get("usage") or {}
        if not text:
            # A reasoning model spends max_tokens on hidden thinking before it
            # writes anything, so running out is a different failure from an
            # upstream that simply sent nothing back.
            finish = choices[0].get("finish_reason") if choices else None
            details = usage.get("completion_tokens_details") or {}
            logger.warning(
                "Empty answer from %s: finish=%s completion=%s reasoning=%s",
                data.get("model") or model,
                finish,
                usage.get("completion_tokens"),
                details.get("reasoning_tokens"),
            )
            if finish == "length":
                raise AIError(
                    "The model ran out of reply budget before it answered. "
                    "Try a shorter question or another model."
                )
            raise AIError("The AI service returned an empty answer.")
        return ChatReply(
            text=text,
            model=str(data.get("model") or model),
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
        )

    async def image(self, model: str, prompt: str, aspect_ratio: str) -> ImageReply:
        """Generate pictures from a prompt."""
        data = await asyncio.to_thread(
            self._post,
            "/chat/completions",
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "modalities": ["image", "text"],
                "image_config": {"aspect_ratio": aspect_ratio},
                "stream": False,
            },
            timeout=global_state.AI_IMAGE_TIMEOUT,
        )
        choices = data.get("choices") or []
        message = choices[0].get("message") if choices else None
        decoded = [
            picture
            for picture in (
                _decode_image(item) for item in (message or {}).get("images") or []
            )
            if picture
        ]
        if not decoded:
            raise AIError("The AI service returned no image.")
        return ImageReply(
            images=decoded,
            text=str((message or {}).get("content") or "").strip(),
            model=str(data.get("model") or model),
        )

    async def is_flagged(self, text: str) -> bool:
        """Ask the proxy's classifier whether a prompt breaks its rules."""
        data = await asyncio.to_thread(
            self._post,
            "/moderations",
            {"input": text},
            timeout=global_state.AI_MODERATION_TIMEOUT,
        )
        results = data.get("results") or []
        return bool(results) and bool(results[0].get("flagged"))

    async def load_models(self) -> int:
        """Fetch the live model catalogue into global_state.

        Returns how many models were kept, so the caller can log it. Raises
        AIError rather than leaving a half-filled catalogue behind.
        """
        data = await asyncio.to_thread(
            self._get, "/models", timeout=global_state.AI_MODELS_TIMEOUT
        )
        text_models: list[str] = []
        image_models: list[str] = []
        credits: dict[str, int] = {}
        for entry in data.get("data") or []:
            model_id = str(entry.get("id") or "")
            if not model_id or _unusable_model(model_id):
                continue
            outputs = (entry.get("architecture") or {}).get("output_modalities") or []
            if "image" in outputs:
                image_models.append(model_id)
                credits[model_id] = _credits_for(entry)
            elif "text" in outputs:
                text_models.append(model_id)

        if not text_models or not image_models:
            raise AIError("The AI service returned no usable models.")

        global_state.ai_text_models = sorted(text_models)
        global_state.ai_image_models = sorted(image_models)
        global_state.ai_image_credits = credits
        return len(text_models) + len(image_models)

    def _post(
        self, path: str, payload: dict[str, Any], *, timeout: float
    ) -> dict[str, Any]:
        return self._request("POST", path, payload=payload, timeout=timeout)

    def _get(self, path: str, *, timeout: float) -> dict[str, Any]:
        return self._request("GET", path, timeout=timeout)

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        timeout: float,
    ) -> dict[str, Any]:
        try:
            response = requests.request(
                method,
                f"{global_state.HACKCLUB_AI_BASE}{path}",
                headers=self._headers(),
                json=payload,
                timeout=timeout,
            )
        except requests.RequestException as error:
            raise AIError(f"Could not reach the AI service: {error}") from error
        return _checked(response)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


def _checked(response: requests.Response) -> dict[str, Any]:
    """Return the JSON body, or raise the message the proxy sent."""
    if response.status_code >= 400:
        raise AIError(
            _error_message(response),
            status=response.status_code,
            retry_after=_retry_after(response),
        )
    try:
        body = response.json()
    except ValueError as error:
        raise AIError("The AI service sent a response that was not JSON.") from error
    if not isinstance(body, dict):
        raise AIError("The AI service sent an unexpected response.")
    return body


def _error_message(response: requests.Response) -> str:
    """Pull the useful sentence out of an error body."""
    try:
        body = response.json()
    except ValueError:
        return f"The AI service returned HTTP {response.status_code}."
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])
    if isinstance(error, str):
        return error
    return f"The AI service returned HTTP {response.status_code}."


def _retry_after(response: requests.Response) -> int | None:
    """The Retry-After header, when it is a plain number of seconds."""
    value = response.headers.get("Retry-After", "")
    return int(value) if value.isdigit() else None


def _decode_image(item: Any) -> bytes | None:
    """Turn one `images` entry into bytes, ignoring anything malformed."""
    url = str(((item.get("image_url") or {}).get("url")) or "")
    _, _, encoded = url.partition(",")
    if not encoded:
        return None
    try:
        return base64.b64decode(encoded)
    except ValueError:
        return None


def _credits_for(entry: Any) -> int:
    """What one picture from this model costs, in $0.04 credits."""
    pricing = entry.get("pricing") or {}
    try:
        unit = float(pricing.get("image_output") or pricing.get("image") or 0)
    except (TypeError, ValueError):
        return 1
    cost = unit * global_state.AI_IMAGE_TOKENS_PER_REQUEST
    return max(1, math.ceil(cost / global_state.AI_IMAGE_CREDIT_USD))


def _unusable_model(model_id: str) -> bool:
    """Batch tiers queue, embeddings do not chat, and auto picks for itself."""
    return (
        ":batch" in model_id
        or "embedding" in model_id
        or model_id.startswith("openrouter/auto")
    )
