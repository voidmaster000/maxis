"""The /ai commands: budgets, chat memory, and what gets attached.

The client is replaced with a fake, so these are about the decisions the cog
makes -- who may spend what, what is remembered, and how a reply is shown --
rather than about HTTP.
"""

from datetime import UTC, datetime

import pytest

from bot.commands.ai_commands import (
    AI,
    image_model_autocomplete,
    text_model_autocomplete,
)
from bot.core import global_state
from bot.objects.hackclub_ai import AIError, ChatReply, ImageReply
from tests.conftest import FakeInteraction, FakeUser


class FakeClient:
    """The AI client, minus the network."""

    def __init__(
        self,
        *,
        text: str = "An answer.",
        images: list[bytes] | None = None,
        flagged: bool = False,
        configured: bool = True,
        chat_error: AIError | None = None,
        image_error: AIError | None = None,
    ) -> None:
        self.text = text
        self.images = [b"png"] if images is None else images
        self.flagged = flagged
        self.configured = configured
        self.chat_error = chat_error
        self.image_error = image_error
        self.chat_calls: list[tuple[str, list[dict[str, str]]]] = []
        self.image_calls: list[tuple[str, str, str]] = []
        self.moderated: list[str] = []

    async def chat(self, model, messages):
        self.chat_calls.append((model, messages))
        if self.chat_error:
            raise self.chat_error
        return ChatReply(self.text, model, 12, 3)

    async def image(self, model, prompt, aspect_ratio):
        self.image_calls.append((model, prompt, aspect_ratio))
        if self.image_error:
            raise self.image_error
        return ImageReply(self.images, "", model)

    async def is_flagged(self, text):
        self.moderated.append(text)
        return self.flagged


@pytest.fixture
def ai():
    cog = AI()
    cog.client = FakeClient()
    # A day stamp, as if a command had already run today, so the counters a
    # test preloads survive the rollover check at the top of each command.
    global_state.ai_usage_day = datetime.now(UTC).date().isoformat()
    return cog


@pytest.fixture
def no_cooldown(monkeypatch):
    """Drop the cooldowns so a test can make two calls in a row."""
    monkeypatch.setattr(global_state, "AI_TEXT_COOLDOWN", 0)
    monkeypatch.setattr(global_state, "AI_IMAGE_COOLDOWN", 0)


# ------------------------------------------------------------------- text


async def test_ask_sends_the_answer_and_counts_the_request(ai):
    interaction = FakeInteraction()

    await ai.ask.callback(ai, interaction, "hello")

    assert interaction.deferred
    assert interaction.followups[0].description == "An answer."
    assert global_state.ai_text_usage[1] == 1
    assert global_state.ai_text_total == 1


async def test_ask_sends_the_default_model_and_the_persona(ai):
    interaction = FakeInteraction()

    await ai.ask.callback(ai, interaction, "hello")

    model, messages = ai.client.chat_calls[0]
    assert model == global_state.AI_DEFAULT_TEXT_MODEL
    assert messages[0] == {"role": "system", "content": global_state.AI_SYSTEM_PROMPT}
    assert messages[-1] == {"role": "user", "content": "hello"}


async def test_ask_sends_the_model_that_was_picked(ai):
    interaction = FakeInteraction()

    await ai.ask.callback(ai, interaction, "hello", "qwen/qwen3-32b")

    assert ai.client.chat_calls[0][0] == "qwen/qwen3-32b"


async def test_a_long_answer_is_attached_as_markdown(ai):
    ai.client.text = "x" * (global_state.AI_MAX_ANSWER_CHARS + 1)
    interaction = FakeInteraction()

    await ai.ask.callback(ai, interaction, "hello")

    assert interaction.followups[0].description.endswith("...")
    attachment = interaction.followup_files[0]
    assert attachment.filename == "answer.md"
    assert attachment.fp.read() == ai.client.text.encode()


# ------------------------------------------------------------ chat memory


async def test_chat_resends_the_conversation(ai, no_cooldown):
    interaction = FakeInteraction(channel_id=5)

    await ai.chat.callback(ai, interaction, "first")
    await ai.chat.callback(ai, interaction, "second")

    _, messages = ai.client.chat_calls[1]
    assert {"role": "user", "content": "first"} in messages
    assert {"role": "assistant", "content": "An answer."} in messages
    assert messages[-1] == {"role": "user", "content": "second"}
    assert len(global_state.ai_conversations[(5, 1)]) == 4


async def test_conversations_are_per_user_and_per_channel(ai, no_cooldown):
    same_channel = FakeInteraction(channel_id=5)
    other_user = FakeInteraction(FakeUser(2), channel_id=5)
    other_channel = FakeInteraction(channel_id=6)

    await ai.chat.callback(ai, same_channel, "one")
    await ai.chat.callback(ai, other_user, "two")
    await ai.chat.callback(ai, other_channel, "three")

    assert len(ai.client.chat_calls[1][1]) == 2
    assert len(ai.client.chat_calls[2][1]) == 2
    assert set(global_state.ai_conversations) == {(5, 1), (5, 2), (6, 1)}


async def test_chat_keeps_only_the_last_twenty_messages(ai, no_cooldown):
    interaction = FakeInteraction(channel_id=5)
    global_state.ai_conversations[(5, 1)] = [
        {
            "role": "user" if index % 2 == 0 else "assistant",
            "content": f"old-{index}",
        }
        for index in range(global_state.AI_MAX_HISTORY_MESSAGES)
    ]

    await ai.chat.callback(ai, interaction, "new")

    history = global_state.ai_conversations[(5, 1)]
    assert len(history) == global_state.AI_MAX_HISTORY_MESSAGES
    assert history[-2] == {"role": "user", "content": "new"}
    assert history[-1] == {"role": "assistant", "content": "An answer."}
    assert all(message["content"] != "old-0" for message in history)


async def test_reset_clears_only_this_conversation(ai):
    global_state.ai_conversations[(5, 1)] = [{"role": "user", "content": "x"}]
    global_state.ai_conversations[(6, 1)] = [{"role": "user", "content": "y"}]
    interaction = FakeInteraction(channel_id=5)

    await ai.reset.callback(ai, interaction)

    assert (5, 1) not in global_state.ai_conversations
    assert (6, 1) in global_state.ai_conversations
    assert "cleared" in interaction.sent[0][0].description


async def test_reset_without_a_conversation_says_so(ai):
    interaction = FakeInteraction(channel_id=5)

    await ai.reset.callback(ai, interaction)

    assert "no conversation" in interaction.sent[0][0].description.lower()


# ---------------------------------------------------------------- budgets


async def test_a_second_text_request_waits_for_the_cooldown(ai):
    first = FakeInteraction()
    await ai.ask.callback(ai, first, "hello")

    second = FakeInteraction()
    await ai.ask.callback(ai, second, "again")

    assert "cooldown" in second.sent[0][0].description
    assert second.followups == []
    assert global_state.ai_text_usage[1] == 1


async def test_the_daily_cap_stops_further_text_requests(ai):
    global_state.ai_text_usage[1] = global_state.AI_TEXT_DAILY_REQUESTS
    interaction = FakeInteraction()

    await ai.ask.callback(ai, interaction, "hello")

    assert "used all" in interaction.sent[0][0].description
    assert ai.client.chat_calls == []


async def test_the_bot_wide_text_cap_stops_everyone(ai):
    global_state.ai_text_total = global_state.AI_TEXT_DAILY_TOTAL
    interaction = FakeInteraction(FakeUser(9))

    await ai.ask.callback(ai, interaction, "hello")

    assert "bot has used" in interaction.sent[0][0].description
    assert ai.client.chat_calls == []


async def test_the_counters_roll_over_on_a_new_utc_day(ai):
    global_state.ai_usage_day = "2000-01-01"
    global_state.ai_text_usage[1] = 40
    global_state.ai_text_total = 400
    interaction = FakeInteraction()

    await ai.ask.callback(ai, interaction, "hello")

    assert global_state.ai_text_usage[1] == 1
    assert global_state.ai_text_total == 1
    assert global_state.ai_usage_day != "2000-01-01"


async def test_without_a_key_the_command_says_what_is_missing(ai):
    ai.client.configured = False
    interaction = FakeInteraction()

    await ai.ask.callback(ai, interaction, "hello")

    assert "HACKCLUB_AI_KEY" in interaction.sent[0][0].description
    assert ai.client.chat_calls == []


async def test_a_failed_call_explains_the_daily_limit(ai):
    ai.client.chat_error = AIError("nope", status=402)
    interaction = FakeInteraction()

    await ai.ask.callback(ai, interaction, "hello")

    assert "spending limit" in interaction.followups[0].description
    assert global_state.ai_text_usage == {}
    assert global_state.ai_text_times == {}


# ------------------------------------------------------------------ image


async def test_image_generates_and_attaches_a_picture(ai):
    interaction = FakeInteraction()

    await ai.image.callback(ai, interaction, "a cat")

    assert ai.client.image_calls == [
        (global_state.AI_DEFAULT_IMAGE_MODEL, "a cat", "1:1")
    ]
    embed = interaction.followups[0]
    assert embed.description == "a cat"
    assert embed.image.url == "attachment://image-1.png"
    assert interaction.followup_files[0].filename == "image-1.png"
    assert global_state.ai_image_usage[1] == 1


async def test_a_flagged_prompt_costs_nothing(ai):
    ai.client.flagged = True
    interaction = FakeInteraction()

    await ai.image.callback(ai, interaction, "something bad")

    assert ai.client.moderated == ["something bad"]
    assert ai.client.image_calls == []
    assert "moderation" in interaction.followups[0].description
    assert global_state.ai_image_usage == {}


async def test_an_expensive_model_spends_more_credits(ai):
    global_state.ai_image_credits = {"google/gemini-3-pro-image": 4}
    interaction = FakeInteraction()

    await ai.image.callback(ai, interaction, "a cat", "google/gemini-3-pro-image")

    assert global_state.ai_image_usage[1] == 4

    # A different user, who has already spent one credit, so this is the credit
    # check rather than the cooldown.
    global_state.ai_image_usage[2] = 1
    other = FakeInteraction(FakeUser(2))
    await ai.image.callback(ai, other, "a cat", "google/gemini-3-pro-image")

    assert "credit" in other.sent[0][0].description
    assert len(ai.client.image_calls) == 1


@pytest.mark.parametrize(
    "label",
    [
        "openai/gpt-5-image (2 credits)",
        "openai/gpt-5-image (2 credit(s))",  # what older clients have cached
        "OPENAI/GPT-5-IMAGE (2 credits)",
    ],
)
async def test_a_picked_label_is_reduced_to_the_model_it_names(ai, label):
    global_state.ai_image_models = ["openai/gpt-5-image"]
    global_state.ai_image_credits = {"openai/gpt-5-image": 2}
    interaction = FakeInteraction()

    # Usually the value behind a suggestion arrives; this is the case where the
    # label it filled the field with is what gets submitted.
    await ai.image.callback(ai, interaction, "a lighthouse", label)

    assert ai.client.image_calls[0][0] == "openai/gpt-5-image"
    assert global_state.ai_image_usage[1] == 2


async def test_the_bot_wide_image_cap_stops_everyone(ai):
    global_state.ai_image_total = global_state.AI_IMAGE_DAILY_TOTAL
    interaction = FakeInteraction(FakeUser(9))

    await ai.image.callback(ai, interaction, "a cat")

    assert "bot has used" in interaction.sent[0][0].description
    assert ai.client.image_calls == []


# ------------------------------------------------------------------ usage


async def test_usage_reports_both_sets_of_counters(ai):
    global_state.ai_text_usage[1] = 3
    global_state.ai_text_total = 7
    global_state.ai_image_usage[1] = 2
    global_state.ai_image_total = 5
    interaction = FakeInteraction()

    await ai.usage.callback(ai, interaction)

    fields = {field.name: field.value for field in interaction.sent[0][0].fields}
    assert fields["Text"].startswith("3/50")
    assert "7/500" in fields["Text"]
    assert fields["Images"].startswith("2/4")
    assert "5/40" in fields["Images"]


# ----------------------------------------------------------- autocomplete


async def test_text_autocomplete_offers_the_curated_models_when_empty():
    choices = await text_model_autocomplete(FakeInteraction(), "")

    assert choices[0].value == global_state.AI_TEXT_MODEL_FALLBACKS[0]
    assert all(choice.name == choice.value for choice in choices)


async def test_autocomplete_filters_what_has_been_typed():
    global_state.ai_text_models = ["vendor/alpha", "vendor/beta", "other/gamma"]

    choices = await text_model_autocomplete(FakeInteraction(), "BET")

    assert [choice.value for choice in choices] == ["vendor/beta"]


async def test_autocomplete_stops_at_discords_limit():
    global_state.ai_text_models = [f"vendor/model-{index}" for index in range(60)]

    choices = await text_model_autocomplete(FakeInteraction(), "")

    assert len(choices) == global_state.AI_MODEL_CHOICES == 25


async def test_image_autocomplete_labels_what_each_model_costs():
    global_state.ai_image_models = ["costly/image"]
    global_state.ai_image_credits = {"costly/image": 4}

    choices = await image_model_autocomplete(FakeInteraction(), "")

    assert choices[0].value == "costly/image"
    assert "4 credit" in choices[0].name
