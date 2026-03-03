"""
Currency/Economy slash commands
"""

from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from bot.helper import (
    get_random_color,
    BASIC_COOLDOWN,
    DAILY_COOLDOWN,
    WEEKLY_COOLDOWN,
    MONTHLY_COOLDOWN,
    get_random_work,
    get_random_integer,
    credit_balance,
    credit_balance_for_different_user,
    debit_balance,
    debit_balance_for_different_user,
    refresh_works,
    refresh_robs,
    refresh_dailies,
    refresh_weeklies,
    refresh_monthlies,
    refresh_balances,
)
from bot.objects.shop import Shop


def _get_main():
    """Lazy import Main to avoid circular imports during bot startup."""
    from bot.main import Main  # type: ignore

    return Main


def setup_currency_commands(bot: commands.Bot):
    """Setup currency/economy slash commands"""
    Main = _get_main()

    @bot.tree.command(
        name="balance",
        description="Shows your current bank balance or another user's balance",
    )
    @app_commands.describe(user="The user whose balance you want to check")
    async def balance(
        interaction: discord.Interaction, user: Optional[discord.User] = None
    ):
        target_user = user or interaction.user

        if target_user.id not in Main.balance_map:
            Main.balance_map[target_user.id] = 0
            refresh_balances(Main.CONNSTR)

        bal = Main.balance_map[target_user.id]
        embed = discord.Embed(
            title=f"{target_user.display_name if interaction.guild else target_user.name}'s balance:-",
            color=get_random_color(),
        )
        embed.add_field(name="Bank", value=f":coin: {bal}")
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="daily", description="Get your daily 🪙 5000 earnings!")
    async def daily(interaction: discord.Interaction):
        user_id = interaction.user.id

        if user_id in Main.user_daily_times:
            time_diff = datetime.now(timezone.utc) - Main.user_daily_times[user_id]
            if time_diff.total_seconds() >= DAILY_COOLDOWN:
                Main.user_daily_times[user_id] = datetime.now(timezone.utc)
                earn = 5000
                if await credit_balance(
                    earn,
                    interaction,
                    Main.CONNSTR,
                    Main.user_settings_map,
                    Main.balance_map,
                ):
                    embed = discord.Embed(
                        title=f"{interaction.user.display_name}'s Daily Earnings",
                        description=f"{interaction.user.display_name} got their daily earnings: :coin: {earn}",
                        color=get_random_color(),
                    )
                    await interaction.response.send_message(embed=embed)
                refresh_dailies(Main.CONNSTR, Main.user_daily_times)
            else:
                left_seconds = int(DAILY_COOLDOWN - time_diff.total_seconds())
                hours = left_seconds // 3600
                minutes = (left_seconds % 3600) // 60
                seconds = left_seconds % 60
                embed = discord.Embed(
                    title="Error!",
                    description=f"You are currently on cooldown! You may use this command again after "
                    f"{hours} hours, {minutes} minutes and {seconds} seconds.",
                    color=get_random_color(),
                )
                await interaction.response.send_message(embed=embed)
        else:
            Main.user_daily_times[user_id] = datetime.now(timezone.utc)
            earn = 5000
            if await credit_balance(
                earn,
                interaction,
                Main.CONNSTR,
                Main.user_settings_map,
                Main.balance_map,
            ):
                embed = discord.Embed(
                    title=f"{interaction.user.display_name}'s Daily Earnings",
                    description=f"{interaction.user.display_name} got their daily earnings: :coin: {earn}",
                    color=get_random_color(),
                )
                await interaction.response.send_message(embed=embed)
            refresh_dailies(Main.CONNSTR, Main.user_daily_times)

    @bot.tree.command(name="weekly", description="Get your weekly 🪙 10000 earnings!")
    async def weekly(interaction: discord.Interaction):
        user_id = interaction.user.id

        if user_id in Main.user_weekly_times:
            time_diff = datetime.now(timezone.utc) - Main.user_weekly_times[user_id]
            if time_diff.total_seconds() >= WEEKLY_COOLDOWN:
                Main.user_weekly_times[user_id] = datetime.now(timezone.utc)
                earn = 10000
                if await credit_balance(
                    earn,
                    interaction,
                    Main.CONNSTR,
                    Main.user_settings_map,
                    Main.balance_map,
                ):
                    embed = discord.Embed(
                        title=f"{interaction.user.display_name}'s Weekly Earnings",
                        description=f"{interaction.user.display_name} got their weekly earnings: :coin: {earn}",
                        color=get_random_color(),
                    )
                    await interaction.response.send_message(embed=embed)
                refresh_weeklies(Main.CONNSTR, Main.user_weekly_times)
            else:
                left_seconds = int(WEEKLY_COOLDOWN - time_diff.total_seconds())
                days = left_seconds // (24 * 3600)
                left_seconds = left_seconds % (24 * 3600)
                hours = left_seconds // 3600
                minutes = (left_seconds % 3600) // 60
                seconds = left_seconds % 60
                embed = discord.Embed(
                    title="Error!",
                    description=f"You are currently on cooldown! You may use this command again after "
                    f"{days} days, {hours} hours, {minutes} minutes and {seconds} seconds.",
                    color=get_random_color(),
                )
                await interaction.response.send_message(embed=embed)
        else:
            Main.user_weekly_times[user_id] = datetime.now(timezone.utc)
            earn = 10000
            if await credit_balance(
                earn,
                interaction,
                Main.CONNSTR,
                Main.user_settings_map,
                Main.balance_map,
            ):
                embed = discord.Embed(
                    title=f"{interaction.user.display_name}'s Weekly Earnings",
                    description=f"{interaction.user.display_name} got their weekly earnings: :coin: {earn}",
                    color=get_random_color(),
                )
                await interaction.response.send_message(embed=embed)
            refresh_weeklies(Main.CONNSTR, Main.user_weekly_times)

    @bot.tree.command(name="monthly", description="Get your monthly 🪙 50000 earnings!")
    async def monthly(interaction: discord.Interaction):
        user_id = interaction.user.id

        if user_id in Main.user_monthly_times:
            time_diff = datetime.now(timezone.utc) - Main.user_monthly_times[user_id]
            if time_diff.total_seconds() >= MONTHLY_COOLDOWN:
                Main.user_monthly_times[user_id] = datetime.now(timezone.utc)
                earn = 50000
                if await credit_balance(
                    earn,
                    interaction,
                    Main.CONNSTR,
                    Main.user_settings_map,
                    Main.balance_map,
                ):
                    embed = discord.Embed(
                        title=f"{interaction.user.display_name}'s Monthly Earnings",
                        description=f"{interaction.user.display_name} got their monthly earnings: :coin: {earn}",
                        color=get_random_color(),
                    )
                    await interaction.response.send_message(embed=embed)
                refresh_monthlies(Main.CONNSTR, Main.user_monthly_times)
            else:
                left_seconds = int(MONTHLY_COOLDOWN - time_diff.total_seconds())
                days = left_seconds // (24 * 3600)
                left_seconds = left_seconds % (24 * 3600)
                hours = left_seconds // 3600
                minutes = (left_seconds % 3600) // 60
                seconds = left_seconds % 60
                embed = discord.Embed(
                    title="Error!",
                    description=f"You are currently on cooldown! You may use this command again after "
                    f"{days} days, {hours} hours, {minutes} minutes and {seconds} seconds.",
                    color=get_random_color(),
                )
                await interaction.response.send_message(embed=embed)
        else:
            Main.user_monthly_times[user_id] = datetime.now(timezone.utc)
            earn = 50000
            if await credit_balance(
                earn,
                interaction,
                Main.CONNSTR,
                Main.user_settings_map,
                Main.balance_map,
            ):
                embed = discord.Embed(
                    title=f"{interaction.user.display_name}'s Monthly Earnings",
                    description=f"{interaction.user.display_name} got their monthly earnings: :coin: {earn}",
                    color=get_random_color(),
                )
                await interaction.response.send_message(embed=embed)
            refresh_monthlies(Main.CONNSTR, Main.user_monthly_times)

    @bot.tree.command(name="work", description="You work and gain money!")
    async def work(interaction: discord.Interaction):
        user_id = interaction.user.id

        if user_id in Main.user_worked_times:
            time_diff = datetime.now(timezone.utc) - Main.user_worked_times[user_id]
            if time_diff.total_seconds() >= BASIC_COOLDOWN:
                Main.user_worked_times[user_id] = datetime.now(timezone.utc)
                work_msg = get_random_work()
                earn = get_random_integer(500, 100)
                if await credit_balance(
                    earn,
                    interaction,
                    Main.CONNSTR,
                    Main.user_settings_map,
                    Main.balance_map,
                ):
                    embed = discord.Embed(
                        title=f"{interaction.user.display_name} Worked",
                        description=f"{interaction.user.display_name} {work_msg} :coin: {earn}",
                        color=get_random_color(),
                    )
                    await interaction.response.send_message(embed=embed)
                refresh_works(Main.CONNSTR, Main.user_worked_times)
            else:
                left = int(BASIC_COOLDOWN - time_diff.total_seconds())
                embed = discord.Embed(
                    title="Error!",
                    description=f"You are currently on cooldown! You may use this command again after {left} seconds.",
                    color=get_random_color(),
                )
                await interaction.response.send_message(embed=embed)
        else:
            Main.user_worked_times[user_id] = datetime.now(timezone.utc)
            work_msg = get_random_work()
            earn = get_random_integer(500, 100)
            if await credit_balance(
                earn,
                interaction,
                Main.CONNSTR,
                Main.user_settings_map,
                Main.balance_map,
            ):
                embed = discord.Embed(
                    title=f"{interaction.user.display_name} Worked",
                    description=f"{interaction.user.display_name} {work_msg} :coin: {earn}",
                    color=get_random_color(),
                )
                await interaction.response.send_message(embed=embed)
            refresh_works(Main.CONNSTR, Main.user_worked_times)

    @bot.tree.command(name="rob", description="Rob others and get money, the dark way")
    @app_commands.describe(user="The user to rob")
    async def rob(interaction: discord.Interaction, user: discord.User):
        if not interaction.guild:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error!",
                    description="This command only works in servers!",
                    color=get_random_color(),
                ),
                ephemeral=True,
            )
            return

        commander_id = interaction.user.id

        if user.bot:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error!",
                    description="You can't rob bots!",
                    color=get_random_color(),
                ),
                ephemeral=True,
            )
            return

        if commander_id == user.id:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error!",
                    description="You can't rob yourself!",
                    color=get_random_color(),
                ),
                ephemeral=True,
            )
            return

        # Check cooldown
        if commander_id in Main.user_robbed_times:
            time_diff = (
                datetime.now(timezone.utc) - Main.user_robbed_times[commander_id]
            )
            if time_diff.total_seconds() < BASIC_COOLDOWN:
                left = int(BASIC_COOLDOWN - time_diff.total_seconds())
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="Error!",
                        description=f"You are currently on cooldown! You may use this command again after {left} seconds.",
                        color=get_random_color(),
                    ),
                    ephemeral=True,
                )
                return

        # Check passive mode
        if commander_id in Main.user_settings_map:
            if Main.user_settings_map[commander_id].bank_passive_enabled:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="Error!",
                        description="You are in passive mode! You can't rob anyone.",
                        color=get_random_color(),
                    ),
                    ephemeral=True,
                )
                return

        if user.id in Main.user_settings_map:
            if Main.user_settings_map[user.id].bank_passive_enabled:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="Error!",
                        description="That user is in passive mode! Try someone else.",
                        color=get_random_color(),
                    ),
                    ephemeral=True,
                )
                return

        # Check balance
        if user.id not in Main.balance_map or Main.balance_map[user.id] < 1000:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error!",
                    description="That user does not have enough money to rob!",
                    color=get_random_color(),
                ),
                ephemeral=True,
            )
            return

        # Perform robbery
        Main.user_robbed_times[commander_id] = datetime.now(timezone.utc)
        refresh_robs(Main.CONNSTR, Main.user_robbed_times)

        rob_value = get_random_integer(5000, 1000)
        while Main.balance_map[user.id] < rob_value:
            rob_value = get_random_integer(5000, 1000)

        if await debit_balance_for_different_user(
            rob_value,
            user,
            interaction,
            Main.CONNSTR,
            Main.user_settings_map,
            Main.balance_map,
        ):
            if await credit_balance(
                rob_value,
                interaction,
                Main.CONNSTR,
                Main.user_settings_map,
                Main.balance_map,
            ):
                embed = discord.Embed(
                    title="Success!",
                    description=f"{interaction.user.display_name} successfully robbed "
                    f"{user.display_name}, and earned :coin: {rob_value}.",
                    color=get_random_color(),
                )
                await interaction.response.send_message(embed=embed)
                refresh_balances(Main.CONNSTR)

    @bot.tree.command(name="give", description="Transfer money to others' accounts!")
    @app_commands.describe(
        user="The user to give money to", amount="The amount of money to give"
    )
    async def give(interaction: discord.Interaction, user: discord.User, amount: int):
        if not interaction.guild:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error!",
                    description="This command only works in servers!",
                    color=get_random_color(),
                ),
                ephemeral=True,
            )
            return

        user_id = interaction.user.id

        if user.bot:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error!",
                    description="You can't give money to bots!",
                    color=get_random_color(),
                ),
                ephemeral=True,
            )
            return

        if user_id == user.id:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error!",
                    description="You can't give money to yourself!",
                    color=get_random_color(),
                ),
                ephemeral=True,
            )
            return

        if amount <= 0:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error!",
                    description="Amount must be greater than 0!",
                    color=get_random_color(),
                ),
                ephemeral=True,
            )
            return

        # Check passive mode
        if user_id in Main.user_settings_map:
            if Main.user_settings_map[user_id].bank_passive_enabled:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="Error!",
                        description="You are in passive mode! You can't give money to anyone.",
                        color=get_random_color(),
                    ),
                    ephemeral=True,
                )
                return

        if user.id in Main.user_settings_map:
            if Main.user_settings_map[user.id].bank_passive_enabled:
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="Error!",
                        description="That user is in passive mode. You can't give money to them.",
                        color=get_random_color(),
                    ),
                    ephemeral=True,
                )
                return

        # Check balance
        if user_id not in Main.balance_map:
            Main.balance_map[user_id] = 0

        if amount > Main.balance_map[user_id]:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error!",
                    description="You can't give more money than you have in your account!",
                    color=get_random_color(),
                ),
                ephemeral=True,
            )
            return

        # Transfer money
        if await debit_balance(
            amount, interaction, Main.CONNSTR, Main.user_settings_map, Main.balance_map
        ):
            if await credit_balance_for_different_user(
                amount,
                user,
                interaction,
                Main.CONNSTR,
                Main.user_settings_map,
                Main.balance_map,
            ):
                embed = discord.Embed(
                    title="Success!",
                    description=f"{interaction.user.display_name} successfully gave "
                    f"{user.display_name} :coin: {amount}.",
                    color=get_random_color(),
                )
                await interaction.response.send_message(embed=embed)
                refresh_balances(Main.CONNSTR)

    @bot.tree.command(
        name="leaderboard",
        description="Compare and check out the richest users of your server!",
    )
    async def leaderboard(interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error!",
                    description="This command only works in servers!",
                    color=get_random_color(),
                ),
                ephemeral=True,
            )
            return

        users: list[tuple[discord.Member, int]] = []
        for member in interaction.guild.members:
            if not member.bot and member.id in Main.balance_map:
                users.append((member, Main.balance_map[member.id]))

        users.sort(key=lambda x: x[1], reverse=True)
        users = users[:5]  # Top 5

        if users:
            formatted = "\n".join(
                [
                    f"{i+1}) {user[0].display_name} (:coin: {user[1]})"
                    for i, user in enumerate(users)
                ]
            )
            embed = discord.Embed(
                title=f"Top {len(users)} richest user(s) in {interaction.guild.name}:-",
                description=formatted,
                color=get_random_color(),
            )
        else:
            embed = discord.Embed(
                title="No one has more than :coin: 0 in this server!",
                color=get_random_color(),
            )

        await interaction.response.send_message(embed=embed)

    @bot.tree.command(
        name="globalleaderboard",
        description="Compare and check out the richest users of our bot (Global)!",
    )
    async def global_leaderboard(interaction: discord.Interaction):
        await interaction.response.defer()

        users: list[tuple[discord.User, int]] = []
        for user_id, balance in Main.balance_map.items():
            try:
                user = await bot.fetch_user(user_id)
                if not user.bot:
                    users.append((user, balance))
            except:
                continue

        users.sort(key=lambda x: x[1], reverse=True)
        users = users[:5]  # Top 5

        if users:
            formatted = "\n".join(
                [f"{i+1}) {user[0]} (:coin: {user[1]})" for i, user in enumerate(users)]
            )
            embed = discord.Embed(
                title=f"Top {len(users)} richest user(s) of Maxis:-",
                description=formatted,
                color=get_random_color(),
            )
        else:
            embed = discord.Embed(
                title="No one has more than :coin: 0 in our database!",
                color=get_random_color(),
            )

        await interaction.followup.send(embed=embed)

    @bot.tree.command(
        name="inventory", description="Displays a list of all items in your inventory"
    )
    async def inv(interaction: discord.Interaction):
        user_id = interaction.user.id
        item_text: list[str] = []

        if user_id in Shop.owned_items:
            user_items = Shop.owned_items[user_id]
            index = 0
            for name, count in user_items.items():
                if count > 0:
                    index += 1
                    item_text.append(f"{index}) {[shop_item for shop_item in Shop.items if shop_item.name == name][0].emoji} {name} (Count: {count})")

        if not item_text:
            item_text.append("There are no items in your inventory!")

        embed = discord.Embed(
            title="Items in your inventory:-",
            description="\n".join(item_text),
            color=get_random_color(),
        )
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(
        name="shop",
        description="Shows a list of all items in the shop, and their details",
    )
    @app_commands.describe(item="The item to view details for (optional)")
    @app_commands.choices(
        item=[
            app_commands.Choice(name=shop_item.name, value=shop_item.command)
            for shop_item in Shop.items
        ]
    )
    async def shop(interaction: discord.Interaction, item: Optional[str] = None):
        user_id = interaction.user.id

        if item:
            item_lower = item.lower()
            for shop_item in Shop.items:
                if item_lower == shop_item.command.lower():
                    embed = discord.Embed(
                        title=f"Maxis Shop - Information about {shop_item.emoji} {shop_item.name}",
                        description=f"> Description: {shop_item.desc}\n"
                        f"> Persistent?: {'Yes' if shop_item.is_persistent else 'No'}\n"
                        f"> Cost: :coin: {shop_item.cost}\n"
                        f"> Amount owned: {Shop.get_amount_owned(user_id, shop_item.name)}\n"
                        f"> Command to get: ```/buy {shop_item.command}```\n"
                        f"> Command to use: ```/use {shop_item.command}```",
                        color=get_random_color(),
                    )
                    await interaction.response.send_message(embed=embed)
                    return

            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error!",
                    description=f"No item named {item} was found! Use /shop to see the available items.",
                    color=get_random_color(),
                ),
                ephemeral=True,
            )
        else:
            embed = discord.Embed(title="Maxis Shop", color=get_random_color())
            for index, shop_item in enumerate(Shop.items, 1):
                embed.add_field(
                    name=f"{index}) {shop_item.emoji} {shop_item.name}",
                    value=f"> Description: {shop_item.desc}\n"
                    f"> Persistent?: {'Yes' if shop_item.is_persistent else 'No'}\n"
                    f"> Cost: :coin: {shop_item.cost}\n"
                    f"> Amount owned: {Shop.get_amount_owned(user_id, shop_item.name)}\n"
                    f"> Command to get: ```/buy {shop_item.command}```\n"
                    f"> Command to use: ```/use {shop_item.command}```",
                    inline=False,
                )
            await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="buy", description="Buy an item from the shop")
    @app_commands.describe(item="The item to buy")
    @app_commands.choices(
        item=[
            app_commands.Choice(name=shop_item.name, value=shop_item.command)
            for shop_item in Shop.items
        ]
    )
    async def buy(interaction: discord.Interaction, item: str):
        item_lower = item.lower()
        for shop_item in Shop.items:
            if item_lower == shop_item.command.lower():
                await shop_item.buy_item(
                    interaction,
                    Main.balance_map,
                    Main.user_settings_map,
                    Main.CONNSTR,
                )
                return

        await interaction.response.send_message(
            embed=discord.Embed(
                title="Error!",
                description=f"No item named {item} was found! Use /shop to see the available items.",
                color=get_random_color(),
            ),
            ephemeral=True,
        )

    @bot.tree.command(name="use", description="Use an item in your inventory")
    @app_commands.describe(item="The item to use")
    @app_commands.choices(
        item=[
            app_commands.Choice(name=shop_item.name, value=shop_item.command)
            for shop_item in Shop.items
        ]
    )
    async def use(interaction: discord.Interaction, item: str):
        item_lower = item.lower()
        for shop_item in Shop.items:
            if item_lower == shop_item.command.lower():
                await shop_item.use_item(
                    interaction,
                    Main.CONNSTR,
                )
                return

        await interaction.response.send_message(
            embed=discord.Embed(
                title="Error!",
                description=f"No item named {item} was found! Use /shop to see the available items.",
                color=get_random_color(),
            ),
            ephemeral=True,
        )
