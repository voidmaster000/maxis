"""
Nitro item functionality
"""

from datetime import datetime, timedelta, timezone
import discord


async def use_nitro(interaction: discord.Interaction):
    """Use nitro item to reduce cooldowns"""
    from bot.main import Main
    from bot.helper import refresh_works, refresh_dailies

    user_id = interaction.user.id

    # Reduce work cooldown
    if user_id in Main.user_worked_times:
        work_reduce = timedelta(seconds=30) - (
            datetime.now(timezone.utc) - Main.user_worked_times[user_id]
        )
        if work_reduce.total_seconds() > 0:
            Main.user_worked_times[user_id] = (
                Main.user_worked_times[user_id] - work_reduce
            )
            refresh_works(Main.CONNSTR, Main.user_worked_times)

    # Reduce daily cooldown
    if user_id in Main.user_daily_times:
        daily_reduce = timedelta(seconds=86400) - (
            datetime.now(timezone.utc) - Main.user_daily_times[user_id]
        )
        if daily_reduce.total_seconds() > 0:
            Main.user_daily_times[user_id] = (
                Main.user_daily_times[user_id] - daily_reduce
            )
            refresh_dailies(Main.CONNSTR, Main.user_daily_times)
