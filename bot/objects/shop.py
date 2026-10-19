"""
Shop and ShopItem classes for the economy system
"""

import logging
from collections.abc import Callable, Coroutine

import discord
from discord import app_commands

from bot.core import database_sync, global_state
from bot.core.helper import get_random_color, reply_error
from bot.core.transactions import debit
from bot.objects.hacker_laptop import HackerLaptop
from bot.objects.nitro import use_nitro

logger = logging.getLogger(__name__)

type UseFunc = Callable[[discord.Interaction], Coroutine[None, None, None]]


class ShopItem:
    def __init__(
        self,
        name: str,
        desc: str,
        use_message: str,
        command: str,
        emoji: str,
        cost: int,
        is_persistent: bool,
        use_func: UseFunc | None = None,
    ):
        self.name = name
        self.desc = desc
        self.use_message = use_message
        self.command = command
        self.emoji = emoji
        self.cost = cost
        self.is_persistent = is_persistent
        self.use_func = use_func
        self.is_functional = use_func is not None

    async def use_item(self, interaction: discord.Interaction) -> None:
        """Use an item from inventory"""
        user_id = interaction.user.id
        owned = global_state.inventory.get(user_id, {})

        if owned.get(self.name, 0) <= 0:
            await reply_error(
                interaction, "You don't have this item! Buy it from the shop to use it."
            )
            return

        remaining = self._consume(user_id, owned)

        if self.is_persistent:
            description = self.use_message
        else:
            description = (
                f"{self.use_message}\n"
                f"You now have {remaining} {self.emoji} {self.name}(s)."
            )

        await interaction.response.send_message(
            embed=discord.Embed(
                title=f"{interaction.user.display_name} used {self.emoji} {self.name}",
                description=description,
                color=get_random_color(),
            )
        )

        if self.is_functional and self.use_func:
            await self.use_func(interaction)

    def _consume(self, user_id: int, owned: dict) -> int:
        """Take one of this item, unless it is persistent. Returns the count left."""
        if self.is_persistent:
            return owned[self.name]

        remaining = owned[self.name] - 1
        owned[self.name] = remaining
        database_sync.save_inventory()
        return remaining

    async def buy_item(self, interaction: discord.Interaction) -> None:
        """Buy an item from the shop"""
        try:
            user_id = interaction.user.id
            owned = global_state.inventory.setdefault(user_id, {})

            if owned.get(self.name, 0) > 0:
                await reply_error(
                    interaction,
                    f"You already own this item! Use it with "
                    f"```/economy use {self.command}```.",
                )
                return

            if not await debit(self.cost, interaction.user, interaction):
                return

            owned[self.name] = owned.get(self.name, 0) + 1
            database_sync.save_inventory()

            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Success!",
                    description=(
                        f"{interaction.user.display_name} purchased 1 {self.emoji} {self.name}.\n"
                        f"Now you have {owned[self.name]} {self.emoji} {self.name}(s)."
                    ),
                    color=get_random_color(),
                )
            )
        except Exception:
            logger.exception("Error buying item")


class Shop:
    """The catalogue of items, and the lookups the shop commands need."""

    items: list[ShopItem] = [
        ShopItem(
            "Juice",
            "Refresh yourself with a cool can of juice.",
            "You drink some juice, and get refreshed.",
            "juice",
            ":beverage_box:",
            1000,
            False,
        ),
        ShopItem(
            "Nitro",
            "Speed up your day, and work. Work and daily cooldown will be over.",
            "You use nitro and gain speed, resulting in your work and day being finished faster.",
            "nitro",
            ":rocket:",
            5400,
            False,
            use_nitro,
        ),
        ShopItem(
            "Hacker Code",
            "Very special bruteforce attack code. Tested upon top targets.",
            "Use it on your laptop.",
            "code",
            ":dvd:",
            90000,
            True,
        ),
        ShopItem(
            "Hacker Laptop",
            "Have a PC with you anytime, anywhere. Pen-testing utilities pre-installed.",
            "PC has booted.",
            "laptop",
            ":computer:",
            60000,
            True,
            HackerLaptop.open,
        ),
        ShopItem(
            "Pet Cat",
            "A pet cat, stays with you as a companion when you code.",
            "MEW!!! CODE!!!",
            "cat",
            ":cat:",
            60000,
            True,
        ),
        ShopItem(
            "Premium Pass",
            "Flex item, shows up on rich people's profiles.",
            "No use lol. Flex on others.",
            "pass",
            ":crown:",
            100000,
            True,
        ),
        ShopItem(
            "Magna Diamond",
            "Flex item for the very-rich.",
            "FLEX TIME!",
            "magna",
            ":large_blue_diamond:",
            500000,
            True,
        ),
    ]

    @classmethod
    def find(cls, command: str) -> ShopItem | None:
        """The item a /economy <command> argument names, or None."""
        wanted = command.strip().lower()
        return next(
            (item for item in cls.items if item.command.lower() == wanted), None
        )

    @classmethod
    def by_name(cls, name: str) -> ShopItem | None:
        """The item with this display name, or None."""
        return next((item for item in cls.items if item.name == name), None)

    @classmethod
    def choices(cls) -> list[app_commands.Choice[str]]:
        """The autocomplete choices for a command's `item` argument."""
        return [
            app_commands.Choice(name=item.name, value=item.command)
            for item in cls.items
        ]

    @classmethod
    def amount_owned(cls, user_id: int, item_name: str) -> int:
        """How many of one item a user is carrying."""
        return global_state.inventory.get(user_id, {}).get(item_name, 0)
