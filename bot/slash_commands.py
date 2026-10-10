"""
Unified slash command setup

Each category of slash commands lives in its own `GroupCog`, which registers as
an `app_commands.Group` on the tree. That is what lets `/utility help`
discover the categories and their commands straight from the tree.
"""

from discord.ext import commands

from bot.commands.economy_commands import Economy
from bot.commands.image_commands import Image
from bot.commands.moderation_commands import Moderation
from bot.commands.utility_commands import Utility

# Registration order here is the order groups appear in Discord's command list.
COGS = (Utility, Moderation, Economy, Image)


async def setup_slash_commands(bot: commands.Bot):
    """Register every command cog with the bot."""
    for cog_class in COGS:
        await bot.add_cog(cog_class())