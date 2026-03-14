"""
Hacker Laptop item functionality
"""

from datetime import datetime
import threading
from typing import NotRequired, TypeAlias, TypedDict

import discord
from pymongo import MongoClient

from bot.helper import get_random_color


class CommandHistoryEntry(TypedDict):
    timestamp: str
    command: str
    result: str
    secret1: NotRequired[str]
    secret2: NotRequired[str]
    secret3: NotRequired[str]


HistoryMap: TypeAlias = dict[str, list[CommandHistoryEntry]]


class LaptopHistoryDoc(TypedDict):
    name: str
    key: list[str]
    val: list[list[CommandHistoryEntry]]


# Configuration
MAX_HISTORY_LINES = 8

# Global state
history_map: HistoryMap = {}


def _get_connstr() -> str:
    """Get Mongo connection string lazily to avoid circular imports."""
    from bot.main import Main  # type: ignore

    return Main.CONNSTR


def refresh_laptop_history():
    """Refresh laptop command history in database"""

    def refresh():
        try:
            client = MongoClient[LaptopHistoryDoc](_get_connstr())
            db = client["UnknownDatabase"]
            collection = db["UnknownCollection"]
            keys = list(history_map.keys())
            vals = [history_map[k] for k in keys]
            collection.replace_one(
                {"name": "laptop_history"},
                {"name": "laptop_history", "key": keys, "val": vals},
                upsert=True,
            )
            client.close()
        except Exception as e:
            print(f"Error refreshing laptop command history: {e}")

    threading.Thread(target=refresh, daemon=True).start()


def append_user_cmd_history(
    user_id: int,
    command: str,
    result: str,
    secret1: str | None = None,
    secret2: str | None = None,
    secret3: int | None = None,
):
    """Append one command history entry for a user."""
    key = str(user_id)
    entries = history_map.get(key, [])
    entry: CommandHistoryEntry = {
        "timestamp": str(int(datetime.now().timestamp())),
        "command": command,
        "result": result,
    }
    if secret1 is not None:
        entry["secret1"] = secret1
    if secret2 is not None:
        entry["secret2"] = secret2
    if secret3 is not None:
        entry["secret3"] = str(secret3)

    entries.append(entry)
    history_map[key] = entries
    refresh_laptop_history()


def get_user_cmd_history(
    user_id: int, limit: int = MAX_HISTORY_LINES
) -> list[CommandHistoryEntry]:
    """Get recent command history entries for a specific user."""
    entries = history_map.get(str(user_id), [])
    return entries[-limit:] if entries else []


def get_last_user_cmd(user_id: int) -> CommandHistoryEntry | None:
    """Get the most recent command history entry for a user."""
    entries = history_map.get(str(user_id), [])
    return entries[-1] if entries else None


def format_user_cmd_history(user_id: int, limit: int = MAX_HISTORY_LINES) -> str:
    """Format command history for embed display."""
    history = get_user_cmd_history(user_id, limit)
    if not history:
        return "No commands executed yet."

    formatted: list[str] = []
    for entry in history:
        timestamp = entry.get("timestamp", "0")
        command = entry.get("command", "unknown")
        result = entry.get("result", "")
        formatted.append(f"<t:{timestamp}:f> `{command}` -> {result}")

    return "\n".join(formatted) if formatted else "No commands executed yet."


async def use_laptop(interaction: discord.Interaction):
    """Use hacker laptop item"""
    user_id = interaction.user.id

    embed = discord.Embed(
        title=f"{interaction.user.display_name}'s PC",
        color=get_random_color(),
    )
    embed.add_field(name="OS", value="MaxisOS")
    embed.add_field(name="VPN Status", value="Connected to MaxisVPN")
    embed.add_field(
        name="Command History",
        value=format_user_cmd_history(user_id),
        inline=False,
    )

    view = discord.ui.View()
    view.add_item(
        discord.ui.Button(
            label="Run Command",
            style=discord.ButtonStyle.primary,
            custom_id=f"laptop_cmd_{user_id}",
        )
    )

    await interaction.followup.send(embed=embed, view=view)
