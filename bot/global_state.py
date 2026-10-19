"""
Global configuration and runtime state for Maxis.

Every module-level tuning constant in the project lives here, so there is one
place to look and one place to change. Below the constants sits the mutable data
the cogs share; persistence of that data is handled by `bot.database_sync`, and
balance changes by `bot.transactions`.

Reference data that has to be read from disk is deliberately *not* here:
`global_state` is imported by everything, so it stays free of file I/O. The
currency list lives in `bot.currencies` instead.

This module imports nothing from the rest of the bot except `bot.objects`,
which are plain data classes. That is what lets every cog do a plain
module-level `from bot import global_state` without creating an import cycle.
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

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
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


# ---------------------------------------------------------------------------
# Mutable runtime state
#
# Loaded from the database at startup and persisted by bot.database_sync.
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
