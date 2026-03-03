"""
Hacker Laptop item functionality
"""

from datetime import datetime, timezone
import discord
from bot.helper import get_random_color


async def use_laptop(interaction: discord.Interaction):
    """Use hacker laptop item"""
    user_id = interaction.user.id

    embed = discord.Embed(
        title=f"{interaction.user.display_name}'s PC",
        description="Press a button below to perform the desired action.",
        color=get_random_color(),
    )
    embed.add_field(name="OS", value="MaxisOS")
    embed.add_field(
        name="Time (UTC or GMT)",
        value=datetime.now(timezone.utc).strftime("%d %B %Y %I:%M:%S %p").upper(),
    )
    embed.add_field(name="MaxisVPN Status", value="Connected")
    embed.timestamp = datetime.now(timezone.utc)

    view = discord.ui.View()
    view.add_item(
        discord.ui.Button(
            label="Run Hacker Code",
            style=discord.ButtonStyle.danger,
            custom_id=f"laptop_code_{user_id}",
        )
    )
    view.add_item(
        discord.ui.Button(
            label="Shut Down",
            style=discord.ButtonStyle.danger,
            custom_id=f"laptop_off_{user_id}",
        )
    )

    await interaction.followup.send(embed=embed, view=view)