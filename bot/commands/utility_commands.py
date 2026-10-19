"""
Utility slash commands
"""

import asyncio
import logging
import math
import os
import shutil
import tempfile
import zoneinfo
from datetime import datetime
from typing import NamedTuple

import discord
import requests
from discord import app_commands
from discord.ext import commands

from bot import database_sync, global_state
from bot.currencies import CURRENCY_CODES
from bot.helper import get_random_color, reply_error, timezone_autocomplete
from bot.objects.calculator import Calculator
from bot.objects.rps import RpsGame
from bot.objects.tictactoe import TicTacToe
from bot.objects.user_settings import UserSettings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------

# Discord choice objects for /utility currconv, built from the currency list.
CURRENCY_CHOICES = [
    app_commands.Choice(name=code, value=code) for code in CURRENCY_CODES
]


class Setting(NamedTuple):
    """One toggle on /utility setting, and what it says when flipped."""

    attribute: str
    said: dict[bool, str]


SETTINGS: dict[str, Setting] = {
    "bankdm": Setting(
        "bank_dm_enabled",
        {
            True: "Enabled bank transaction DMs! Now you WILL be DMed about all your bank transactions.",
            False: "Disabled bank transaction DMs! Now you WON'T be DMed about any of your bank transactions.",
        },
    ),
    "passive": Setting(
        "bank_passive_enabled",
        {
            True: "Enabled passive mode! Now NEITHER anyone can rob you, NOR you can rob anyone else.\n"
            "You also CANNOT give money to someone else.",
            False: "Disabled passive mode! Now anyone CAN rob you, and you CAN rob anyone else.\n"
            "You also CAN give money to someone else.",
        },
    ),
}


class Utility(commands.GroupCog):
    """Basic utility slash commands (the /utility category)."""

    @app_commands.command(name="ping", description="Displays bot latency")
    async def ping(self, interaction: discord.Interaction):
        latency = round(interaction.client.latency * 1000)
        embed = discord.Embed(
            title="Pong!",
            description=f"Latency is {latency} ms.",
            color=get_random_color(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="hello", description="Says hello to the user")
    async def hello(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Hello!",
            description=f"Hello there, {interaction.user.name}! Maxis here at your service. "
            f"Type '/help' for more information on supported commands.",
            color=get_random_color(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="datetime", description="Displays the current date and time"
    )
    @app_commands.describe(timezone="Choose which timezone to display the time in")
    @app_commands.autocomplete(timezone=timezone_autocomplete)
    async def datetime_cmd(
        self, interaction: discord.Interaction, timezone: str | None = None
    ):
        nowlocal = datetime.now()
        nowutc = datetime.now(zoneinfo.ZoneInfo("UTC"))
        embed = discord.Embed(title="Current Date & Time:", color=get_random_color())
        embed.add_field(name="Local Time", value=f"<t:{int(nowlocal.timestamp())}:F>")
        embed.add_field(name="UTC/GMT", value=nowutc.strftime("%d %B %Y %I:%M:%S %p"))
        if timezone:
            # The value comes from autocomplete, but it is still just a string a
            # client can send anything for, and ZoneInfo raises on an unknown
            # key rather than returning nothing.
            try:
                zone = zoneinfo.ZoneInfo(timezone)
            except (KeyError, ValueError):
                await reply_error(
                    interaction,
                    f"Unknown timezone '{timezone}'! Pick one from the suggestions.",
                )
                return
            embed.add_field(
                name=timezone,
                value=datetime.now(zone).strftime("%d %B %Y %I:%M:%S %p"),
            )
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------------

    @app_commands.command(name="replies", description="Display all custom replies")
    async def replies(self, interaction: discord.Interaction):
        repl = "\n".join(
            [f"{key}: {val}" for key, val in global_state.custom_replies.items()]
        )
        embed = discord.Embed(
            title="Currently set custom replies:-",
            description=repl if repl else "No custom replies have been set up yet!",
            color=get_random_color(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="botinfo", description="Shows information about Maxis")
    async def botinfo(self, interaction: discord.Interaction):
        roles_text = "None"
        is_bot_admin = False

        if interaction.guild:
            bot_member = interaction.guild.get_member(
                getattr(interaction.client.user, "id", 0)
            )
            if bot_member:
                roles = [
                    role.mention
                    for role in bot_member.roles
                    if role != interaction.guild.default_role
                ]
                roles_text = "\n".join(roles) if roles else "None"
                is_bot_admin = bot_member.guild_permissions.administrator

        embed = discord.Embed(title="Maxis Status:-", color=get_random_color())
        embed.add_field(
            name="Server count", value=str(len(interaction.client.guilds)), inline=True
        )
        embed.add_field(
            name="User count", value=str(len(interaction.client.users)), inline=True
        )

        latency = round(
            0
            if math.isnan(interaction.client.latency)
            else interaction.client.latency * 1000
        )
        embed.add_field(name="Ping", value=f"Gateway ping: {latency} ms", inline=True)
        embed.add_field(name="Roles", value=roles_text, inline=True)
        embed.add_field(
            name="Is bot admin?", value="Yes" if is_bot_admin else "No", inline=True
        )

        invite_url = discord.utils.oauth_url(
            getattr(interaction.client.user, "id", 0),
            permissions=discord.Permissions(administrator=True),
        )
        embed.add_field(name="Invite Link", value=invite_url, inline=True)
        embed.add_field(name="Version", value=global_state.VERSION, inline=True)
        embed.add_field(
            name="Bot server", value="https://maxis.voidmaster.dev/", inline=True
        )
        embed.add_field(
            name="Bot discord server",
            value="https://discord.gg/t79ZyuHr5K",
            inline=True,
        )
        embed.add_field(
            name="Bot type", value="Utility, Moderation and Economy Bot", inline=True
        )
        embed.add_field(name="Developer", value="voidmaster000", inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="userinfo",
        description="Shows mentioned user's info, or yours if not specified",
    )
    @app_commands.describe(user="The user whose information you want to see")
    async def userinfo(
        self, interaction: discord.Interaction, user: discord.User | None = None
    ):
        target_user = user or interaction.user

        roles_text = "None"
        is_user_admin = False

        if interaction.guild:
            member = interaction.guild.get_member(target_user.id)
            if member:
                roles = [
                    role.mention
                    for role in member.roles
                    if role != interaction.guild.default_role
                ]
                roles_text = "\n".join(reversed(roles)) if roles else "None"
                is_user_admin = member.guild_permissions.administrator

        embed = discord.Embed(
            title=f"Information about {(target_user.display_name if interaction.guild else target_user.name)}:-",
            color=get_random_color(),
        )

        if interaction.guild:
            embed.set_image(url=target_user.display_avatar.url)
        else:
            embed.set_image(url=target_user.avatar.url if target_user.avatar else None)

        embed.add_field(name="Discriminated name:", value=str(target_user), inline=True)
        embed.add_field(name="User ID:", value=str(target_user.id), inline=True)
        embed.add_field(
            name="Is bot?:", value="Yes" if target_user.bot else "No", inline=True
        )
        embed.add_field(
            name="Account created:",
            value=f"<t:{int(target_user.created_at.timestamp())}:F>",
            inline=True,
        )

        if interaction.guild:
            member = interaction.guild.get_member(target_user.id)
            if member and member.joined_at:
                embed.add_field(
                    name="Joined server:",
                    value=f"<t:{int(member.joined_at.timestamp())}:F>",
                    inline=True,
                )

        embed.add_field(name="Roles:", value=roles_text, inline=True)
        embed.add_field(
            name="Is server admin?:",
            value="Yes" if is_user_admin else "No",
            inline=True,
        )

        if target_user.id == 783667580106702848:  # Bot owner ID
            embed.add_field(name="Is bot owner?:", value="Yes", inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="serverinfo", description="Shows the server's info on which command is run"
    )
    async def serverinfo(self, interaction: discord.Interaction):
        if not interaction.guild:
            embed = discord.Embed(
                title="Error!",
                description="This command only works in servers!",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed)
            return

        bots = sum(1 for m in interaction.guild.members if m.bot)
        humans = len(interaction.guild.members) - bots

        embed = discord.Embed(
            title=f"Information about {interaction.guild.name}:-",
            color=get_random_color(),
        )

        if interaction.guild.icon:
            embed.set_image(url=interaction.guild.icon.url)

        embed.add_field(name="Server ID:", value=str(interaction.guild.id), inline=True)
        embed.add_field(
            name="Server owner:",
            value=(
                interaction.guild.owner.display_name
                if interaction.guild.owner
                else "Not found!"
            ),
            inline=True,
        )
        embed.add_field(
            name="Server description:",
            value=interaction.guild.description or "None",
            inline=False,
        )
        embed.add_field(
            name="Created on:",
            value=f"<t:{int(interaction.guild.created_at.timestamp())}:F>",
            inline=False,
        )
        embed.add_field(
            name="Members count:",
            value=str(interaction.guild.member_count),
            inline=True,
        )
        embed.add_field(
            name="Members ratio:", value=f"{humans} Humans\n{bots} Bots", inline=True
        )
        embed.add_field(
            name="Roles count:", value=str(len(interaction.guild.roles)), inline=True
        )
        embed.add_field(
            name="Channels count:",
            value=str(len(interaction.guild.channels)),
            inline=True,
        )

        text_channels = len(
            [
                c
                for c in interaction.guild.channels
                if isinstance(c, discord.TextChannel)
            ]
        )
        voice_channels = len(
            [
                c
                for c in interaction.guild.channels
                if isinstance(c, discord.VoiceChannel)
            ]
        )
        embed.add_field(
            name="Channels ratio:",
            value=f"{text_channels} Text\n{voice_channels} Voice",
            inline=True,
        )
        embed.add_field(
            name="Boosts count:",
            value=str(interaction.guild.premium_subscription_count),
            inline=True,
        )
        embed.add_field(
            name="Boost level:", value=str(interaction.guild.premium_tier), inline=True
        )
        embed.add_field(
            name="Emojis count:", value=str(len(interaction.guild.emojis)), inline=True
        )
        embed.add_field(
            name="Verification level:",
            value=str(interaction.guild.verification_level),
            inline=True,
        )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="makefile",
        description="Creates a new file with the specified name and content",
    )
    @app_commands.describe(
        filename="The name to give the file", content="The content of the file"
    )
    async def makefile(
        self, interaction: discord.Interaction, filename: str, content: str
    ):
        # The file always lands in a throwaway temp directory, so `filename` is
        # only ever used as the download name and can never escape it.
        safe_name = os.path.basename(filename.strip().replace("\\", "/")).strip()
        if not safe_name or safe_name in (".", ".."):
            await reply_error(interaction, "Please give a valid file name!")
            return

        size = len(content.encode("utf-8"))
        if size > global_state.MAX_ATTACHMENT_BYTES:
            limit_mb = global_state.MAX_ATTACHMENT_BYTES // (1024 * 1024)
            await reply_error(
                interaction,
                f"That file is {size // (1024 * 1024)} MB, which is over the {limit_mb} MB limit!",
            )
            return

        temp_dir = tempfile.mkdtemp(prefix="maxis-makefile-")
        try:
            path = os.path.join(temp_dir, safe_name)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            embed = discord.Embed(
                title="Success!",
                description=f"Here's your file `{safe_name}`",
                color=get_random_color(),
            )
            # filename= keeps the name the user asked for in the download.
            # File holds the handle open, so it has to be closed before the
            # temp dir can be removed.
            attachment = discord.File(path, filename=safe_name)
            try:
                await interaction.response.send_message(
                    embed=embed,
                    file=attachment,
                )
            finally:
                attachment.close()
        except Exception:
            await reply_error(interaction, "Failed to create file! Please try again.")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @app_commands.command(
        name="calculate", description="Solve a mathematical expression"
    )
    @app_commands.describe(expression="The expression to solve (brackets supported)")
    async def calculate(
        self,
        interaction: discord.Interaction,
        expression: str,
    ):
        result = Calculator(expression).evaluate()
        if result.success:
            embed = discord.Embed(
                title="Success!",
                description=f"The result of `{expression}` is `{result.result}`",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed)
        else:
            await reply_error(
                interaction, f"Failed to calculate `{expression}`: {result.error}"
            )

    @app_commands.command(name="reply", description="Set a custom reply")
    @app_commands.describe(
        text="The text to trigger the reply", reply="The reply message"
    )
    async def set_custom_reply(
        self, interaction: discord.Interaction, text: str, reply: str
    ):
        if text and reply:
            global_state.custom_replies[text] = reply
            database_sync.save_replies()
            embed = discord.Embed(
                title="Success!",
                description=f"Successfully set custom reply! Bot will now reply with '{reply}' "
                f"when any message contains '{text}'.",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed)
        else:
            await reply_error(interaction, "Both text and reply are required!")

    @app_commands.command(name="noreply", description="Disable a custom reply")
    @app_commands.describe(text="The text of the reply to disable")
    async def no_reply(self, interaction: discord.Interaction, text: str):
        removed = False
        for key in list(global_state.custom_replies.keys()):
            if key in text or text in key:
                del global_state.custom_replies[key]
                database_sync.save_replies()
                removed = True
                embed = discord.Embed(
                    title="Success!",
                    description=f"Successfully disabled custom reply {key}!",
                    color=get_random_color(),
                )
                await interaction.response.send_message(embed=embed)
                break

        if not removed:
            embed = discord.Embed(
                title="Error!",
                description=f"No reply matching '{text}' was found!",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="dm", description="DMs a message to a user")
    @app_commands.describe(
        user="The user to DM", dm_message="The message to DM to the user"
    )
    async def dm(
        self, interaction: discord.Interaction, user: discord.User, dm_message: str
    ):
        embed = discord.Embed(
            title=(
                f"Alert! Message from {interaction.user.name} at {interaction.guild.name} :-"
                if interaction.guild
                else f"Alert! Message from {interaction.user.name} :-"
            ),
            description=dm_message,
            color=get_random_color(),
        )

        try:
            await user.send(embed=embed)
            success_embed = discord.Embed(
                title="Success!",
                description="Successfully DM-ed message to user.",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=success_embed)
        except discord.Forbidden:
            error_embed = discord.Embed(
                title="Error!",
                description="DM to user failed (Possible reason: User's DMs are closed).",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=error_embed)

    @app_commands.command(
        name="rps", description='Play "Rock Paper Scissors" with the bot'
    )
    @app_commands.describe(choice="Your choice (rock, paper, or scissors)")
    @app_commands.choices(
        choice=[
            app_commands.Choice(name="Rock", value="rock"),
            app_commands.Choice(name="Paper", value="paper"),
            app_commands.Choice(name="Scissors", value="scissors"),
        ]
    )
    async def rps(self, interaction: discord.Interaction, choice: str | None = None):
        if choice:
            await interaction.response.send_message(embed=RpsGame(choice).embed())
        else:
            await interaction.response.send_message(
                embed=RpsGame.choice_embed(),
                view=RpsGame.choice_view(),
            )

    @app_commands.command(name="setting", description="Changes your user settings")
    @app_commands.describe(
        type="The type of setting to change", value="The value of the setting"
    )
    @app_commands.choices(
        type=[
            app_commands.Choice(name="Bank transaction DM", value="bankdm"),
            app_commands.Choice(name="Passive mode", value="passive"),
        ]
    )
    @app_commands.choices(
        value=[
            app_commands.Choice(name="Enabled", value="true"),
            app_commands.Choice(name="Disabled", value="false"),
        ]
    )
    async def change_user_settings(
        self, interaction: discord.Interaction, type: str, value: str
    ):
        user_id = interaction.user.id
        settings = global_state.user_settings_map.setdefault(user_id, UserSettings())

        enabled = {"true": True, "false": False}.get(value)
        if enabled is None:
            await reply_error(
                interaction,
                "Incorrect arguments given! Use 'true' or 'false' for the value.",
            )
            return

        setting = SETTINGS.get(type)
        if setting is None:
            await reply_error(interaction, f"Setting type {type} not found!")
            return

        setattr(settings, setting.attribute, enabled)
        global_state.user_settings_map[user_id] = settings
        database_sync.save_user_settings()

        await interaction.response.send_message(
            embed=discord.Embed(
                title="Success!",
                description=setting.said[enabled],
                color=get_random_color(),
            )
        )

    @app_commands.command(
        name="currconv", description="Converts one currency to another"
    )
    @app_commands.describe(
        convert_amount="The amount of money to convert",
        from_currency="The currency of the given amount (e.g., USD, EUR)",
        to_currency="The currency to convert the amount to (e.g., USD, EUR)",
    )
    @app_commands.choices(from_currency=CURRENCY_CHOICES, to_currency=CURRENCY_CHOICES)
    async def currency_convert(
        self,
        interaction: discord.Interaction,
        convert_amount: float,
        from_currency: str,
        to_currency: str,
    ):
        await interaction.response.defer()

        # Validate currencies against the fixed list
        valid_codes = CURRENCY_CODES
        if not valid_codes:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error!",
                    description="Could not load currency list!",
                    color=get_random_color(),
                )
            )
            return

        if (
            from_currency.upper() not in valid_codes
            or to_currency.upper() not in valid_codes
        ):
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error!",
                    description=f"Invalid currency code! Valid codes: {', '.join(valid_codes[:10])}...",
                    color=get_random_color(),
                )
            )
            return

        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        # Get exchange rate API key from environment
        exchange_api_key = global_state.EXAPI
        if not exchange_api_key:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error!",
                    description="Exchange rate API key not configured! Please set EXAPI environment variable.",
                    color=get_random_color(),
                )
            )
            return

        # Call exchange rate API
        try:
            url = f"https://v6.exchangerate-api.com/v6/{exchange_api_key}/pair/{from_currency}/{to_currency}/{convert_amount}"
            # requests blocks, so keep it off the event loop
            response = await asyncio.to_thread(requests.get, url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get("result") != "error":
                    converted_amount = data.get("conversion_result")
                    embed = discord.Embed(
                        title=f"{from_currency} to {to_currency} conversion:-",
                        description=f"{convert_amount} {from_currency} = {converted_amount} {to_currency}",
                        color=get_random_color(),
                    )
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="Error!",
                            description="Conversion failed!",
                            color=get_random_color(),
                        )
                    )
            else:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Error!",
                        description="Failed to connect to exchange rate API!",
                        color=get_random_color(),
                    )
                )
        except Exception:
            logger.exception("Error in currency conversion")
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error!",
                    description="Conversion failed! Please try again.",
                    color=get_random_color(),
                )
            )

    @app_commands.command(name="ttt", description="Play Tic Tac Toe with the bot")
    async def ttt(self, interaction: discord.Interaction):
        await interaction.response.defer()

        game = TicTacToe()
        await interaction.followup.send(
            embed=game.embed(), view=game.view(interaction.user.id)
        )
