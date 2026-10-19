"""Moderation slash commands for Maxis."""

import discord
from discord import app_commands
from discord.ext import commands

from bot.core import database_sync, global_state
from bot.core.helper import get_random_color, reply_error
from bot.objects.warn import Warn


async def require_moderator(interaction: discord.Interaction) -> discord.Guild | None:
    """Return the guild if this interaction may use mod commands, else None.

    Moderation commands only work in a server, and only for an admin. The
    caller gets the guild back so it does not have to re-narrow the Optional.
    """
    member = interaction.user
    if not isinstance(member, discord.Member) or not interaction.guild:
        await reply_error(interaction, "This command only works in servers!")
        return None

    if not member.guild_permissions.administrator:
        await reply_error(
            interaction,
            "You don't have admin perms, so you cannot use mod commands!",
        )
        return None

    return interaction.guild


class Moderation(commands.GroupCog):
    """Moderation slash commands (the /moderation category)."""

    @app_commands.command(name="kick", description="Kicks the mentioned user")
    @app_commands.describe(
        user="The user to kick", reason="The reason for kicking (optional)"
    )
    @app_commands.default_permissions(kick_members=True)
    async def kick(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        reason: str | None = None,
    ):
        guild = await require_moderator(interaction)
        if guild is None:
            return

        try:
            await guild.kick(user, reason=reason)
            embed = discord.Embed(
                title="Success!",
                description=f"Successfully kicked user {user}."
                + (f" Reason: {reason}" if reason else ""),
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await reply_error(
                interaction,
                "I can't kick that user! Reasons - No kick permission, lower role or lower position.",
            )

    @app_commands.command(name="ban", description="Bans the mentioned user")
    @app_commands.describe(
        user="The user to ban", reason="The reason for banning (optional)"
    )
    @app_commands.default_permissions(ban_members=True)
    async def ban(
        self,
        interaction: discord.Interaction,
        user: discord.User,
        reason: str | None = None,
    ):
        guild = await require_moderator(interaction)
        if guild is None:
            return

        try:
            await guild.ban(user, reason=reason)
            embed = discord.Embed(
                title="Success!",
                description=f"Successfully banned user {user}."
                + (f" Reason: {reason}" if reason else ""),
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await reply_error(
                interaction,
                "I can't ban that user! Reasons - No ban permission, lower role or lower position.",
            )

    @app_commands.command(name="unban", description="Unbans the mentioned user")
    @app_commands.describe(user="The user to unban")
    @app_commands.default_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user: discord.User):
        guild = await require_moderator(interaction)
        if guild is None:
            return

        try:
            await guild.unban(user)
            embed = discord.Embed(
                title="Success!",
                description=f"Successfully unbanned user {user}.",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await reply_error(
                interaction, "I can't unban that user! Reasons - No unban permission."
            )

    @app_commands.command(
        name="mute", description="Mutes the mentioned user (Mute = Disable chat and VC)"
    )
    @app_commands.describe(user="The user to mute")
    @app_commands.default_permissions(moderate_members=True)
    async def mute(self, interaction: discord.Interaction, user: discord.Member):
        guild = await require_moderator(interaction)
        if guild is None:
            return

        try:
            await user.edit(mute=True, deafen=True)
            embed = discord.Embed(
                title="Success!",
                description=f"Successfully muted user {user}.",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await reply_error(
                interaction,
                "I can't mute that user! Reasons - No mute permission, lower role or lower position.",
            )

    @app_commands.command(
        name="unmute",
        description="Unmutes the mentioned user (Mute = Enable chat and VC)",
    )
    @app_commands.describe(user="The user to unmute")
    @app_commands.default_permissions(moderate_members=True)
    async def unmute(self, interaction: discord.Interaction, user: discord.Member):
        guild = await require_moderator(interaction)
        if guild is None:
            return

        try:
            await user.edit(mute=False, deafen=False)
            embed = discord.Embed(
                title="Success!",
                description=f"Successfully unmuted user {user}.",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await reply_error(
                interaction, "I can't unmute that user! Reasons - No unmute permission."
            )

    @app_commands.command(name="warn", description="Warns a user")
    @app_commands.describe(user="The user to warn", cause="The reason for the warning")
    @app_commands.default_permissions(moderate_members=True)
    async def warn(
        self, interaction: discord.Interaction, user: discord.Member, cause: str
    ):
        guild = await require_moderator(interaction)
        if guild is None:
            return

        server_id = guild.id

        if server_id not in global_state.warn_map:
            global_state.warn_map[server_id] = {}

        if user.id not in global_state.warn_map[server_id]:
            warn = Warn(cause, user.id)
            global_state.warn_map[server_id][user.id] = warn
        else:
            global_state.warn_map[server_id][user.id].new_warn(cause)

        warn = global_state.warn_map[server_id][user.id]

        embed = discord.Embed(
            title="Success!",
            description=f"Successfully warned {user} for cause:\n{cause}\n"
            f"They now have {warn.warns} warn(s).",
            color=get_random_color(),
        )
        await interaction.response.send_message(embed=embed)

        # Try to DM user
        try:
            dm_embed = discord.Embed(
                title="Alert!",
                description=f"You have been warned in **{guild.name}** for reason: **{cause}**. "
                f"You now have **{warn.warns}** warn(s) in that server.",
                color=get_random_color(),
            )
            await user.send(embed=dm_embed)
        except discord.Forbidden:
            # their direct messages are closed, which is not our problem
            pass

        database_sync.save_warns()

    @app_commands.command(name="clearwarns", description="Clear all warns for a user")
    @app_commands.describe(user="The user to clear warns for")
    @app_commands.default_permissions(moderate_members=True)
    async def clear_warn(self, interaction: discord.Interaction, user: discord.Member):
        guild = await require_moderator(interaction)
        if guild is None:
            return

        server_id = guild.id

        if (
            server_id in global_state.warn_map
            and user.id in global_state.warn_map[server_id]
        ):
            del global_state.warn_map[server_id][user.id]
            embed = discord.Embed(
                title="Success!",
                description=f"Successfully removed all warnings for {user}!",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(
                title="Error!",
                description="No warns were found for this user!",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed)

        database_sync.save_warns()

    @app_commands.command(name="getwarns", description="Gets all warns for a user")
    @app_commands.describe(user="The user to get warns for")
    @app_commands.default_permissions(moderate_members=True)
    async def get_warns(self, interaction: discord.Interaction, user: discord.Member):
        guild = await require_moderator(interaction)
        if guild is None:
            return

        server_id = guild.id

        if (
            server_id in global_state.warn_map
            and user.id in global_state.warn_map[server_id]
        ):
            warn = global_state.warn_map[server_id][user.id]
            causes = (
                "\n".join(warn.warn_causes)
                if warn.warn_causes
                else "No warns were found for this user!"
            )
        else:
            causes = "No warns were found for this user!"

        embed = discord.Embed(
            title=f"Warns for {user}:-", description=causes, color=get_random_color()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="clear", description="Clears specified number of messages"
    )
    @app_commands.describe(amount="The number of messages to clear")
    @app_commands.default_permissions(manage_messages=True)
    async def clear_messages(self, interaction: discord.Interaction, amount: int):
        # a DM channel is not a TextChannel either, so this also covers DMs
        if type(interaction.channel) is not discord.TextChannel:
            await reply_error(interaction, "This command only works in servers!")
            return

        guild = await require_moderator(interaction)
        if guild is None:
            return

        if amount <= 0 or amount > 100:
            await reply_error(interaction, "Amount must be between 1 and 100!")
            return

        try:
            deleted = await interaction.channel.purge(limit=amount)
            embed = discord.Embed(
                title="Success!",
                description=f"{interaction.user.name} cleared {len(deleted)} message(s) in: {interaction.channel.mention}",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.Forbidden:
            await reply_error(
                interaction, "I don't have permission to manage messages!"
            )

    @app_commands.command(name="nuke", description="Cleans everything in a channel")
    @app_commands.default_permissions(manage_channels=True)
    async def nuke(self, interaction: discord.Interaction):
        guild = await require_moderator(interaction)
        if guild is None:
            return

        if not isinstance(interaction.channel, discord.TextChannel):
            await reply_error(interaction, "This command only works in text channels!")
            return

        channel = interaction.channel
        channel_name = channel.name
        channel_category = channel.category
        channel_topic = channel.topic
        channel_slowmode = channel.slowmode_delay
        channel_nsfw = channel.is_nsfw()
        channel_auto_archive_duration = channel.default_auto_archive_duration
        channel_default_thread_slowmode_delay = channel.default_thread_slowmode_delay
        channel_news = channel.is_news()
        channel_overwrites = channel.overwrites
        channel_position = channel.position

        try:
            # Delete channel
            await channel.delete()

            # Recreate channel
            new_channel = await channel.guild.create_text_channel(
                name=channel_name,
                category=channel_category,
                topic=channel_topic if channel_topic else "",
                slowmode_delay=channel_slowmode,
                nsfw=channel_nsfw,
                default_auto_archive_duration=channel_auto_archive_duration,
                default_thread_slowmode_delay=channel_default_thread_slowmode_delay,
                news=channel_news,
                overwrites=channel_overwrites,
                position=channel_position,
                reason=f"Nuked by {interaction.user.name}",
            )

            embed = discord.Embed(
                title="Success!",
                description=f"Successfully nuked this channel (Nuked By: {interaction.user.name}).",
                color=get_random_color(),
            )
            await new_channel.send(embed=embed)
        except discord.Forbidden:
            await reply_error(
                interaction, "I don't have permission to manage channels!"
            )
