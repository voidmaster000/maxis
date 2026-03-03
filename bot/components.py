"""
Component interaction handlers
"""

import discord
from bot.helper import (
    get_random_color,
    get_win_status,
    get_choice_name,
    get_random_integer,
)


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

        modal = discord.ui.Modal(title="Laptop Command Prompt")
        modal.add_item(
            discord.ui.TextInput(
                label="Enter command",
                placeholder="Try: help",
                custom_id="laptop_cmd_input",
                required=True,
                max_length=120,
            )
        )
        message_id = interaction.message.id if interaction.message else 0
        modal.custom_id = f"laptop_cmd_input:{user_id}:{message_id}"
        await interaction.response.send_modal(modal)

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
