"""
Component interaction handlers
"""

from typing import cast

import discord
from discord.ext import commands

from bot.core.helper import help_category_embed, help_group, reply_error
from bot.objects.rps import RpsGame
from bot.objects.tictactoe import TicTacToe


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
        elif custom_id.startswith("ttt_"):
            await ComponentsListener._handle_ttt(interaction, custom_id)
        else:
            await reply_error(interaction, "Something went wrong. Please try again.")

    @staticmethod
    async def _handle_laptop(interaction: discord.Interaction, custom_id: str):
        """Handle laptop interactions"""
        parts = custom_id.split(":")
        if len(parts) < 2:
            return

        user_id = int(parts[1])

        if user_id != interaction.user.id:
            await reply_error(interaction, "You can't use someone else's PC!")
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
        modal.custom_id = f"laptop_cmd_input:{user_id}"
        await interaction.response.send_modal(modal)

    @staticmethod
    async def _handle_help_category(interaction: discord.Interaction):
        """Handle help category selection"""
        values = interaction.data.get("values") if interaction.data else None
        category = values[0].strip().lower() if values else None

        if category is None:
            await reply_error(
                interaction, "No category was provided! Please pick one of the options."
            )
            return

        # Interaction.client is typed as Client, but for an application command
        # it is always the Bot that owns the command tree.
        bot = cast(commands.Bot, interaction.client)
        group = help_group(bot, category)
        if group is None:
            await reply_error(interaction, "Invalid category!")
            return

        embed = help_category_embed(group)
        await interaction.response.edit_message(embed=embed)

    @staticmethod
    async def _handle_rps(interaction: discord.Interaction, custom_id: str):
        """Handle RPS button clicks"""
        game = RpsGame.from_button(custom_id)
        await interaction.response.edit_message(embed=game.embed(), view=None)

    @staticmethod
    async def _handle_ttt(interaction: discord.Interaction, custom_id: str):
        """Handle Tic Tac Toe button clicks"""
        if not interaction.message:
            await interaction.response.defer()
            return

        _, row, col, player_id = custom_id.split("_")
        player_id = int(player_id)
        if interaction.user.id != player_id:
            await reply_error(interaction, "You can't play someone else's game!")
            return

        components = cast(
            list[object], interaction.message.components if interaction.message else []
        )
        if not components:
            await interaction.response.defer()
            return

        # The buttons are the board, so the game reads straight back out of them
        game = TicTacToe.from_components(components)

        move = (int(row), int(col))
        if move not in game.legal_moves():
            await interaction.response.defer()
            return

        game.play(move)
        if not game.is_over():
            game.play_bot_turn()

        await interaction.response.edit_message(
            embed=game.embed(),
            view=game.view(player_id),
        )
