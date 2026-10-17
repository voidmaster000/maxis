"""
Shared helpers for Maxis.

Small, stateless helpers used from more than one place: building replies,
rendering /help, and picking random values. Anything with state or business
rules belongs elsewhere -- data lives in global_state, persistence in
database_sync, balance changes in transactions, and per-feature logic in
bot/objects/.
"""

import random
import zoneinfo

import discord
from discord import app_commands
from discord.ext import commands

from bot import global_state

# --------------------------------------------------------------------------
# Discord helpers
# Small helpers used while building replies and command arguments.
# --------------------------------------------------------------------------


async def reply_error(interaction: discord.Interaction, message: str) -> None:
    """Reply with a short-lived error embed."""
    await interaction.response.send_message(
        embed=discord.Embed(
            title="Error!",
            description=message,
            color=get_random_color(),
        ),
        ephemeral=True,
    )


def get_random_color() -> discord.Colour:
    """Generate a random Discord color"""
    return discord.Colour.from_rgb(
        random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
    )


async def timezone_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[discord.app_commands.Choice[str]]:
    """Autocomplete function for timezones"""

    timezones = zoneinfo.available_timezones()
    choices: list[discord.app_commands.Choice[str]] = []
    for tz in timezones:
        if current.lower() in tz.lower():
            choices.append(discord.app_commands.Choice(name=tz, value=tz))
        if len(choices) >= 25:
            break
    return choices


# --------------------------------------------------------------------------
# /help
# The help categories are the app_commands.Groups registered by the cogs, so
# everything here reads them off the command tree. There is no second list
# to keep in sync, and the order is whatever discord.py registered.
# --------------------------------------------------------------------------


def help_groups(bot: commands.Bot) -> list[app_commands.Group]:
    """The registered help categories, in the order Discord lists them."""
    return [
        command
        for command in bot.tree.get_commands()
        if isinstance(command, app_commands.Group)
    ]


def help_group(bot: commands.Bot, name: str) -> app_commands.Group | None:
    """Look up one category by name, or None if there is no such group."""
    wanted = name.strip().lower()
    return next((group for group in help_groups(bot) if group.name == wanted), None)


def help_category_embed(group: app_commands.Group) -> discord.Embed:
    """Build the help embed for one category, listing its commands."""
    embed = discord.Embed(
        title=f"Maxis {group.name.title()} commands:-",
        color=get_random_color(),
    )

    for command in group.commands:
        if not isinstance(command, app_commands.Command):
            continue
        params = "".join(f" ({param.name})" for param in command.parameters)
        embed.add_field(
            name=f"/{command.qualified_name}{params}",
            value=command.description or "No description.",
            inline=True,
        )
        if len(embed.fields) >= global_state.MAX_HELP_FIELDS:
            break

    return embed


# --------------------------------------------------------------------------
# Random
# Shared random choices and numbers.
# --------------------------------------------------------------------------


def get_random_integer(max_inclusive: int, min_inclusive: int) -> int:
    """Get random integer between min and max (inclusive)"""
    if max_inclusive == min_inclusive:
        return max_inclusive
    if max_inclusive < min_inclusive:
        return 0
    val = random.randint(min_inclusive, max_inclusive)
    return val


def get_random_work() -> str:
    """Get a random work message"""
    return random.choice(global_state.WORKS)
