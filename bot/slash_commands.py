"""
Unified slash command setup
"""

from discord.ext import commands


def setup_slash_commands(bot: commands.Bot):
    """Setup all slash commands"""
    # Import lazily to avoid circular imports when bot.main loads this module
    from bot.commands import basic_commands, currency_commands, mod_commands

    basic_commands.setup_basic_commands(bot)
    currency_commands.setup_currency_commands(bot)
    mod_commands.setup_mod_commands(bot)
