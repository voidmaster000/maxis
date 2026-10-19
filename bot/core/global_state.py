"""
Global configuration and runtime state for Maxis.

Every module-level tuning constant in the project lives here, so there is one
place to look and one place to change. Below the constants sits the mutable data
the cogs share; persistence of that data is handled by `bot.core.database_sync`, and
balance changes by `bot.core.transactions`.

Nothing here touches the filesystem: `global_state` is imported by everything,
so it stays free of I/O, and every value it holds is a literal.

This module imports nothing from the rest of the bot except `bot.objects`,
which are plain data classes. That is what lets every cog do a plain
module-level `from bot.core import global_state` without creating an import cycle.
"""

import os
from datetime import datetime
from decimal import getcontext
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from bot.objects.user_settings import UserSettings
from bot.objects.warn import Warn

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

load_dotenv()

TOKEN: str = os.getenv("TOKEN", "null")
CONNSTR: str = os.getenv("CONNSTR", "null")
PORT: int = int(os.getenv("PORT", "8080"))
EXAPI: str = os.getenv("EXAPI", "")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# This module sits two levels below the repo root: bot/core/global_state.py.
# The depth is pinned by a test, so a future move fails there instead of
# quietly pointing every resource lookup at the wrong directory.
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
RESOURCES_DIR: Path = PROJECT_ROOT / "resources"


def resource_path(*parts: str) -> Path:
    """Build an absolute path inside the bundled resources directory."""
    return RESOURCES_DIR.joinpath(*parts)


# ---------------------------------------------------------------------------
# Bot metadata
# ---------------------------------------------------------------------------

VERSION: str = "5.2.0"

INVITE_URL: str = (
    "https://discord.com/api/oauth2/authorize"
    "?client_id=891518158790361138&permissions=8&scope=bot"
)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASE: str = "UnknownDatabase"
COLLECTION: str = "UnknownCollection"

# ---------------------------------------------------------------------------
# Discord limits
# ---------------------------------------------------------------------------

# Discord allows at most 25 choices per autocomplete and fields per embed.
MAX_HELP_FIELDS: int = 25

# Largest attachment a normal bot may upload. Caps /utility makefile so a huge
# string cannot be written to disk.
MAX_ATTACHMENT_BYTES: int = 8 * 1024 * 1024

# ---------------------------------------------------------------------------
# Cooldowns, in seconds
# ---------------------------------------------------------------------------

BASIC_COOLDOWN: int = 30
DAILY_COOLDOWN: int = 86400
WEEKLY_COOLDOWN: int = 604800
MONTHLY_COOLDOWN: int = 2592000

# ---------------------------------------------------------------------------
# Hack Club AI
#
# The proxy is OpenRouter-compatible: chat and image generation share one
# endpoint, and /models is public. Models are suggested by autocomplete rather
# than fixed choices, because there are hundreds of them and Discord allows 25
# choices on one option.
# ---------------------------------------------------------------------------

HACKCLUB_AI_KEY: str = os.getenv("HACKCLUB_AI_KEY", "")
HACKCLUB_AI_BASE: str = "https://ai.hackclub.com/proxy/v1"

# Text is the cheap half of the quota: the default costs about $0.00006 for a
# 700-token answer, where Gemini Flash costs about $0.002.
AI_DEFAULT_TEXT_MODEL: str = "deepseek/deepseek-v4.1-flash"
AI_DEFAULT_IMAGE_MODEL: str = "google/gemini-2.5-flash-image"

AI_SYSTEM_PROMPT: str = (
    "You are Maxis, a friendly Discord bot. Answer in Discord markdown, keep "
    "replies short unless asked for detail, and refuse requests for explicit, "
    "hateful or illegal content."
)

# Bounded so one answer cannot run away with the daily quota, and so it fits in
# a single embed almost every time.
AI_MAX_ANSWER_TOKENS: int = 800
AI_MAX_ANSWER_CHARS: int = 4096

# Used until /models answers, and if it cannot be reached at all.
AI_TEXT_MODEL_FALLBACKS: tuple[str, ...] = (
    "deepseek/deepseek-v4.1-flash",
    "deepseek/deepseek-v4-pro",
    "google/gemini-2.5-flash",
    "google/gemini-2.5-flash-lite",
    "anthropic/claude-haiku-5.5",
    "anthropic/claude-sonnet-5.5",
    "openai/gpt-5-mini",
    "openai/gpt-6.1-sol",
    "qwen/qwen3.7-flash",
    "qwen/qwen3-32b",
    "meta-llama/llama-3.3-70b-instruct",
    "x-ai/grok-4.7",
)
AI_IMAGE_MODEL_FALLBACKS: tuple[str, ...] = (
    "google/gemini-2.5-flash-image",
    "google/gemini-3.1-flash-lite-image",
    "google/gemini-3.1-flash-image",
    "openai/gpt-5-image-mini",
    "google/gemini-3-pro-image",
)

# Cost of an image in credits, matching AI_IMAGE_CREDIT_USD. The live prices
# replace this at startup; these cover the same models by hand.
AI_IMAGE_CREDIT_FALLBACKS: dict[str, int] = {
    "google/gemini-2.5-flash-image": 1,
    "google/gemini-3.1-flash-lite-image": 1,
    "google/gemini-3.1-flash-image": 2,
    "openai/gpt-5-image-mini": 1,
    "google/gemini-3-pro-image": 4,
}

# Discord returns at most 25 autocomplete choices, so that is also the most the
# picker can show per keystroke.
AI_MODEL_CHOICES: int = 25

# Image output is billed per image token and Gemini emits 1290 per picture, so
# one credit is roughly one $0.04 image. The daily caps are counted in credits.
AI_IMAGE_TOKENS_PER_REQUEST: int = 1290
AI_IMAGE_CREDIT_USD: float = 0.04

AI_ASPECT_RATIOS: tuple[str, ...] = (
    "1:1",
    "2:3",
    "3:2",
    "3:4",
    "4:3",
    "4:5",
    "5:4",
    "9:16",
    "16:9",
    "21:9",
)

# Sized for ten people: four image credits each is $1.60 of the $3.00 day, and
# the text caps leave the rest fit even if everyone picks an expensive model.
AI_TEXT_COOLDOWN: int = 10
AI_IMAGE_COOLDOWN: int = 300
AI_TEXT_DAILY_REQUESTS: int = 50
AI_IMAGE_DAILY_CREDITS: int = 4
AI_TEXT_DAILY_TOTAL: int = 500
AI_IMAGE_DAILY_TOTAL: int = 40

AI_TEXT_TIMEOUT: int = 60
AI_IMAGE_TIMEOUT: int = 180
AI_MODERATION_TIMEOUT: int = 20
AI_MODELS_TIMEOUT: int = 10

# How much of a conversation is resent with each /ai chat turn. A turn is a user
# message plus the answer, so this is ten exchanges.
AI_MAX_HISTORY_MESSAGES: int = 20

# ---------------------------------------------------------------------------
# Item tuning
# ---------------------------------------------------------------------------

# How many past commands the hacker laptop shows.
MAX_HISTORY_LINES: int = 8

# Stakes for a single hacker laptop code challenge.
PRIZE_OR_COST: int = 9000

# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------

# Decimal precision used when evaluating /utility calculate.
getcontext().prec = 50

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

# Flavour text for /economy work.
WORKS: list[str] = [
    "did babysitting for 6 hours and earned",
    "finished a 100-day job and earned",
    "found some money on road and got",
    "sold a modern art picture and earned",
    "caught a robber and was prized with",
    "fixed neighbour's PC and earned",
    "checked his car bonnet and found",
    "won a bet and earned",
    "repaired cars at workshop for a day and earned",
    "won a lucky draw and earned",
]


# The currencies /utility currconv accepts. This is a product decision rather
# than reference data: these are the codes the exchange-rate API quotes, and the
# list stops at 25 because Discord allows no more choices than that on a single
# command option. The order is user-visible -- Discord lists the choices in it,
# and so does the "valid codes" hint in the error message.
CURRENCY_CODES: tuple[str, ...] = (
    "USD",
    "EUR",
    "JPY",
    "GBP",
    "AUD",
    "CAD",
    "CHF",
    "CNY",
    "SEK",
    "MXN",
    "NZD",
    "SGD",
    "HKD",
    "NOK",
    "KRW",
    "TRY",
    "INR",
    "RUB",
    "BRL",
    "ZAR",
    "DKK",
    "PLN",
    "TWD",
    "THB",
    "MYR",
)


# ---------------------------------------------------------------------------
# Mutable runtime state
#
# Loaded from the database at startup and persisted by bot.core.database_sync.
# ---------------------------------------------------------------------------

# Custom replies, set with /utility reply and matched against incoming messages.
custom_replies: dict[str, str] = {}

# Bank balances, by user id.
balance_map: dict[int, int] = {}

# Shop inventory: user id -> item name -> count.
inventory: dict[int, dict[str, int]] = {}

# Per-user preferences (bank DM, passive mode).
user_settings_map: dict[int, UserSettings] = {}

# Cooldown bookkeeping: user id -> when they last used the command.
user_worked_times: dict[int, datetime] = {}
user_robbed_times: dict[int, datetime] = {}
user_daily_times: dict[int, datetime] = {}
user_weekly_times: dict[int, datetime] = {}
user_monthly_times: dict[int, datetime] = {}

# Warnings, by guild id -> user id.
warn_map: dict[int, dict[int, Warn]] = {}

# Hacker laptop command history, by user id.
laptop_history: dict[str, list[Any]] = {}

# AI model catalogue, filled from /models when /ai loads. Empty means the
# fallbacks above are in use.
ai_text_models: list[str] = []
ai_image_models: list[str] = []
ai_image_credits: dict[str, int] = {}

# AI conversations, by (channel id, user id). This is chat context rather than
# bot data, so it is never written to MongoDB.
ai_conversations: dict[tuple[int, int], list[dict[str, str]]] = {}

# AI cooldowns and daily counters. The counters reset when ai_usage_day moves
# past the UTC date the API bills on.
ai_text_times: dict[int, datetime] = {}
ai_image_times: dict[int, datetime] = {}
ai_text_usage: dict[int, int] = {}
ai_image_usage: dict[int, int] = {}
ai_text_total: int = 0
ai_image_total: int = 0
ai_usage_day: str = ""
