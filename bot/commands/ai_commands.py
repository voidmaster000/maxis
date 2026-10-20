"""AI slash commands for Maxis.

`/ai` is a thin Discord layer over the Hack Club AI proxy. The request shapes
and error handling live in `bot.objects.hackclub_ai`, the budgets and chat
history live in global_state, and this module only decides who may spend what
and how the result is shown.

The caps are sized for a group of ten: four image credits per person and forty
for the bot keep pictures at about $1.60 of the $3.00 daily limit, which leaves
the text side room to run all day on a cheap model.
"""

import logging
import re
from datetime import UTC, datetime
from io import BytesIO

import discord
from discord import app_commands
from discord.ext import commands

from bot.core import global_state
from bot.core.helper import get_random_color, reply_error
from bot.objects.hackclub_ai import AIError, ChatReply, HackClubAI, ImageReply

logger = logging.getLogger(__name__)

ASPECT_RATIO_CHOICES = [
    app_commands.Choice(name=ratio, value=ratio)
    for ratio in global_state.AI_ASPECT_RATIOS
]


# --------------------------------------------------------------------------
# Models
# The live list is fetched once, when the cog loads. Until then -- and if the
# fetch fails -- these read the curated fallbacks, so autocomplete always works.
# --------------------------------------------------------------------------


def _text_models() -> list[str]:
    return global_state.ai_text_models or list(global_state.AI_TEXT_MODEL_FALLBACKS)


def _image_models() -> list[str]:
    return global_state.ai_image_models or list(global_state.AI_IMAGE_MODEL_FALLBACKS)


def _image_credits(model: str) -> int:
    credits = global_state.ai_image_credits or global_state.AI_IMAGE_CREDIT_FALLBACKS
    return credits.get(model, 1)


def _credit_label(credits: int) -> str:
    return f"{credits} credit" if credits == 1 else f"{credits} credits"


# Autocomplete normally sends the value behind the label, but not always: the
# client fills the field with the label, so one that is edited afterwards (or
# submitted from some clients) arrives as typed text -- "openai/gpt-5-image
# (2 credits)" instead of the id. Typing allows any string at all, so reduce
# whatever turns up to a published id, stripping the price and matching the
# list case-insensitively so the spelling sent on is the one the proxy knows. The
# "(s)" form is what older clients still have cached.
_CREDIT_LABEL = re.compile(r"^(?P<model>.+?) \(\d+ credit(?:s|\(s\))?\)$")


def _model_id(raw: str, models: list[str]) -> str:
    """Reduce whatever was submitted to a model id from the known list."""
    candidate = _CREDIT_LABEL.sub(r"\g<model>", (raw or "").strip())
    wanted = candidate.casefold()
    return next((model for model in models if model.casefold() == wanted), candidate)


def _ordered(models: list[str], preferred: tuple[str, ...], current: str) -> list[str]:
    """Substring matches, or the curated names first while the box is empty."""
    if current:
        wanted = current.casefold()
        return [model for model in models if wanted in model.casefold()]
    first = [model for model in preferred if model in models]
    return first + [model for model in models if model not in first]


# Choice is generic, so without pinning it to [str] a checker infers the whole
# constraint set (str | int | float) and rejects the declared return type.


def _text_choices(current: str) -> list[app_commands.Choice[str]]:
    ordered = _ordered(_text_models(), global_state.AI_TEXT_MODEL_FALLBACKS, current)
    return [
        app_commands.Choice[str](name=model, value=model)
        for model in ordered[: global_state.AI_MODEL_CHOICES]
    ]


def _image_choices(current: str) -> list[app_commands.Choice[str]]:
    ordered = _ordered(_image_models(), global_state.AI_IMAGE_MODEL_FALLBACKS, current)
    return [
        app_commands.Choice[str](
            name=f"{model} ({_credit_label(_image_credits(model))})", value=model
        )
        for model in ordered[: global_state.AI_MODEL_CHOICES]
    ]


async def text_model_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    """Suggest chat models, filtered by what has been typed."""
    return _text_choices(current)


async def image_model_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    """Suggest image models, labelled with what each one costs."""
    return _image_choices(current)


# --------------------------------------------------------------------------
# Budgets
# --------------------------------------------------------------------------


def _cooldown_remaining(times: dict[int, datetime], user_id: int, cooldown: int) -> int:
    """Seconds before this user may spend again, or 0."""
    last = times.get(user_id)
    if last is None:
        return 0
    elapsed = (datetime.now(UTC) - last).total_seconds()
    return max(0, int(cooldown - elapsed))


def _roll_usage_day() -> None:
    """Clear the counters when the UTC date the API bills on changes."""
    today = datetime.now(UTC).date().isoformat()
    if global_state.ai_usage_day == today:
        return
    global_state.ai_usage_day = today
    global_state.ai_text_usage.clear()
    global_state.ai_image_usage.clear()
    global_state.ai_text_total = 0
    global_state.ai_image_total = 0


def _text_refusal(user_id: int) -> str | None:
    """Why this request cannot be made, or None if it can."""
    wait = _cooldown_remaining(
        global_state.ai_text_times, user_id, global_state.AI_TEXT_COOLDOWN
    )
    if wait:
        return f"You are on cooldown. Try again in {wait} seconds."
    if (
        global_state.ai_text_usage.get(user_id, 0)
        >= global_state.AI_TEXT_DAILY_REQUESTS
    ):
        return (
            f"You have used all {global_state.AI_TEXT_DAILY_REQUESTS} of your AI "
            "requests today."
        )
    if global_state.ai_text_total >= global_state.AI_TEXT_DAILY_TOTAL:
        return "The bot has used its AI requests for today. Try again after 00:00 UTC."
    return None


def _record_text(user_id: int) -> None:
    global_state.ai_text_times[user_id] = datetime.now(UTC)
    global_state.ai_text_usage[user_id] = global_state.ai_text_usage.get(user_id, 0) + 1
    global_state.ai_text_total += 1


def _image_refusal(user_id: int, credits: int) -> str | None:
    """Why this picture cannot be made, or None if it can."""
    wait = _cooldown_remaining(
        global_state.ai_image_times, user_id, global_state.AI_IMAGE_COOLDOWN
    )
    if wait:
        minutes, seconds = divmod(wait, 60)
        return f"You are on cooldown. Try again in {minutes}m {seconds}s."
    used = global_state.ai_image_usage.get(user_id, 0)
    if used + credits > global_state.AI_IMAGE_DAILY_CREDITS:
        left = max(0, global_state.AI_IMAGE_DAILY_CREDITS - used)
        return (
            f"That image costs {_credit_label(credits)} and you have {left} left today."
        )
    if global_state.ai_image_total + credits > global_state.AI_IMAGE_DAILY_TOTAL:
        return (
            "The bot has used its image credits for today. Try again after 00:00 UTC."
        )
    return None


def _record_image(user_id: int, credits: int) -> None:
    global_state.ai_image_times[user_id] = datetime.now(UTC)
    global_state.ai_image_usage[user_id] = (
        global_state.ai_image_usage.get(user_id, 0) + credits
    )
    global_state.ai_image_total += credits


# --------------------------------------------------------------------------
# Replies
# --------------------------------------------------------------------------


def _error_embed(message: str) -> discord.Embed:
    return discord.Embed(title="Error!", description=message, color=get_random_color())


def _failure_message(error: AIError) -> str:
    """Turn a failed call into something worth reading."""
    if error.status == 401:
        return "The AI API key was rejected. Check `HACKCLUB_AI_KEY`."
    if error.status == 402:
        return (
            "The bot has reached the Hack Club AI daily spending limit. "
            "Try again after 00:00 UTC."
        )
    if error.status == 429:
        wait = (
            f" Try again in {error.retry_after} seconds."
            if error.retry_after
            else " Try again shortly."
        )
        return "The AI service is rate limiting requests." + wait
    return str(error)


async def _send_answer(interaction: discord.Interaction, reply: ChatReply) -> None:
    """Show an answer, or attach it when it will not fit in one embed."""
    footer = f"{reply.model} - {reply.prompt_tokens}+{reply.completion_tokens} tokens"
    if len(reply.text) <= global_state.AI_MAX_ANSWER_CHARS:
        embed = discord.Embed(description=reply.text, color=get_random_color())
        embed.set_footer(text=footer)
        await interaction.followup.send(embed=embed)
        return

    preview = reply.text[:1000].rstrip() + "..."
    embed = discord.Embed(description=preview, color=get_random_color())
    embed.set_footer(text=f"{footer}, full answer attached")
    file = discord.File(BytesIO(reply.text.encode()), filename="answer.md")
    await interaction.followup.send(embed=embed, file=file)


async def _send_image(
    interaction: discord.Interaction,
    reply: ImageReply,
    prompt: str,
    credits: int,
) -> None:
    """Attach the generated pictures, with the prompt as the caption."""
    files = [
        discord.File(BytesIO(data), filename=f"image-{index}.png")
        for index, data in enumerate(reply.images[:4], start=1)
    ]
    footer = f"{reply.model} ({_credit_label(credits)})"
    if len(files) > 1:
        footer += f", {len(files)} images"
    embed = discord.Embed(description=prompt, color=get_random_color())
    embed.set_footer(text=footer)
    embed.set_image(url=f"attachment://{files[0].filename}")
    await interaction.followup.send(embed=embed, files=files)


# group_name is given rather than taken from the class name: GroupCog
# kebab-cases that, which would install this as /a-i. The docstring below is the
# group's description in Discord, which caps it at 100 characters, so it stays
# one line like the other categories.
class AI(commands.GroupCog, group_name="ai"):
    """AI slash commands (the /ai category)."""

    def __init__(self) -> None:
        self.client = HackClubAI()

    async def cog_load(self) -> None:
        """Fetch the live model list once, falling back to the curated one.

        Without a key every command refuses, so there is no list worth
        fetching; that also keeps the tests off the network.
        """
        if not self.client.configured:
            return
        try:
            count = await self.client.load_models()
        except AIError as error:
            logger.warning("Using the built-in AI model list: %s", error)
        else:
            logger.info("Loaded %d AI models", count)

    async def _check_text(self, interaction: discord.Interaction) -> bool:
        """True when the caller may spend a text request."""
        _roll_usage_day()
        if not self.client.configured:
            await reply_error(
                interaction, "AI is not configured: set HACKCLUB_AI_KEY in .env."
            )
            return False
        refusal = _text_refusal(interaction.user.id)
        if refusal:
            await reply_error(interaction, refusal)
            return False
        return True

    async def _chat(
        self,
        interaction: discord.Interaction,
        model: str,
        messages: list[dict[str, str]],
    ) -> ChatReply | None:
        """Run one chat call, reporting failures in the channel."""
        try:
            return await self.client.chat(model, messages)
        except AIError as error:
            logger.warning("AI chat failed: %s", error)
            await interaction.followup.send(embed=_error_embed(_failure_message(error)))
            return None

    @app_commands.command(
        name="ask", description="Ask an AI a question, without keeping the answer"
    )
    @app_commands.describe(
        prompt="What to ask", model="Model to use (defaults to a cheap one)"
    )
    @app_commands.autocomplete(model=text_model_autocomplete)
    async def ask(self, interaction: discord.Interaction, prompt: str, model: str = ""):
        if not await self._check_text(interaction):
            return
        await interaction.response.defer()

        messages = [
            {"role": "system", "content": global_state.AI_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        reply = await self._chat(
            interaction,
            _model_id(model, _text_models()) or global_state.AI_DEFAULT_TEXT_MODEL,
            messages,
        )
        if reply is None:
            return
        _record_text(interaction.user.id)
        await _send_answer(interaction, reply)

    @app_commands.command(
        name="chat", description="Chat with an AI, remembering the conversation"
    )
    @app_commands.describe(
        prompt="What to say",
        model="Model to use (defaults to a cheap one)",
    )
    @app_commands.autocomplete(model=text_model_autocomplete)
    async def chat(
        self, interaction: discord.Interaction, prompt: str, model: str = ""
    ):
        if not await self._check_text(interaction):
            return
        await interaction.response.defer()

        key = (interaction.channel_id or 0, interaction.user.id)
        history = global_state.ai_conversations.get(key, [])
        question = {"role": "user", "content": prompt}
        messages = [
            {"role": "system", "content": global_state.AI_SYSTEM_PROMPT},
            *history,
            question,
        ]
        reply = await self._chat(
            interaction,
            _model_id(model, _text_models()) or global_state.AI_DEFAULT_TEXT_MODEL,
            messages,
        )
        if reply is None:
            return

        _record_text(interaction.user.id)
        answer = {"role": "assistant", "content": reply.text}
        global_state.ai_conversations[key] = (history + [question, answer])[
            -global_state.AI_MAX_HISTORY_MESSAGES :
        ]
        await _send_answer(interaction, reply)

    @app_commands.command(name="image", description="Generate an image from a prompt")
    @app_commands.describe(
        prompt="What the image should show",
        model="Model to use (defaults to a cheap one)",
        aspect_ratio="Shape of the image",
    )
    @app_commands.choices(aspect_ratio=ASPECT_RATIO_CHOICES)
    @app_commands.autocomplete(model=image_model_autocomplete)
    async def image(
        self,
        interaction: discord.Interaction,
        prompt: str,
        model: str = "",
        aspect_ratio: str = "1:1",
    ):
        _roll_usage_day()
        if not self.client.configured:
            await reply_error(
                interaction, "AI is not configured: set HACKCLUB_AI_KEY in .env."
            )
            return

        chosen = (
            _model_id(model, _image_models()) or global_state.AI_DEFAULT_IMAGE_MODEL
        )
        credits = _image_credits(chosen)
        refusal = _image_refusal(interaction.user.id, credits)
        if refusal:
            await reply_error(interaction, refusal)
            return

        await interaction.response.defer()
        try:
            flagged = await self.client.is_flagged(prompt)
        except AIError as error:
            logger.warning("AI moderation failed: %s", error)
            await interaction.followup.send(embed=_error_embed(_failure_message(error)))
            return
        if flagged:
            await interaction.followup.send(
                embed=_error_embed("That prompt was rejected by the moderation check.")
            )
            return

        try:
            reply = await self.client.image(chosen, prompt, aspect_ratio)
        except AIError as error:
            logger.warning("AI image failed: %s", error)
            await interaction.followup.send(embed=_error_embed(_failure_message(error)))
            return

        _record_image(interaction.user.id, credits)
        await _send_image(interaction, reply, prompt, credits)

    @app_commands.command(
        name="reset", description="Forget your conversation with the AI here"
    )
    async def reset(self, interaction: discord.Interaction):
        key = (interaction.channel_id or 0, interaction.user.id)
        existed = global_state.ai_conversations.pop(key, None) is not None
        description = (
            "Your conversation in this channel has been cleared."
            if existed
            else "There was no conversation here to clear."
        )
        embed = discord.Embed(description=description, color=get_random_color())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="usage", description="Show how much AI quota you have used today"
    )
    async def usage(self, interaction: discord.Interaction):
        _roll_usage_day()
        user_id = interaction.user.id
        text = (
            f"{global_state.ai_text_usage.get(user_id, 0)}"
            f"/{global_state.AI_TEXT_DAILY_REQUESTS} requests"
            f" (bot: {global_state.ai_text_total}/{global_state.AI_TEXT_DAILY_TOTAL})"
        )
        images = (
            f"{global_state.ai_image_usage.get(user_id, 0)}"
            f"/{global_state.AI_IMAGE_DAILY_CREDITS} credits"
            f" (bot: {global_state.ai_image_total}/{global_state.AI_IMAGE_DAILY_TOTAL})"
        )
        embed = discord.Embed(title="AI usage today:-", color=get_random_color())
        embed.add_field(name="Text", value=text, inline=False)
        embed.add_field(name="Images", value=images, inline=False)
        embed.set_footer(text="Counters reset at 00:00 UTC.")
        await interaction.response.send_message(embed=embed, ephemeral=True)
