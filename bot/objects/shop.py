"""
Shop and ShopItem classes for the economy system
"""

import asyncio
from typing import Coroutine, Dict, Optional, Callable, TypeAlias, TypedDict

import discord

from bot.helper import get_random_color, debit_balance
from bot.objects.user_settings import UserSettings

UseFunc: TypeAlias = Callable[[discord.Interaction], Coroutine[None, None, None]]


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
        use_func: Optional[UseFunc] = None,
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

    async def use_item(
        self,
        interaction: discord.Interaction,
        connstr: str,
    ):
        """Use an item from inventory"""
        user_id = interaction.user.id
        if user_id in Shop.owned_items and self.name in Shop.owned_items[user_id]:
            if Shop.owned_items[user_id][self.name] > 0:
                owned = Shop.owned_items[user_id][self.name]
                if not self.is_persistent:
                    Shop.owned_items[user_id][self.name] = owned - 1
                    embed = discord.Embed(
                        title=f"{interaction.user.display_name} used {self.emoji} {self.name}",
                        description=f"{self.use_message}\nYou now have {owned - 1} {self.emoji} {self.name}(s).",
                        color=get_random_color(),
                    )
                    await interaction.response.send_message(embed=embed)
                    Shop.refresh_ownerships(connstr)
                else:
                    embed = discord.Embed(
                        title=f"{interaction.user.display_name} used {self.emoji} {self.name}",
                        description=self.use_message,
                        color=get_random_color(),
                    )
                    await interaction.response.send_message(embed=embed)

                if self.is_functional and self.use_func:
                    asyncio.create_task(self.use_func(interaction))

                return

        embed = discord.Embed(
            title="Error!",
            description="You don't have this item! Buy it from the shop to use it.",
            color=get_random_color(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def buy_item(
        self,
        interaction: discord.Interaction,
        balance_map: Dict[int, int],
        user_settings_map: Dict[int, UserSettings],
        connstr: str,
    ):
        """Buy an item from the shop"""
        try:
            user_id = interaction.user.id
            if user_id not in Shop.owned_items:
                Shop.owned_items[user_id] = {}
            elif self.name in Shop.owned_items[user_id]:
                if Shop.owned_items[user_id][self.name] > 0:
                    embed = discord.Embed(
                        title="Error!",
                        description=f"You already own this item! Use it with ```/use {self.command}```.",
                        color=get_random_color(),
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

            if await debit_balance(
                self.cost, interaction, connstr, user_settings_map, balance_map
            ):
                if self.name in Shop.owned_items[user_id]:
                    Shop.owned_items[user_id][self.name] += 1
                else:
                    Shop.owned_items[user_id][self.name] = 1

                embed = discord.Embed(
                    title="Success!",
                    description=f"{interaction.user.display_name} purchased 1 {self.emoji} {self.name}.\n"
                    f"Now you have {Shop.owned_items[user_id][self.name]} {self.emoji} {self.name}(s).",
                    color=get_random_color(),
                )
                await interaction.response.send_message(embed=embed)
                Shop.refresh_ownerships(connstr)
        except Exception as ex:
            print(f"Error buying item: {ex}")


class Shop:
    items: list[ShopItem] = []
    owned_items: Dict[int, Dict[str, int]] = {}

    @staticmethod
    def init_shop():
        """Initialize shop items"""
        from bot.objects.nitro import use_nitro
        from bot.objects.hacker_laptop import use_laptop

        juice = ShopItem(
            "Juice",
            "Refresh yourself with a cool can of juice.",
            "You drink some juice, and get refreshed.",
            "juice",
            ":beverage_box:",
            1000,
            False,
        )
        nitro = ShopItem(
            "Nitro",
            "Speed up your day, and work. Work and daily cooldown will be over.",
            "You use nitro and gain speed, resulting in your work and day being finished faster.",
            "nitro",
            ":rocket:",
            5400,
            False,
            use_nitro,
        )
        code = ShopItem(
            "Hacker Code",
            "Very special bruteforce attack code. Tested upon top targets.",
            "Use it on your laptop.",
            "code",
            ":dvd:",
            90000,
            True,
        )
        laptop = ShopItem(
            "Hacker Laptop",
            "Have a PC with you anytime, anywhere. Pen-testing utilities pre-installed.",
            "PC has booted.",
            "laptop",
            ":computer:",
            60000,
            True,
            use_laptop,
        )
        cat = ShopItem(
            "Pet Cat",
            "A pet cat, stays with you as a companion when you code.",
            "MEW!!! CODE!!!",
            "cat",
            ":cat:",
            60000,
            True,
        )
        pass_item = ShopItem(
            "Premium Pass",
            "Flex item, shows up on rich people's profiles.",
            "No use lol. Flex on others.",
            "pass",
            ":crown:",
            100000,
            True,
        )
        diamond = ShopItem(
            "Magna Diamond",
            "Flex item for the very-rich.",
            "FLEX TIME!",
            "magna",
            ":large_blue_diamond:",
            500000,
            True,
        )

        Shop.items = [juice, nitro, code, laptop, cat, pass_item, diamond]

    @staticmethod
    def get_amount_owned(user_id: int, item_name: str) -> int:
        """Get amount of item owned by user"""
        if user_id in Shop.owned_items and item_name in Shop.owned_items[user_id]:
            return Shop.owned_items[user_id][item_name]
        return 0

    @staticmethod
    def refresh_ownerships(connstr: str):
        """Refresh item ownerships in database"""

        def refresh():
            try:
                from pymongo import MongoClient

                class ItemDoc(TypedDict):
                    name: str
                    key: list[int]
                    val: list[ItemDocValue]

                class ItemDocValue(TypedDict):
                    key: list[str]
                    val: list[int]

                client = MongoClient[ItemDoc](connstr)
                db = client["UnknownDatabase"]
                collection = db["UnknownCollection"]

                values: list[ItemDocValue] = []
                for map_val in Shop.owned_items.values():
                    values.append(
                        {"key": list(map_val.keys()), "val": list(map_val.values())}
                    )

                doc: ItemDoc = {
                    "name": "item",
                    "key": list(Shop.owned_items.keys()),
                    "val": values,
                }

                if collection.count_documents({"name": "item"}) > 0:
                    collection.replace_one({"name": "item"}, doc)
                else:
                    collection.insert_one(doc)
                client.close()
            except Exception as e:
                print(f"Error refreshing ownerships: {e}")

        import threading

        threading.Thread(target=refresh, daemon=True).start()
