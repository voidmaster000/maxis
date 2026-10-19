from datetime import UTC, datetime

import discord
from discord import app_commands
from discord.ext import commands

from bot import database_sync, global_state
from bot.helper import (
    get_random_color,
    get_random_integer,
    get_random_work,
    reply_error,
)
from bot.objects.shop import Shop
from bot.transactions import credit, debit


def _split_duration(seconds: int) -> tuple[int, int, int, int]:
    """Break a duration in seconds into whole days, hours, minutes and seconds."""
    days, rest = divmod(seconds, 24 * 3600)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    return days, hours, minutes, secs


async def _reply_cooldown(interaction: discord.Interaction, duration: str) -> None:
    """Tell the user how long is left on a cooldown they just hit."""
    await interaction.response.send_message(
        embed=discord.Embed(
            title="Error!",
            description=(
                "You are currently on cooldown! You may use this command again after "
                f"{duration}"
            ),
            color=get_random_color(),
        )
    )


async def _reply_no_such_item(interaction: discord.Interaction, item: str) -> None:
    """The one message every shop command gives for an unknown item name."""
    await reply_error(
        interaction,
        f"No item named {item} was found! Use `/economy shop` to see the available items.",
    )


class Economy(commands.GroupCog):
    """Economy slash commands (the /economy category)."""

    @app_commands.command(
        name="balance",
        description="Shows your current bank balance or another user's balance",
    )
    @app_commands.describe(user="The user whose balance you want to check")
    async def balance(
        self, interaction: discord.Interaction, user: discord.User | None = None
    ):
        target_user = user or interaction.user

        if target_user.id not in global_state.balance_map:
            global_state.balance_map[target_user.id] = 0
            database_sync.save_balances()

        bal = global_state.balance_map[target_user.id]
        embed = discord.Embed(
            title=f"{target_user.display_name if interaction.guild else target_user.name}'s balance:-",
            color=get_random_color(),
        )
        embed.add_field(name="Bank", value=f":coin: {bal}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="daily", description="Get your daily 🪙 5000 earnings!")
    async def daily(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        last = global_state.user_daily_times.get(user_id)

        if last is not None:
            elapsed = (datetime.now(UTC) - last).total_seconds()
            if elapsed < global_state.DAILY_COOLDOWN:
                _, hours, minutes, seconds = _split_duration(
                    int(global_state.DAILY_COOLDOWN - elapsed)
                )
                await _reply_cooldown(
                    interaction,
                    f"{hours} hours, {minutes} minutes and {seconds} seconds.",
                )
                return

        global_state.user_daily_times[user_id] = datetime.now(UTC)
        earn = 5000
        if await credit(earn, interaction.user, interaction):
            embed = discord.Embed(
                title=f"{interaction.user.display_name}'s Daily Earnings",
                description=f"{interaction.user.display_name} got their daily earnings: :coin: {earn}",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed)
        database_sync.save_dailies()

    @app_commands.command(
        name="weekly", description="Get your weekly 🪙 10000 earnings!"
    )
    async def weekly(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        last = global_state.user_weekly_times.get(user_id)

        if last is not None:
            elapsed = (datetime.now(UTC) - last).total_seconds()
            if elapsed < global_state.WEEKLY_COOLDOWN:
                days, hours, minutes, seconds = _split_duration(
                    int(global_state.WEEKLY_COOLDOWN - elapsed)
                )
                await _reply_cooldown(
                    interaction,
                    f"{days} days, {hours} hours, {minutes} minutes and {seconds} seconds.",
                )
                return

        global_state.user_weekly_times[user_id] = datetime.now(UTC)
        earn = 10000
        if await credit(earn, interaction.user, interaction):
            embed = discord.Embed(
                title=f"{interaction.user.display_name}'s Weekly Earnings",
                description=f"{interaction.user.display_name} got their weekly earnings: :coin: {earn}",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed)
        database_sync.save_weeklies()

    @app_commands.command(
        name="monthly", description="Get your monthly 🪙 50000 earnings!"
    )
    async def monthly(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        last = global_state.user_monthly_times.get(user_id)

        if last is not None:
            elapsed = (datetime.now(UTC) - last).total_seconds()
            if elapsed < global_state.MONTHLY_COOLDOWN:
                days, hours, minutes, seconds = _split_duration(
                    int(global_state.MONTHLY_COOLDOWN - elapsed)
                )
                await _reply_cooldown(
                    interaction,
                    f"{days} days, {hours} hours, {minutes} minutes and {seconds} seconds.",
                )
                return

        global_state.user_monthly_times[user_id] = datetime.now(UTC)
        earn = 50000
        if await credit(earn, interaction.user, interaction):
            embed = discord.Embed(
                title=f"{interaction.user.display_name}'s Monthly Earnings",
                description=f"{interaction.user.display_name} got their monthly earnings: :coin: {earn}",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed)
        database_sync.save_monthlies()

    @app_commands.command(name="work", description="You work and gain money!")
    async def work(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        last = global_state.user_worked_times.get(user_id)

        if last is not None:
            elapsed = (datetime.now(UTC) - last).total_seconds()
            if elapsed < global_state.BASIC_COOLDOWN:
                left = int(global_state.BASIC_COOLDOWN - elapsed)
                await _reply_cooldown(interaction, f"{left} seconds.")
                return

        global_state.user_worked_times[user_id] = datetime.now(UTC)
        work_msg = get_random_work()
        earn = get_random_integer(100, 500)
        if await credit(earn, interaction.user, interaction):
            embed = discord.Embed(
                title=f"{interaction.user.display_name} Worked",
                description=f"{interaction.user.display_name} {work_msg} :coin: {earn}",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed)
        database_sync.save_works()

    @app_commands.command(
        name="rob", description="Rob others and get money, the dark way"
    )
    @app_commands.describe(user="The user to rob")
    async def rob(self, interaction: discord.Interaction, user: discord.User):
        if not interaction.guild:
            await reply_error(interaction, "This command only works in servers!")
            return

        commander_id = interaction.user.id

        if user.bot:
            await reply_error(interaction, "You can't rob bots!")
            return

        if commander_id == user.id:
            await reply_error(interaction, "You can't rob yourself!")
            return

        # Check cooldown
        if commander_id in global_state.user_robbed_times:
            time_diff = datetime.now(UTC) - global_state.user_robbed_times[commander_id]
            if time_diff.total_seconds() < global_state.BASIC_COOLDOWN:
                left = int(global_state.BASIC_COOLDOWN - time_diff.total_seconds())
                await reply_error(
                    interaction,
                    f"You are currently on cooldown! You may use this command again after {left} seconds.",
                )
                return

        # Check passive mode
        if commander_id in global_state.user_settings_map:
            if global_state.user_settings_map[commander_id].bank_passive_enabled:
                await reply_error(
                    interaction, "You are in passive mode! You can't rob anyone."
                )
                return

        if user.id in global_state.user_settings_map:
            if global_state.user_settings_map[user.id].bank_passive_enabled:
                await reply_error(
                    interaction, "That user is in passive mode! Try someone else."
                )
                return

        # Check balance
        if (
            user.id not in global_state.balance_map
            or global_state.balance_map[user.id] < 1000
        ):
            await reply_error(
                interaction, "That user does not have enough money to rob!"
            )
            return

        # Perform robbery
        global_state.user_robbed_times[commander_id] = datetime.now(UTC)
        database_sync.save_robs()

        rob_value = get_random_integer(1000, 5000)
        while global_state.balance_map[user.id] < rob_value:
            rob_value = get_random_integer(1000, 5000)

        if await debit(rob_value, user, interaction):
            if await credit(rob_value, interaction.user, interaction):
                embed = discord.Embed(
                    title="Success!",
                    description=f"{interaction.user.display_name} successfully robbed "
                    f"{user.display_name}, and earned :coin: {rob_value}.",
                    color=get_random_color(),
                )
                await interaction.response.send_message(embed=embed)
                database_sync.save_balances()

    @app_commands.command(
        name="give", description="Transfer money to others' accounts!"
    )
    @app_commands.describe(
        user="The user to give money to", amount="The amount of money to give"
    )
    async def give(
        self, interaction: discord.Interaction, user: discord.User, amount: int
    ):
        if not interaction.guild:
            await reply_error(interaction, "This command only works in servers!")
            return

        user_id = interaction.user.id

        if user.bot:
            await reply_error(interaction, "You can't give money to bots!")
            return

        if user_id == user.id:
            await reply_error(interaction, "You can't give money to yourself!")
            return

        if amount <= 0:
            await reply_error(interaction, "Amount must be greater than 0!")
            return

        # Check passive mode
        if user_id in global_state.user_settings_map:
            if global_state.user_settings_map[user_id].bank_passive_enabled:
                await reply_error(
                    interaction,
                    "You are in passive mode! You can't give money to anyone.",
                )
                return

        if user.id in global_state.user_settings_map:
            if global_state.user_settings_map[user.id].bank_passive_enabled:
                await reply_error(
                    interaction,
                    "That user is in passive mode. You can't give money to them.",
                )
                return

        # Check balance
        if user_id not in global_state.balance_map:
            global_state.balance_map[user_id] = 0

        if amount > global_state.balance_map[user_id]:
            await reply_error(
                interaction, "You can't give more money than you have in your account!"
            )
            return

        # Transfer money
        if await debit(amount, interaction.user, interaction):
            if await credit(amount, user, interaction):
                embed = discord.Embed(
                    title="Success!",
                    description=f"{interaction.user.display_name} successfully gave "
                    f"{user.display_name} :coin: {amount}.",
                    color=get_random_color(),
                )
                await interaction.response.send_message(embed=embed)
                database_sync.save_balances()

    @app_commands.command(
        name="leaderboard",
        description="Compare and check out the richest users of your server!",
    )
    async def leaderboard(self, interaction: discord.Interaction):
        if not interaction.guild:
            await reply_error(interaction, "This command only works in servers!")
            return

        users: list[tuple[discord.Member, int]] = []
        for member in interaction.guild.members:
            if not member.bot and member.id in global_state.balance_map:
                users.append((member, global_state.balance_map[member.id]))

        users.sort(key=lambda x: x[1], reverse=True)
        users = users[:5]  # Top 5

        if users:
            formatted = "\n".join(
                [
                    f"{i + 1}) {user[0].display_name} (:coin: {user[1]})"
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

    @app_commands.command(
        name="globalleaderboard",
        description="Compare and check out the richest users of our bot (Global)!",
    )
    async def global_leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()

        users: list[tuple[discord.User, int]] = []
        # snapshot the balances: fetch_user awaits, and any credit or debit
        # running at the same time could add a new account mid-loop
        for user_id, balance in list(global_state.balance_map.items()):
            try:
                user = await interaction.client.fetch_user(user_id)
            except (discord.NotFound, discord.HTTPException):
                # account gone, or Discord would not tell us who this is
                continue
            if not user.bot:
                users.append((user, balance))

        users.sort(key=lambda x: x[1], reverse=True)
        users = users[:5]  # Top 5

        if users:
            formatted = "\n".join(
                [
                    f"{i + 1}) {user[0]} (:coin: {user[1]})"
                    for i, user in enumerate(users)
                ]
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

    @app_commands.command(
        name="inventory", description="Displays a list of all items in your inventory"
    )
    async def inv(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        item_text: list[str] = []

        if user_id in global_state.inventory:
            user_items = global_state.inventory[user_id]
            index = 0
            for name, count in user_items.items():
                if count <= 0:
                    continue
                index += 1
                owned = Shop.by_name(name)
                emoji = owned.emoji if owned else ""
                item_text.append(f"{index}) {emoji} {name} (Count: {count})")

        if not item_text:
            item_text.append("There are no items in your inventory!")

        embed = discord.Embed(
            title="Items in your inventory:-",
            description="\n".join(item_text),
            color=get_random_color(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="shop",
        description="Shows a list of all items in the shop, and their details",
    )
    @app_commands.describe(item="The item to view details for (optional)")
    @app_commands.choices(item=Shop.choices())
    async def shop(self, interaction: discord.Interaction, item: str | None = None):
        user_id = interaction.user.id

        if item:
            shop_item = Shop.find(item)
            if shop_item is None:
                await _reply_no_such_item(interaction, item)
                return

            embed = discord.Embed(
                title=f"Maxis Shop - Information about {shop_item.emoji} {shop_item.name}",
                description=f"> Description: {shop_item.desc}\n"
                f"> Persistent?: {'Yes' if shop_item.is_persistent else 'No'}\n"
                f"> Cost: :coin: {shop_item.cost}\n"
                f"> Amount owned: {Shop.amount_owned(user_id, shop_item.name)}\n"
                f"> Command to get: `/economy buy {shop_item.command}`\n"
                f"> Command to use: `/economy use {shop_item.command}`",
                color=get_random_color(),
            )
            await interaction.response.send_message(embed=embed)
        else:
            embed = discord.Embed(title="Maxis Shop", color=get_random_color())
            for index, shop_item in enumerate(Shop.items, 1):
                embed.add_field(
                    name=f"{index}) {shop_item.emoji} {shop_item.name}",
                    value=f"> Description: {shop_item.desc}\n"
                    f"> Persistent?: {'Yes' if shop_item.is_persistent else 'No'}\n"
                    f"> Cost: :coin: {shop_item.cost}\n"
                    f"> Amount owned: {Shop.amount_owned(user_id, shop_item.name)}",
                    inline=False,
                )
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="buy", description="Buy an item from the shop")
    @app_commands.describe(item="The item to buy")
    @app_commands.choices(item=Shop.choices())
    async def buy(self, interaction: discord.Interaction, item: str):
        shop_item = Shop.find(item)
        if shop_item is None:
            await _reply_no_such_item(interaction, item)
            return

        await shop_item.buy_item(interaction)

    @app_commands.command(name="use", description="Use an item in your inventory")
    @app_commands.describe(item="The item to use")
    @app_commands.choices(item=Shop.choices())
    async def use(self, interaction: discord.Interaction, item: str):
        shop_item = Shop.find(item)
        if shop_item is None:
            await _reply_no_such_item(interaction, item)
            return

        await shop_item.use_item(interaction)
