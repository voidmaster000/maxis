"""
Component interaction handlers
"""

import discord
import random
from bot.helper import (
    get_random_color,
    get_win_status,
    get_choice_name,
    get_random_integer,
)
from bot.objects.shop import Shop


class ComponentsListener:
    @staticmethod
    async def on_interaction(interaction: discord.Interaction):
        """Handle component interactions"""
        if not interaction.data or "custom_id" not in interaction.data:
            return

        custom_id = interaction.data["custom_id"]

        if custom_id.startswith("laptop"):
            await ComponentsListener._handle_laptop(interaction, custom_id)
        elif custom_id == "help_category":
            await ComponentsListener._handle_help_category(interaction)
        elif custom_id.startswith("rps_"):
            await ComponentsListener._handle_rps(interaction, custom_id)
        else:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error!",
                    description="Something went wrong. Please try again.",
                    color=get_random_color(),
                ),
                ephemeral=True,
            )

    @staticmethod
    async def _handle_laptop(interaction: discord.Interaction, custom_id: str):
        """Handle laptop interactions"""
        parts = custom_id.split("_")
        if len(parts) < 3:
            return

        user_id = int(parts[2])

        if user_id != interaction.user.id:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error!",
                    description="You can't use someone else's PC!",
                    color=get_random_color(),
                ),
                ephemeral=True,
            )
            return

        if "code" in custom_id:
            if (
                user_id not in Shop.owned_items
                or "Hacker Code" not in Shop.owned_items[user_id]
            ):
                await interaction.response.send_message(
                    embed=discord.Embed(
                        title="Error!",
                        description="You don't have the Hacker Code! Buy it from the shop.",
                        color=get_random_color(),
                    ),
                    ephemeral=True,
                )
                return

            # Generate pattern question
            question, answer = ComponentsListener._generate_pattern()

            modal = discord.ui.Modal(title="What's the next number in the pattern?")
            modal.add_item(
                discord.ui.TextInput(
                    label=question,
                    placeholder="Enter the answer",
                    custom_id="laptop_code_answer",
                    required=True,
                )
            )
            modal.custom_id = f"laptop_code_result_{answer}"
            await interaction.response.send_modal(modal)

        elif "off" in custom_id:
            embed = discord.Embed(
                title="You shut down the laptop.", color=get_random_color()
            )
            await interaction.response.edit_message(embed=embed, view=None)

    @staticmethod
    def _generate_pattern():
        """Generate a number pattern question"""
        pattern_multiplier = random.randint(1, 3)
        pattern_adder = random.randint(1, 8)
        current = 0
        pattern: list[int] = []

        for i in range(1, 10):
            current += (pattern_multiplier * i) + pattern_adder
            pattern.append(current)

        question = "n(i) = n(i - 1) + (i * m) + a, n(0) = 0, i = 1 to 9 given below, find n(10):\n" + ", ".join(map(str, pattern))
        answer = current + (pattern_multiplier * 10) + pattern_adder

        return question, answer

    @staticmethod
    async def _handle_help_category(interaction: discord.Interaction):
        """Handle help category selection"""
        from bot.commands.basic_commands import help_category

        values = interaction.data.get("values") if interaction.data else None
        if not values:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Error!",
                    description="No category was provided! Please pick one of the options.",
                    color=get_random_color(),
                ),
                ephemeral=True,
            )
            return

        category = values[0]
        embed = await help_category(category)
        await interaction.response.edit_message(embed=embed)

    @staticmethod
    async def _handle_rps(interaction: discord.Interaction, custom_id: str):
        """Handle RPS button clicks"""
        choice_map = {
            "rps_rock": "rock",
            "rps_paper": "paper",
            "rps_scissors": "scissors",
        }
        user_choice = choice_map.get(custom_id, "rock")[0].lower()
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
                description=f"You chose {choice_map.get(custom_id, 'rock')} and bot chose {get_choice_name(bot_choice)}.",
                color=get_random_color(),
            )

        await interaction.response.edit_message(embed=embed, view=None)
