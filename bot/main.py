"""
Main bot file - Entry point for Maxis
"""

import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Sequence, TypedDict
from dotenv import load_dotenv

import discord
from discord.abc import Snowflake
from discord.app_commands import Command, ContextMenu, Group
from discord.ext import commands
from discord.utils import MISSING
from pymongo import MongoClient

from bot.helper import custom_replies, balance_map, warn_map, get_random_color
from bot.objects.user_settings import UserSettings
from bot.objects.warn import Warn
from bot.objects.shop import Shop

# Ensure the module isn't loaded twice when executed with `python -m bot.main`, resulting in duplicate stale state
sys.modules.setdefault("bot.main", sys.modules[__name__])

# Load environment variables
load_dotenv()

# Bot configuration
TOKEN = os.getenv("TOKEN", "null")
CONNSTR = os.getenv("CONNSTR", "null")
PORT = int(os.getenv("PORT", "8080"))

# Global state
user_worked_times: Dict[int, datetime] = {}
user_robbed_times: Dict[int, datetime] = {}
user_daily_times: Dict[int, datetime] = {}
user_weekly_times: Dict[int, datetime] = {}
user_monthly_times: Dict[int, datetime] = {}
user_settings_map: Dict[int, UserSettings] = {}

# Bot intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.dm_messages = True
intents.guild_messages = True
intents.members = True
# intents.direct_messages = True
# intents.guild_bans = True


# Custom CommandTree to handle global command registration
class MaxisGlobalLinkTree(discord.app_commands.CommandTree):
    """Custom CommandTree to handle global command registration"""

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


# Custom Bot class to use MaxisGlobalLinkTree
class MaxisBot(commands.Bot):
    """Custom Bot class to use MaxisGlobalLinkTree"""

    def __init__(self, command_prefix: str, intents: discord.Intents, **kwargs: Any):
        super().__init__(command_prefix=command_prefix, intents=intents, **kwargs, tree_cls=MaxisGlobalLinkTree)


# Create bot instance (no prefix needed since we're using slash commands only yet add)
bot = MaxisBot(command_prefix=">", intents=intents)


# Make these accessible to other modules
class Main:
    CONNSTR = CONNSTR
    balance_map = balance_map
    user_settings_map = user_settings_map
    user_worked_times = user_worked_times
    user_robbed_times = user_robbed_times
    user_daily_times = user_daily_times
    user_weekly_times = user_weekly_times
    user_monthly_times = user_monthly_times


def init_data():
    """Initialize data from MongoDB"""
    try:


        class GeneralDoc(TypedDict):
            name: str
            key: list[Any]
            val: list[Any]


        class ReplyDoc(TypedDict):
            name: str
            key: list[str]
            val: list[str]


        class WarnDoc(TypedDict):
            name: str
            key: list[int]
            val: list[WarnDocValue]


        class WarnDocValue(TypedDict):
            key: list[int]
            val: list[WarnDocValueValue]


        class WarnDocValueValue(TypedDict):
            id: int
            warns: int
            causes: list[str]


        class BalanceDoc(TypedDict):
            name: str
            key: list[int]
            val: list[int]


        class ItemDoc(TypedDict):
            name: str
            key: list[int]
            val: list[ItemDocValue]


        class ItemDocValue(TypedDict):
            key: list[str]
            val: list[int]


        class WorkDoc(TypedDict):
            name: str
            key: list[int]
            val: list[datetime]


        class RobDoc(TypedDict):
            name: str
            key: list[int]
            val: list[datetime]


        class DailyDoc(TypedDict):
            name: str
            key: list[int]
            val: list[datetime]


        class WeeklyDoc(TypedDict):
            name: str
            key: list[int]
            val: list[datetime]


        class MonthlyDoc(TypedDict):
            name: str
            key: list[int]
            val: list[datetime]


        client = MongoClient[GeneralDoc](CONNSTR)
        db = client["UnknownDatabase"]
        collection = db["UnknownCollection"]

        for doc in collection.find():
            doc_name = doc["name"]

            if doc_name == "reply":
                docReply: ReplyDoc = doc
                custom_replies.clear()
                keys = docReply["key"] or []
                vals = docReply["val"] or []
                for i in range(len(keys)):
                    custom_replies[keys[i]] = vals[i]

            elif doc_name == "warn":
                docWarn: WarnDoc = doc
                warn_map.clear()
                keys = docWarn["key"] or []
                vals = docWarn["val"] or []
                for i in range(len(keys)):
                    server_id = keys[i] or 0
                    warns_data = vals[i] or {}
                    warns_dict = {}
                    keys_inner = warns_data["key"] or []
                    vals_inner = warns_data["val"] or []
                    for i in range(len(keys_inner)):
                        user_id = keys_inner[i] or 0
                        warn_data = vals_inner[i] or {}
                        warn = Warn()
                        warn.user_id = warn_data["id"] or 0
                        warn.warns = warn_data["warns"] or 0
                        warn.warn_causes = warn_data["causes"] or []
                        warns_dict[user_id] = warn
                    warn_map[server_id] = warns_dict

            elif doc_name == "balance":
                docBalance: BalanceDoc = doc
                balance_map.clear()
                keys = docBalance["key"] or []
                vals = docBalance["val"] or []
                for i in range(len(keys)):
                    balance_map[keys[i]] = vals[i]

            elif doc_name == "item":
                docItem: ItemDoc = doc
                Shop.owned_items.clear()
                keys = docItem["key"] or []
                vals = docItem["val"] or []
                for i in range(len(keys)):
                    user_id = keys[i] or 0
                    items_data = vals[i] or {}
                    item_keys = items_data["key"] or []
                    item_vals = items_data["val"] or []
                    items_dict = {}
                    for j in range(len(item_keys)):
                        items_dict[item_keys[j]] = item_vals[j]
                    Shop.owned_items[user_id] = items_dict

            elif doc_name == "work":
                docWork: WorkDoc = doc
                user_worked_times.clear()
                keys = docWork["key"] or []
                vals = docWork["val"] or []
                for i in range(len(keys)):
                    user_worked_times[keys[i]] = vals[i]
                    user_worked_times[keys[i]] = user_worked_times[keys[i]].replace(
                        tzinfo=timezone.utc
                    )

            elif doc_name == "rob":
                docRob: RobDoc = doc
                user_robbed_times.clear()
                keys = docRob["key"] or []
                vals = docRob["val"] or []
                for i in range(len(keys)):
                    user_robbed_times[keys[i]] = vals[i]
                    user_robbed_times[keys[i]] = user_robbed_times[keys[i]].replace(
                        tzinfo=timezone.utc
                    )

            elif doc_name == "daily":
                docDaily: DailyDoc = doc
                user_daily_times.clear()
                keys = docDaily["key"] or []
                vals = docDaily["val"] or []
                for i in range(len(keys)):
                    user_daily_times[keys[i]] = vals[i]
                    user_daily_times[keys[i]] = user_daily_times[keys[i]].replace(
                        tzinfo=timezone.utc
                    )

            elif doc_name == "weekly":
                docWeekly: WeeklyDoc = doc
                user_weekly_times.clear()
                keys = docWeekly["key"] or []
                vals = docWeekly["val"] or []
                for i in range(len(keys)):
                    user_weekly_times[keys[i]] = vals[i]
                    user_weekly_times[keys[i]] = user_weekly_times[keys[i]].replace(
                        tzinfo=timezone.utc
                    )

            elif doc_name == "monthly":
                docMonthly: MonthlyDoc = doc
                user_monthly_times.clear()
                keys = docMonthly["key"] or []
                vals = docMonthly["val"] or []
                for i in range(len(keys)):
                    user_monthly_times[keys[i]] = vals[i]
                    user_monthly_times[keys[i]] = user_monthly_times[keys[i]].replace(
                        tzinfo=timezone.utc
                    )

            elif doc_name == "usersettings":
                continue  # Handled in init_user_settings()

            else:
                print(f"Unknown document '{doc_name}' found! Skipping")

        client.close()
        print("Retrieved all data.")
    except Exception as e:
        print(f"Error initializing data: {e}")


def init_user_settings():
    """Initialize user settings from MongoDB"""
    try:


        class GeneralDoc(TypedDict):
            name: str
            key: list[Any]
            val: list[Any]


        class UserSettingsDoc(TypedDict):
            name: str
            key: list[int]
            val: list[UserSettingsDocValue]


        class UserSettingsDocValue(TypedDict):
            dm: bool
            passive: bool


        client = MongoClient[GeneralDoc](CONNSTR)
        db = client["UnknownDatabase"]
        collection = db["UnknownCollection"]

        for doc in collection.find():
            if doc["name"] == "usersettings":
                docUserSettings: UserSettingsDoc = doc
                user_settings_map.clear()
                keys = docUserSettings["key"] or []
                vals = docUserSettings["val"] or []
                for i in range(len(keys)):
                    user_id = keys[i]
                    settings_data = vals[i]
                    user_settings_map[user_id] = UserSettings(
                        bank_dm_enabled=(
                            settings_data["dm"] if "dm" in settings_data else True
                        ),
                        bank_passive_enabled=(
                            settings_data["passive"]
                            if "passive" in settings_data
                            else False
                        ),
                    )

        client.close()
        print("Retrieved all user settings.")
    except Exception as e:
        print(f"Error initializing user settings: {e}")


async def init_user_settings_async():
    """Initialize user settings for all guild members"""
    for guild in bot.guilds:
        async for member in guild.fetch_members(limit=None):
            if not member.bot and member.id not in user_settings_map:
                user_settings_map[member.id] = UserSettings()


@bot.event
async def on_ready():
    """Called when bot is ready"""
    print(f"{bot.user} has logged in!")

    # Initialize shop
    Shop.init_shop()

    # Initialize user settings from database
    init_user_settings()

    # Initialize user settings for all guild members
    await init_user_settings_async()

    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

    # Set bot activity
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name=" /help")
    )

    # Start web server (after bot is ready so we have bot.user.id)
    from bot.web_server import start_web_server

    start_web_server(bot, PORT)

    # Start Admes server
    from bot.admes_server import init_admes_server

    init_admes_server(12102)

    # Print invite link
    invite_url = discord.utils.oauth_url(
        getattr(bot.user, "id", 0), permissions=discord.Permissions(administrator=True)
    )
    print(f"Invite link for Maxis: {invite_url}")
    print(f"Web server: http://localhost:{PORT}/")
    print("Admes bridge: remote via tunnel (owner: /admes_tunnel to set URL)")


# Import handlers
from bot.slash_commands import setup_slash_commands
from bot.components import ComponentsListener
from bot.modals import ModalsListener
from bot.helper import custom_replies


# Register event handlers
@bot.event
async def on_message(message: discord.Message):
    """Handle custom replies for non-command messages"""
    if message.author.bot:
        return

    # Check for custom replies
    for reply_key in custom_replies.keys():
        if reply_key in message.content:
            await message.channel.send(custom_replies[reply_key])
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


# Setup slash commands
setup_slash_commands(bot)


def cleanup_temp_files():
    """Clean up temporary files created by makefile command"""
    import glob

    try:
        # Get all files in current directory
        for file_path in glob.glob("*"):
            # Skip important files
            if (
                file_path.startswith(".")
                or file_path == "requirements.txt"
                or file_path == "LICENSE"
                or file_path == "README.md"
            ):
                continue

            # Skip directories
            if os.path.isdir(file_path):
                continue

            # Delete temporary files
            try:
                os.remove(file_path)
                print(f"Deleted temporary file: {file_path}")
            except Exception as e:
                print(f"Could not delete {file_path}: {e}")
    except Exception as e:
        print(f"Error during file cleanup: {e}")


if __name__ == "__main__":
    # Clean up temporary files
    cleanup_temp_files()

    # Initialize data from database
    init_data()

    # Run bot (web server and Admes server will start in on_ready event)
    bot.run(TOKEN)
