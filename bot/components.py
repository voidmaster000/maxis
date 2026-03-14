"""
Component interaction handlers
"""

import discord
from typing import Any, cast
from bot.helper import (
    get_random_color,
    get_win_status,
    get_choice_name,
    get_random_integer,
    ttt_check_terminal_state,
    ttt_get_possible_moves_in_turn,
    ttt_get_state_after_move,
    ttt_get_terminal_state_value,
    ttt_minimax
)


class ComponentsListener:
    _ttt_component_type_logged = False

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

    @staticmethod
    async def _handle_ttt(interaction: discord.Interaction, custom_id: str):
        """Handle Tic Tac Toe button clicks"""

        player_move_row = int(custom_id.split("_")[1])
        player_move_col = int(custom_id.split("_")[2])
        buttons_grid = cast(list[object], interaction.message.components if interaction.message else [])
        if not buttons_grid:
            await interaction.response.defer()
            return

        if not ComponentsListener._ttt_component_type_logged:
            for row in buttons_grid:
                typed_row = cast(Any, row)
                raw_children = typed_row.children if hasattr(typed_row, "children") else None
                typed_children: list[object] = cast(list[object], raw_children) if isinstance(raw_children, list) else []
                print(f"[TTT DEBUG] row={type(typed_row).__module__}.{type(typed_row).__name__} children={len(typed_children)}")
                for button in typed_children:
                    typed_button = cast(Any, button)
                    print(f"[TTT DEBUG] button={type(typed_button).__module__}.{type(typed_button).__name__}")
                break
            ComponentsListener._ttt_component_type_logged = True
        
        # Extract the current board state from the button custom ids
        board = [["" for _ in range(3)] for _ in range(3)]
        for row in buttons_grid:
            typed_row = cast(Any, row)
            row_children = typed_row.children if hasattr(typed_row, "children") else None
            if not isinstance(row_children, list):
                continue
            for button in cast(list[object], row_children):
                typed_button = cast(Any, button)
                if not hasattr(typed_button, "custom_id"):
                    continue
                button_custom_id = typed_button.custom_id
                if not isinstance(button_custom_id, str) or not button_custom_id.startswith("ttt_"):
                    continue
                _, r, c = button_custom_id.split("_")
                r, c = int(r), int(c)
                button_label = typed_button.label if hasattr(typed_button, "label") else None
                if button_label == "X":
                    board[r][c] = "X"
                elif button_label == "O":
                    board[r][c] = "O"

        # Update the board with the user's move
        board[player_move_row][player_move_col] = "X"

        # Check if the game has reached a terminal state after the user's move
        if ttt_check_terminal_state(board):
            terminal_value = ttt_get_terminal_state_value(board)
            if terminal_value == 1:
                result_embed = discord.Embed(
                    title="You win!",
                    description="Congratulations, you won the game!",
                    color=get_random_color(),
                )
            elif terminal_value == -1:
                result_embed = discord.Embed(
                    title="Bot wins!",
                    description="Sorry, the bot won this time.",
                    color=get_random_color(),
                )
            else:
                result_embed = discord.Embed(
                    title="It's a tie!",
                    description="The game ended in a draw.",
                    color=get_random_color(),
                )
            await interaction.response.edit_message(embed=result_embed, view=None)
            return
        
        # Bot's turn to make a move using minimax algorithm
        possible_moves = ttt_get_possible_moves_in_turn(board)
        best_score = float("inf")
        best_move: tuple[int, int] | None = None
        for move in possible_moves:
            next_board = ttt_get_state_after_move(board, move)
            score = ttt_minimax(next_board, float("-inf"), float("inf"))
            if score < best_score:
                best_score = score
                best_move = move

        if best_move is None:
            await interaction.response.defer()
            return

        bot_row, bot_col = best_move
        board[bot_row][bot_col] = "O"

        # Check if the game has reached a terminal state after the bot's move
        game_over = ttt_check_terminal_state(board)
        if game_over:
            terminal_value = ttt_get_terminal_state_value(board)
            if terminal_value == 1:
                result_embed = discord.Embed(
                    title="You win!",
                    description="Congratulations, you won the game!",
                    color=get_random_color(),
                )
            elif terminal_value == -1:
                result_embed = discord.Embed(
                    title="Bot wins!",
                    description="Sorry, the bot won this time.",
                    color=get_random_color(),
                )
            else:
                result_embed = discord.Embed(
                    title="It's a tie!",
                    description="The game ended in a draw.",
                    color=get_random_color(),
                )
        else:
            result_embed = discord.Embed(
                title="Tic Tac Toe",
                description="Select a move.",
                color=get_random_color(),
            )

        updated_view = discord.ui.View()
        for i in range(3):
            for j in range(3):
                cell = board[i][j]
                if cell == "X":
                    label = "X"
                    style = discord.ButtonStyle.success
                elif cell == "O":
                    label = "O"
                    style = discord.ButtonStyle.danger
                else:
                    label = "\u200b"
                    style = discord.ButtonStyle.secondary

                updated_view.add_item(
                    discord.ui.Button(
                        label=label,
                        style=style,
                        custom_id=f"ttt_{i}_{j}",
                        row=i,
                        disabled=game_over or cell != "",
                    )
                )

        await interaction.response.edit_message(
            embed=result_embed,
            view=updated_view,
        )