"""
Main bot file - Entry point for Maxis
"""

import asyncio
import threading
from collections.abc import Sequence
from typing import Any

import discord
import uvicorn
from discord.abc import Snowflake
from discord.app_commands import Command, ContextMenu, Group
from discord.ext import commands
from discord.utils import MISSING
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from bot import database_sync, global_state
from bot.commands.economy_commands import Economy
from bot.commands.help_command import add_help_command
from bot.commands.image_commands import Image
from bot.commands.moderation_commands import Moderation
from bot.commands.utility_commands import Utility
from bot.components_listener import ComponentsListener
from bot.helper import get_random_color
from bot.modals_listener import ModalsListener
from bot.objects.user_settings import UserSettings

# Each category of slash commands is a GroupCog, which registers as an
# app_commands.Group on the tree. This order is the order the groups appear in
# Discord's command list, and what /help shows. /help itself is registered
# separately, as a plain top-level command rather than a category.
COGS = (Utility, Moderation, Economy, Image)

# Guards against registering the command cogs twice (on_ready can fire again)
_cogs_loaded = False

# The rest of the start-up work only makes sense once. on_ready fires again on
# every reconnect, and re-reading the database and re-fetching every member of
# every guild on each one costs a lot of API quota for no new information.
_initialised = False


async def setup_slash_commands(bot: commands.Bot) -> None:
    """Register every command cog, plus the top-level /help command."""
    for cog_class in COGS:
        await bot.add_cog(cog_class())
    add_help_command(bot)


# Bot intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.dm_messages = True
intents.guild_messages = True


# Custom CommandTree to handle global command registration
class MaxisCommandTree(discord.app_commands.CommandTree):
    """Command tree that makes every command usable everywhere.

    Each command is installed to guilds and to user accounts, and works in
    servers, DMs and group DMs.
    """

    def add_command(
        self,
        command: Command[Any, ..., Any] | ContextMenu | Group,
        /,
        *,
        guild: Snowflake | None = MISSING,
        guilds: Sequence[Snowflake] = MISSING,
        override: bool = False,
    ) -> None:
        # Add server, DM and Group DM support
        command.allowed_installs = discord.app_commands.AppInstallationType(
            guild=True, user=True
        )
        command.allowed_contexts = discord.app_commands.AppCommandContext(
            guild=True, dm_channel=True, private_channel=True
        )
        # Pass after modification to superclass add_command
        super().add_command(command, guild=guild, guilds=guilds, override=override)


# Maxis is slash-command only. There are no prefix commands, so discord.py's
# built-in `>help` is turned off -- it walks Cog.__cog_commands__, which a
# GroupCog never populates, so it could not document these commands anyway.
# `/help` is registered separately in bot.commands.help_command.
#
# command_prefix is still required by discord.py and there is nothing left for
# it to match, so it stays inert at ">" rather than "" (which would try to
# parse every ordinary message as a command).
bot = commands.Bot(
    command_prefix=">",
    intents=intents,
    help_command=None,
    tree_cls=MaxisCommandTree,
)


async def ensure_user_settings() -> None:
    """Give every guild member a default settings entry."""
    for guild in bot.guilds:
        async for member in guild.fetch_members(limit=None):
            if not member.bot and member.id not in global_state.user_settings_map:
                global_state.user_settings_map[member.id] = UserSettings()


@bot.event
async def on_ready():
    """Called when bot is ready"""
    global _cogs_loaded, _initialised

    print(f"{bot.user} has logged in!")

    # Cogs must be registered before the command tree can be synced.
    # on_ready can fire again after a reconnect, and re-adding a cog raises.
    if not _cogs_loaded:
        await setup_slash_commands(bot)
        _cogs_loaded = True

    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name=" /help")
    )

    if not _initialised:
        _initialised = True

        # Reading the database is blocking Mongo I/O. Called straight from the
        # event loop it stalls every other command for as long as the server
        # takes to answer -- up to serverSelectionTimeoutMS, five seconds,
        # which is well past the three seconds Discord allows for a first
        # response. An interaction that is not answered in that window is dead
        # and Discord rejects it with error 10062, Unknown interaction.
        # A thread keeps the loop free to answer while the read happens.
        await asyncio.to_thread(database_sync.load_all)
        await ensure_user_settings()

        try:
            synced = await bot.tree.sync()
            print(f"Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

    # Start web server (after bot is ready so we have bot.user.id)
    _start_status_page()

    invite_url = discord.utils.oauth_url(
        getattr(bot.user, "id", 0), permissions=discord.Permissions(administrator=True)
    )
    print(f"Invite link for Maxis: {invite_url}")
    print(f"Web server: http://localhost:{global_state.PORT}/")


@bot.event
async def on_message(message: discord.Message):
    """Handle custom replies for non-command messages"""
    if message.author.bot:
        return

    # Check for custom replies. Snapshot the keys: sending the reply awaits,
    # and /utility reply could add one while we are waiting.
    for reply_key in list(global_state.custom_replies):
        if reply_key in message.content:
            await message.channel.send(global_state.custom_replies[reply_key])
            break

    # Check for bot mentions
    if message.mentions:
        for user in message.mentions:
            if user.id == getattr(bot.user, "id", 0):
                embed = discord.Embed(
                    title="Info!",
                    description="I use slash commands! Type `/` to see available commands.",
                    color=get_random_color(),
                )
                await message.channel.send(embed=embed)
                break


@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        await ComponentsListener.on_interaction(interaction)
    elif interaction.type == discord.InteractionType.modal_submit:
        await ModalsListener.on_modal_submit(interaction)


# ---------------------------------------------------------------------------
# Status web page (FastAPI)
#
# A tiny background HTTP server that renders resources/index.html. It shares
# nothing with the bot apart from the guild count, so it just holds a reference.
# ---------------------------------------------------------------------------

web_app = FastAPI()
web_templates = Jinja2Templates(directory=str(global_state.resource_path(".")))
web_app.mount(
    "/public",
    StaticFiles(directory=str(global_state.resource_path("public"))),
    name="public",
)


@web_app.get("/", response_class=HTMLResponse)
async def status_page(request: Request):
    """Render the public status page."""
    guild_count = len(bot.guilds) if bot.is_ready() else 0
    return web_templates.TemplateResponse(
        request,
        "index.html",
        {
            "invite_url": global_state.INVITE_URL,
            "status": f"Online - {guild_count} servers",
            "version": global_state.VERSION,
        },
    )


def _start_status_page() -> None:
    """Serve the status page on a daemon thread."""

    def run() -> None:
        uvicorn.run(web_app, host="0.0.0.0", port=global_state.PORT, log_level="info")

    threading.Thread(target=run, daemon=True).start()
    print(f"Web server started on http://localhost:{global_state.PORT}/")


if __name__ == "__main__":
    database_sync.load_all()
    try:
        bot.run(global_state.TOKEN)
    finally:
        # the writer is a daemon thread, so anything still queued would be lost
        database_sync.close()