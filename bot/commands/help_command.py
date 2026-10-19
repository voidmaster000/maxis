"""
The /help command for Maxis.

Help sits at the top level rather than inside a category, because help is not a
category. While it lived under /utility the only way to read a category's own
commands was `/<category> help <category>`, which read badly.

It is a plain tree command rather than a `GroupCog` on purpose: a group is
never invocable on its own, so a group named "help" would only ever be reached
as `/help help`.
"""

from typing import cast

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, View

from bot.core.helper import (
    get_random_color,
    help_category_embed,
    help_group,
    help_groups,
)

PREAMBLE = (
    "Maxis is a multipurpose bot, currently under active development.\n"
    "Every command lives under a category, so they are typed as\n"
    "`/<category> <command>`. Pick one below, or start typing a\n"
    "category after `/help`:"
)

FOOTER = (
    "For more information on the bot, how to use it, or queries\n"
    "about, contact us on our official discord server:-"
    "\nhttps://discord.gg/t79ZyuHr5K/\nOr visit Maxis's website:-"
    "\nhttps://maxis.voidmaster.dev/"
)


async def _category_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    """Suggest the registered help categories."""
    bot = cast(commands.Bot, interaction.client)
    return [
        app_commands.Choice(name=group.name, value=group.name)
        for group in help_groups(bot)
        if current.lower() in group.name
    ]


def add_help_command(bot: commands.Bot) -> None:
    """Register the top-level /help command on the tree."""
    tree = bot.tree

    @tree.command(name="help", description="List the commands, by category")
    @app_commands.describe(category="The category to show help for")
    @app_commands.autocomplete(category=_category_autocomplete)
    async def help(
        interaction: discord.Interaction, category: str | None = None
    ) -> None:
        """Show one category's commands, or the index of categories."""
        # Interaction.client is typed as Client, but for an application
        # command it is always the Bot that owns the command tree.
        tree_owner = cast(commands.Bot, interaction.client)

        if category:
            group = help_group(tree_owner, category)
            if group is not None:
                await interaction.response.send_message(
                    embed=help_category_embed(group)
                )
                return

        # No category, or one that does not exist: show the index.
        groups = help_groups(tree_owner)
        listing = "\n".join(
            f"{index}) {group.name.title()} ```/help {group.name}```"
            for index, group in enumerate(groups, 1)
        )
        embed = discord.Embed(
            title="Maxis help docs",
            description=f"{PREAMBLE}\n\n{listing}\n\n{FOOTER}",
            color=get_random_color(),
        )

        view = View()
        select: Select[View] = Select(
            placeholder="Choose a category...",
            custom_id="help_category",
            options=[
                discord.SelectOption(label=group.name.title(), value=group.name)
                for group in groups
            ],
        )
        view.add_item(select)
        await interaction.response.send_message(embed=embed, view=view)
