"""
Rock paper scissors for /utility rps.

The object owns a single throw: what the player picked, what the bot picked,
who won, and how that is shown. Both the slash command and the button handler
build the same game, so neither has to know the rules or the wording.
"""

import random
from enum import Enum

import discord

from bot.helper import get_random_color


class RpsResult(Enum):
    USER_WIN = "user_win"
    BOT_WIN = "bot_win"
    TIE = "tie"
    ERROR = "error"


class RpsGame:
    """One throw of rock paper scissors against the bot."""

    CHOICES = {"r": "Rock", "p": "Paper", "s": "Scissors"}
    BUTTONS = {"rock": "r", "paper": "p", "scissors": "s"}

    _TITLES = {
        RpsResult.USER_WIN: "You win!",
        RpsResult.BOT_WIN: "Bot wins!",
        RpsResult.TIE: "Tie!",
        RpsResult.ERROR: "Error!",
    }

    def __init__(self, user_choice: str) -> None:
        self.asked_for = user_choice
        self.user_choice = user_choice[0].lower() if user_choice else ""
        self.bot_choice = random.choice("rps")
        self.result = self._settle()

    @classmethod
    def from_button(cls, custom_id: str) -> "RpsGame":
        """Play the throw for one of the rock/paper/scissors buttons."""
        return cls(cls.BUTTONS.get(custom_id.removeprefix("rps_"), "rock"))

    def _settle(self) -> RpsResult:
        beats = {"r": "s", "s": "p", "p": "r"}
        if self.user_choice not in self.CHOICES or self.bot_choice not in self.CHOICES:
            return RpsResult.ERROR
        if self.user_choice == self.bot_choice:
            return RpsResult.TIE
        return (
            RpsResult.USER_WIN
            if beats[self.user_choice] == self.bot_choice
            else RpsResult.BOT_WIN
        )

    @property
    def user_name(self) -> str:
        return self.CHOICES.get(self.user_choice, "Unknown")

    @property
    def bot_name(self) -> str:
        return self.CHOICES.get(self.bot_choice, "Unknown")

    def embed(self) -> discord.Embed:
        """The message announcing the result."""
        if self.result is RpsResult.ERROR:
            description = (
                f"You chose {self.asked_for} and bot chose {self.bot_name}."
            )
        else:
            description = (
                f"You chose {self.user_name} and bot chose {self.bot_name}."
            )
        return discord.Embed(
            title=self._TITLES[self.result],
            description=description,
            color=get_random_color(),
        )

    @classmethod
    def choice_embed(cls) -> discord.Embed:
        """The prompt shown before a choice is made."""
        return discord.Embed(
            title="Rock Paper Scissors!",
            description="Select a choice (rock/paper/scissors).",
            color=get_random_color(),
        )

    @classmethod
    def choice_view(cls) -> discord.ui.View:
        """The rock / paper / scissors buttons."""
        view = discord.ui.View()
        for name in cls.BUTTONS:
            view.add_item(
                discord.ui.Button(
                    label=name.title(),
                    style=discord.ButtonStyle.success,
                    custom_id=f"rps_{name}",
                )
            )
        return view