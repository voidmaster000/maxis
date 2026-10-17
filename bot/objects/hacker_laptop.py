"""
Hacker laptop item for the shop.

The laptop owns its command history and the PC screen that shows it, so the
shop hook, the modal handler and the screen refresh all describe one machine
instead of each rebuilding the same embed.
"""

import random
from datetime import datetime
from typing import NotRequired, TypedDict

import discord

from bot import database_sync, global_state
from bot.helper import get_random_color


class CommandHistoryEntry(TypedDict):
    timestamp: str
    command: str
    result: str
    secret1: NotRequired[str]
    secret2: NotRequired[str]
    secret3: NotRequired[str]


class LaptopHistory:
    """The commands one user has run on their laptop."""

    def __init__(self, user_id: int) -> None:
        self.user_id = user_id

    @property
    def entries(self) -> list[CommandHistoryEntry]:
        """Every stored entry for this user."""
        return global_state.laptop_history.get(str(self.user_id), [])

    def append(
        self,
        command: str,
        result: str,
        secret1: str | None = None,
        secret2: str | None = None,
        secret3: int | None = None,
    ) -> None:
        """Record one command, and persist the history."""
        entries = self.entries
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
        global_state.laptop_history[str(self.user_id)] = entries
        database_sync.save_laptop_history()

    def recent(
        self, limit: int = global_state.MAX_HISTORY_LINES
    ) -> list[CommandHistoryEntry]:
        """The most recent entries, oldest first."""
        entries = self.entries
        return entries[-limit:] if entries else []

    def last(self) -> CommandHistoryEntry | None:
        """The most recent entry, if there is one."""
        entries = self.entries
        return entries[-1] if entries else None

    def formatted(self, limit: int = global_state.MAX_HISTORY_LINES) -> str:
        """The history as lines ready to drop into an embed field."""
        entries = self.recent(limit)
        if not entries:
            return "No commands executed yet."

        return "\n".join(
            f"<t:{entry.get('timestamp', '0')}:f> `{entry.get('command', 'unknown')}` "
            f"-> {entry.get('result', '')}"
            for entry in entries
        )


class HackerLaptop:
    """The laptop item: its PC screen, and the challenge its code asks."""

    def __init__(self, user_id: int, owner_name: str) -> None:
        self.user_id = user_id
        self.owner_name = owner_name
        self.history = LaptopHistory(user_id)

    def screen(self) -> discord.Embed:
        """The PC screen, with the command history on it."""
        embed = discord.Embed(
            title=f"{self.owner_name}'s PC",
            color=get_random_color(),
        )
        embed.add_field(name="OS", value="MaxisOS")
        embed.add_field(name="VPN Status", value="Connected to MaxisVPN")
        embed.add_field(
            name="Command History",
            value=self.history.formatted(),
            inline=False,
        )
        return embed

    @staticmethod
    def challenge() -> tuple[str, str, int]:
        """A number pattern question, as (question, pattern, answer)."""
        multiplier = random.randint(1, 3)
        adder = random.randint(1, 8)
        current = 0
        pattern: list[int] = []

        for i in range(1, 10):
            current += (multiplier * i) + adder
            pattern.append(current)

        question = "n(i) = n(i - 1) + (i * m) + a, find n(10):"

        return (
            question,
            ", ".join(map(str, pattern)),
            current + (multiplier * 10) + adder,
        )

    @classmethod
    async def open(cls, interaction: discord.Interaction) -> None:
        """Shop hook: boot the laptop and show its screen."""
        laptop = cls(interaction.user.id, interaction.user.display_name)
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="Run Command",
                style=discord.ButtonStyle.primary,
                custom_id=f"laptop_cmd:{laptop.user_id}",
            )
        )
        await interaction.followup.send(embed=laptop.screen(), view=view)
