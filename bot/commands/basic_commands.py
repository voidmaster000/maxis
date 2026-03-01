"""
Basic utility slash commands
"""

import json
import math
import os
import random
import requests
from datetime import datetime, timezone
from typing import Optional
from io import BytesIO

import discord
from discord import app_commands
from discord.ui import Select, View
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

from bot.helper import (
    get_random_color,
    solve_expression,
    VERSION,
    custom_replies,
    refresh_replies,
    get_win_status,
    get_choice_name,
    get_random_integer,
    refresh_user_settings,
    resource_path,
)
from bot.objects.user_settings import UserSettings


def _load_currency_codes():
    """Load currency codes from JSON for slash command choices."""
    try:
        currencies_path = resource_path("currencies.json")
        with open(currencies_path, "r") as f:
            data = json.load(f)
        return [
            entry["code"] for entry in data.get("currencies", []) if "code" in entry
        ]
    except Exception as e:
        print(f"Failed to load currency codes: {e}")
        return []


CURRENCY_CODES = _load_currency_codes()
CURRENCY_CHOICES = [
    app_commands.Choice(name=code, value=code) for code in CURRENCY_CODES
]

# Owner-only checks (fallbacks to known owner ID if env is missing)
OWNER_USER_ID = int(os.getenv("OWNER_USER_ID", "783667580106702848"))


def _get_main():
    """Lazy import Main to avoid circular import when setting up slash commands."""
    from bot.main import Main  # type: ignore

    return Main


def setup_basic_commands(bot: commands.Bot):
    """Setup basic utility slash commands"""
    Main = _get_main()

    @bot.tree.command(name="ping", description="Displays bot latency")
    async def ping(interaction: discord.Interaction):
        latency = round(bot.latency * 1000)
        embed = discord.Embed(
            title="Pong!",
            description=f"Latency is {latency} ms.",
            color=get_random_color(),
        )
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="hello", description="Says hello to the user")
    async def hello(interaction: discord.Interaction):
        embed = discord.Embed(
            title="Hello!",
            description=f"Hello there, {interaction.user.name}! Maxis here at your service. "
            f"Type '/help' for more information on supported commands.",
            color=get_random_color(),
        )
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(
        name="datetime", description="Displays the current UTC or GMT date and time"
    )
    async def datetime_cmd(interaction: discord.Interaction):
        nowlocal = datetime.now()
        nowutc = datetime.now(timezone.utc)
        embed = discord.Embed(title="Current Time:-", color=get_random_color())
        embed.add_field(name="Local Time", value=f"<t:{int(nowlocal.timestamp())}:F>")
        embed.add_field(name="UTC/GMT", value=nowutc.strftime("%d %B %Y %I:%M:%S %p"))
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="help", description="Display help message")
    @app_commands.describe(
        category="The category to get help for (utility, moderation, economy)"
    )
    @app_commands.choices(
        category=[
            app_commands.Choice(name="Utility", value="utility"),
            app_commands.Choice(name="Moderation", value="moderation"),
            app_commands.Choice(name="Economy", value="economy"),
        ]
    )
    async def help(interaction: discord.Interaction, category: Optional[str] = None):
        try:
            with open(resource_path("commands.json"), "r") as f:
                commands_data = json.load(f)

            if category and category.lower() in ["utility", "moderation", "economy"]:
                cat = category.lower()
                title_map = {
                    "utility": "Maxis Utility commands:-",
                    "moderation": "Maxis Moderation commands:-",
                    "economy": "Maxis Economy commands:-",
                }
                embed = discord.Embed(title=title_map[cat], color=get_random_color())
                for cmd in commands_data[cat]:
                    embed.add_field(name=cmd["name"], value=cmd["desc"], inline=True)
                await interaction.response.send_message(embed=embed)
            else:
                embed = discord.Embed(
                    title="Maxis help docs",
                    description="""Maxis is a multipurpose bot, currently under active development.
To get help about commands, select one category below or use '/help (category)', where categories include:

1) Utility ```/help utility```
2) Moderation ```/help moderation```
3) Economy ```/help economy```

For more information on the bot, how to use it, or queries about, contact us on our official discord server:-
https://discord.gg/t79ZyuHr5K/
Or visit Maxis's website:-
https://user783667580106702848.pepich.de/""",
                    color=get_random_color(),
                )

                view = View()
                select = Select(
                    placeholder="Choose a category...",
                    custom_id="help_category",
                    options=[
                        discord.SelectOption(label="Utility", value="utility"),
                        discord.SelectOption(label="Moderation", value="moderation"),
                        discord.SelectOption(label="Economy", value="economy"),
                    ],
                )
                view.add_item(select)
                await interaction.response.send_message(embed=embed, view=view)
        except Exception as e:
            print(f"Error in help command: {e}")
            await interaction.response.send_message(
                "Error loading help!", ephemeral=True
            )

    @bot.tree.command(name="replies", description="Display all custom replies")
    async def replies(interaction: discord.Interaction):
        repl = "\n".join([f"{key}: {val}" for key, val in custom_replies.items()])
        embed = discord.Embed(
            title="Currently set custom replies:-",
            description=repl if repl else "No custom replies have been set up yet!",
            color=get_random_color(),
        )
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="botinfo", description="Shows information about Maxis")
    async def botinfo(interaction: discord.Interaction):
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
        embed.add_field(name="Version", value=VERSION, inline=True)
        embed.add_field(
            name="Bot discord server",
            value="https://discord.gg/t79ZyuHr5K",
            inline=True,
        )
        embed.add_field(
            name="Bot type", value="Utility, Moderation and Economy Bot", inline=True
        )
        embed.add_field(name="Developer", value="unknownpro56", inline=True)

        await interaction.response.send_message(embed=embed)

    @bot.tree.command(
        name="userinfo",
        description="Shows mentioned user's info, or yours if not specified",
    )
    @app_commands.describe(user="The user whose information you want to see")
    async def userinfo(
        interaction: discord.Interaction, user: Optional[discord.User] = None
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

    @bot.tree.command(
        name="serverinfo", description="Shows the server's info on which command is run"
    )
    async def serverinfo(interaction: discord.Interaction):
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

    @bot.tree.command(name="admes", description="Ask anything to the bot")
    @app_commands.describe(query="The question to ask the bot")
    async def admes(interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        from bot.admes_server import send_query

        # Log the query
        if interaction.guild:
            print(
                f"'{interaction.user.name}' asked in '{interaction.guild.name}': {query}"
            )
        else:
            print(f"'{interaction.user.name}' asked: {query}")

        # Send query to Admes server
        reply = send_query(query)

        if reply:
            embed = discord.Embed(title=f"Reply: {reply}", color=get_random_color())
        else:
            embed = discord.Embed(
                title="Error!",
                description="Could not connect to Admes server or no response received. Please make sure the Admes server is running.",
                color=get_random_color(),
            )

        await interaction.followup.send(embed=embed)

    @bot.tree.command(
        name="admes_tunnel",
        description="Owner only: set or view the Admes tunnel URL",
    )
    @app_commands.describe(url="Optional: set a new tunnel base URL")
    async def admes_tunnel(interaction: discord.Interaction, url: Optional[str] = None):
        if interaction.user.id != OWNER_USER_ID:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Unauthorized",
                    description="This command is restricted to the bot owner.",
                    color=get_random_color(),
                ),
                ephemeral=True,
            )
            return

        from bot.admes_server import get_tunnel_url, set_tunnel_url

        if url:
            set_tunnel_url(url)
            description = f"Tunnel URL set to: {url}"
        else:
            current = get_tunnel_url()
            description = (
                current
                if current
                else "Tunnel URL is not configured. Run /admes_tunnel <url> to set it."
            )

        embed = discord.Embed(
            title="Admes tunnel URL",
            description=description,
            color=get_random_color(),
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @bot.tree.command(
        name="makefile",
        description="Creates a new file with the specified name and content",
    )
    @app_commands.describe(
        filename="The name of the file to create", content="The content of the file"
    )
    async def makefile(interaction: discord.Interaction, filename: str, content: str):
        try:
            if (
                filename == ".env"
                or filename == ".gitignore"
                or filename == "requirements.txt"
                or filename == "LICENSE"
                or filename == "README.md"
            ):
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="Error!",
                        description="System file cannot be modified!",
                        color=get_random_color(),
                    ),
                    ephemeral=True,
                )
                return

            # Create file
            with open(filename, "w") as f:
                f.write(content)

            # Send file
            embed = discord.Embed(
                title="Success!",
                description="Here's your file",
                color=get_random_color(),
            )
            await interaction.response.send_message(
                embed=embed, file=discord.File(filename)
            )

            # Clean up
            os.remove(filename)
        except Exception as e:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error!",
                    description="Failed to create file! Please try again.",
                    color=get_random_color(),
                ),
                ephemeral=True,
            )

    @bot.tree.command(name="calculate", description="Solve a mathematical expression")
    @app_commands.describe(expression="The expression to solve (brackets supported)")
    async def calculate(
        interaction: discord.Interaction,
        expression: str,
    ):
        result = solve_expression(expression)
        if result.success:
            embed = discord.Embed(
                title="Success!",
                description=f"The result of `{expression}` is `{result.result}`",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error!",
                    description=f"Failed to calculate `{expression}`: {result.error}",
                    color=get_random_color(),
                ),
                ephemeral=True,
            )

    @bot.tree.command(name="reply", description="Set a custom reply")
    @app_commands.describe(
        text="The text to trigger the reply", reply="The reply message"
    )
    async def set_custom_reply(interaction: discord.Interaction, text: str, reply: str):
        if text and reply:
            custom_replies[text] = reply
            refresh_replies(Main.CONNSTR)
            embed = discord.Embed(
                title="Success!",
                description=f"Successfully set custom reply! Bot will now reply with '{reply}' "
                f"when any message contains '{text}'.",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error!",
                    description="Both text and reply are required!",
                    color=get_random_color(),
                ),
                ephemeral=True,
            )

    @bot.tree.command(name="noreply", description="Disable a custom reply")
    @app_commands.describe(text="The text of the reply to disable")
    async def no_reply(interaction: discord.Interaction, text: str):
        removed = False
        for key in list(custom_replies.keys()):
            if key in text or text in key:
                del custom_replies[key]
                refresh_replies(Main.CONNSTR)
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

    @bot.tree.command(name="dm", description="DMs a message to a user")
    @app_commands.describe(
        user="The user to DM", dm_message="The message to DM to the user"
    )
    async def dm(interaction: discord.Interaction, user: discord.User, dm_message: str):
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

    @bot.tree.command(name="rps", description='Play "Rock Paper Scissors" with the bot')
    @app_commands.describe(choice="Your choice (rock, paper, or scissors)")
    @app_commands.choices(
        choice=[
            app_commands.Choice(name="Rock", value="rock"),
            app_commands.Choice(name="Paper", value="paper"),
            app_commands.Choice(name="Scissors", value="scissors"),
        ]
    )
    async def rps(interaction: discord.Interaction, choice: Optional[str] = None):
        if choice:
            user_choice = choice[0].lower()
            int_choice = get_random_integer(2, 0)
            bot_choices = ["r", "p", "s"]
            bot_choice = bot_choices[int_choice]
            win_status = get_win_status(bot_choice, user_choice)

            if win_status.value == "user_win":
                embed = discord.Embed(
                    title="You win!",
                    description=f"You chose {get_choice_name(user_choice)} and bot chose {get_choice_name(bot_choice)}.",
                    color=get_random_color(),
                )
            elif win_status.value == "bot_win":
                embed = discord.Embed(
                    title="Bot wins!",
                    description=f"You chose {get_choice_name(user_choice)} and bot chose {get_choice_name(bot_choice)}.",
                    color=get_random_color(),
                )
            elif win_status.value == "tie":
                embed = discord.Embed(
                    title="Tie!",
                    description=f"You chose {get_choice_name(user_choice)} and bot chose {get_choice_name(bot_choice)}.",
                    color=get_random_color(),
                )
            else:
                embed = discord.Embed(
                    title="Error!",
                    description=f"You chose {choice} and bot chose {get_choice_name(bot_choice)}.",
                    color=get_random_color(),
                )
            await interaction.response.send_message(embed=embed)
        else:
            view = discord.ui.View()
            view.add_item(
                discord.ui.Button(
                    label="Rock",
                    style=discord.ButtonStyle.success,
                    custom_id="rps_rock",
                )
            )
            view.add_item(
                discord.ui.Button(
                    label="Paper",
                    style=discord.ButtonStyle.success,
                    custom_id="rps_paper",
                )
            )
            view.add_item(
                discord.ui.Button(
                    label="Scissors",
                    style=discord.ButtonStyle.success,
                    custom_id="rps_scissors",
                )
            )

            embed = discord.Embed(
                title="Rock Paper Scissors!",
                description="Select a choice (rock/paper/scissors).",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed, view=view)

    @bot.tree.command(name="tti", description="Converts given text to image")
    @app_commands.describe(text="The text to convert into image")
    async def text_to_image(interaction: discord.Interaction, text: str):
        await interaction.response.defer()

        if not text.startswith(" "):
            text = " " + text
        if not text.endswith(" "):
            text += " "

        # Create image
        try:
            font = ImageFont.truetype(resource_path("Inter-SemiBold.ttf"), 48)
        except:
            font = ImageFont.load_default()

        # Calculate text size
        img = Image.new("RGB", (1, 1), color="black")
        draw = ImageDraw.Draw(img)
        bbox = draw.textbbox((0, 0), text, font=font)
        width = int(bbox[2] - bbox[0])
        height = int(bbox[3] - bbox[1])

        # Create final image
        img = Image.new("RGB", (width + 20, height + 30), color="black")
        draw = ImageDraw.Draw(img)
        draw.text((10, 5), text, font=font, fill="white")

        # Convert to bytes
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        file = discord.File(buffer, filename="text.png")

        embed = discord.Embed(
            title="Success!",
            description="Here is your image.",
            color=get_random_color(),
        )
        embed.set_image(url="attachment://text.png")

        await interaction.followup.send(embed=embed, file=file)

    @bot.tree.command(name="setting", description="Changes your user settings")
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
            app_commands.Choice(name="Enabled/True", value="true"),
            app_commands.Choice(name="Disabled/False", value="false"),
        ]
    )
    async def change_user_settings(
        interaction: discord.Interaction, type: str, value: str
    ):
        user_id = interaction.user.id

        if user_id not in Main.user_settings_map:
            Main.user_settings_map[user_id] = UserSettings()

        settings = Main.user_settings_map[user_id]

        if value == "true":
            if type == "bankdm":
                settings.bank_dm_enabled = True
                embed = discord.Embed(
                    title="Success!",
                    description="Enabled bank transaction DMs! Now you WILL be DMed about all your bank transactions.",
                    color=get_random_color(),
                )
            elif type == "passive":
                settings.bank_passive_enabled = True
                embed = discord.Embed(
                    title="Success!",
                    description="Enabled passive mode! Now NEITHER anyone can rob you, NOR you can rob anyone else.\n"
                    "You also CANNOT give money to someone else.",
                    color=get_random_color(),
                )
            else:
                embed = discord.Embed(
                    title="Error!",
                    description=f"Setting type {type} not found!",
                    color=get_random_color(),
                )
                await interaction.response.send_message(embed=embed)
                return

        elif value == "false":
            if type == "bankdm":
                settings.bank_dm_enabled = False
                embed = discord.Embed(
                    title="Success!",
                    description="Disabled bank transaction DMs! Now you WON'T be DMed about any of your bank transactions.",
                    color=get_random_color(),
                )
            elif type == "passive":
                settings.bank_passive_enabled = False
                embed = discord.Embed(
                    title="Success!",
                    description="Disabled passive mode! Now anyone CAN rob you, and you CAN rob anyone else.\n"
                    "You also CAN give money to someone else.",
                    color=get_random_color(),
                )
            else:
                embed = discord.Embed(
                    title="Error!",
                    description=f"Setting type {type} not found!",
                    color=get_random_color(),
                )
                await interaction.response.send_message(embed=embed)
                return
        else:
            embed = discord.Embed(
                title="Error!",
                description="Incorrect arguments given! Use 'true' or 'false' for the value.",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed)
            return

        Main.user_settings_map[user_id] = settings
        refresh_user_settings(Main.CONNSTR, Main.user_settings_map)

        await interaction.response.send_message(embed=embed)

    # Load currencies for autocomplete
    def load_currencies():
        """Load currency list from JSON file"""
        try:
            currencies_path = resource_path("currencies.json")
            with open(currencies_path, "r") as f:
                return json.load(f)["currencies"]
        except Exception as e:
            print(f"Failed to load currencies: {e}")
            return []

    @bot.tree.command(name="currconv", description="Converts one currency to another")
    @app_commands.describe(
        convert_amount="The amount of money to convert",
        from_currency="The currency of the given amount (e.g., USD, EUR)",
        to_currency="The currency to convert the amount to (e.g., USD, EUR)",
    )
    @app_commands.choices(from_currency=CURRENCY_CHOICES, to_currency=CURRENCY_CHOICES)
    async def currency_convert(
        interaction: discord.Interaction,
        convert_amount: float,
        from_currency: str,
        to_currency: str,
    ):
        await interaction.response.defer()

        # Validate currencies against the fixed list
        valid_codes = CURRENCY_CODES or [
            c.get("code") for c in load_currencies() if "code" in c
        ]
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
        exchange_api_key = os.getenv("EXAPI")
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
            response = requests.get(url, timeout=10)

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
        except Exception as e:
            print(f"Error in currency conversion: {e}")
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error!",
                    description="Conversion failed! Please try again.",
                    color=get_random_color(),
                )
            )

    @bot.tree.command(
        name="makecolor", description="Generates a color based on given RGB values"
    )
    @app_commands.describe(
        red="The red value (0-255)",
        green="The green value (0-255)",
        blue="The blue value (0-255)",
    )
    async def makecolor(
        interaction: discord.Interaction, red: int, green: int, blue: int
    ):
        await interaction.response.defer()

        if not (0 <= red <= 255 and 0 <= green <= 255 and 0 <= blue <= 255):
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error!",
                    description="RGB values must be between 0 and 255 (inclusive)!",
                    color=get_random_color(),
                )
            )
            return

        # Create color image
        color = (red, green, blue)
        img = Image.new("RGB", (500, 500), color=color)
        draw = ImageDraw.Draw(img)

        # Draw white rounded rectangle for text
        draw.rounded_rectangle([0, 0, 200, 55], radius=50, fill="white")

        # Draw text
        try:
            font = ImageFont.truetype(resource_path("Inter-SemiBold.ttf"), 18)
        except:
            font = ImageFont.load_default()

        draw.text((10, 10), f"RGB: {red}, {green}, {blue}", fill="black", font=font)
        hex_color = f"#{red:02X}{green:02X}{blue:02X}"
        draw.text((10, 30), f"HEX: {hex_color}", fill="black", font=font)

        # Convert to bytes
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        file = discord.File(buffer, filename="color.png")

        embed = discord.Embed(
            title="Success!",
            description=f"Here's your color for (R:{red}, G:{green}, B:{blue}):-",
            color=discord.Color.from_rgb(red, green, blue),
        )
        embed.set_image(url="attachment://color.png")

        await interaction.followup.send(embed=embed, file=file)

    @bot.tree.command(name="randomcolor", description="Generates a random color")
    async def randomcolor(interaction: discord.Interaction):
        await interaction.response.defer()

        # Generate random RGB values
        red = random.randint(0, 255)
        green = random.randint(0, 255)
        blue = random.randint(0, 255)

        # Create color image
        color = (red, green, blue)
        img = Image.new("RGB", (500, 500), color=color)
        draw = ImageDraw.Draw(img)

        # Draw white rounded rectangle for text
        draw.rounded_rectangle([0, 0, 200, 55], radius=50, fill="white")

        # Draw text
        try:
            font = ImageFont.truetype(resource_path("Inter-SemiBold.ttf"), 18)
        except:
            font = ImageFont.load_default()

        draw.text((10, 10), f"RGB: {red}, {green}, {blue}", fill="black", font=font)
        hex_color = f"#{red:02X}{green:02X}{blue:02X}"
        draw.text((10, 30), f"HEX: {hex_color}", fill="black", font=font)

        # Convert to bytes
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        file = discord.File(buffer, filename="color.png")

        embed = discord.Embed(
            title="Success!",
            description=f"Here's your random color (R:{red}, G:{green}, B:{blue}):-",
            color=discord.Color.from_rgb(red, green, blue),
        )
        embed.set_image(url="attachment://color.png")

        await interaction.followup.send(embed=embed, file=file)


async def help_category(category: str) -> discord.Embed:
    """Get help for a specific category"""
    try:
        with open(resource_path("commands.json"), "r") as f:
            commands_data = json.load(f)

        category_map = {
            "utility": ("Maxis Utility commands:-", commands_data["utility"]),
            "moderation": (
                "Maxis Moderation commands:-",
                commands_data["moderation"],
            ),
            "economy": ("Maxis Economy commands:-", commands_data["economy"]),
        }

        if category in category_map:
            title, commands = category_map[category]
            embed = discord.Embed(title=title, color=get_random_color())
            for cmd in commands:
                embed.add_field(name=cmd["name"], value=cmd["desc"], inline=True)
            return embed
    except Exception as e:
        print(f"Error loading help category: {e}")

    return discord.Embed(
        title="Error!", description="Invalid category!", color=get_random_color()
    )
