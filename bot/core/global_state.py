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

VERSION: str = "5.1.2"

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
