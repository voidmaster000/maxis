"""
Modal submission handlers
"""

from datetime import UTC, datetime

import discord

from bot import global_state
from bot.helper import get_random_color
from bot.objects.hacker_laptop import HackerLaptop, LaptopHistory
from bot.transactions import credit, debit


class ModalsListener:
    @staticmethod
    async def _defer_error(interaction: discord.Interaction, message: str) -> None:
        """Defer the modal, then tell the user what went wrong, privately."""
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(
            embed=discord.Embed(
                title="Error!",
                description=message,
                color=get_random_color(),
            ),
            ephemeral=True,
        )

    @staticmethod
    async def on_modal_submit(interaction: discord.Interaction):
        """Handle modal submissions"""
        custom_id = interaction.data.get("custom_id", "") if interaction.data else None
        if not custom_id:
            return

        if custom_id.startswith("laptop_cmd_input:"):
            await ModalsListener._handle_laptop_command(interaction, custom_id)

    @staticmethod
    def _append_history(
        user_id: int,
        command: str,
        result: str,
        secret1: str | None = None,
        secret2: str | None = None,
        secret3: int | None = None,
    ):
        """Append a command entry to persistent history file."""
        LaptopHistory(user_id).append(
            command,
            result,
            secret1=secret1,
            secret2=secret2,
            secret3=secret3,
        )

    @staticmethod
    async def _refresh_laptop_message(
        interaction: discord.Interaction,
        user_id: int,
        shutdown: bool = False,
    ):
        """Refresh command history in original laptop message."""
        try:
            if not shutdown:
                laptop = HackerLaptop(user_id, interaction.user.display_name)
                await interaction.response.edit_message(embed=laptop.screen())
            else:
                await interaction.response.edit_message(
                    embed=discord.Embed(
                        title="PC has been shut down.",
                        color=get_random_color(),
                    )
                )
        except discord.Forbidden:
            return
        except discord.NotFound:
            return
        except Exception as ex:
            print(f"Error refreshing laptop message: {ex}")

    @staticmethod
    async def _handle_laptop_command(interaction: discord.Interaction, custom_id: str):
        """Execute laptop command from command prompt modal."""
        try:
            parts = custom_id.split(":")
            if len(parts) != 2:
                return

            _, user_id_raw = parts
            owner_id = int(user_id_raw)

            if owner_id != interaction.user.id:
                await ModalsListener._defer_error(
                    interaction, "You can't use someone else's PC!"
                )
                return

            command_input = (
                interaction.data.get("components", [{}])[0].get("components", [{}])[0]
                if interaction.data
                else None
            )
            if not command_input:
                await ModalsListener._defer_error(interaction, "No command entered.")
                return

            command_text = (command_input.get("value", "") or "").strip()
            if not command_text:
                await ModalsListener._defer_error(
                    interaction, "Command cannot be empty."
                )
                return

            parts = command_text.split(maxsplit=1)
            command = parts[0].lower()
            command_arg = parts[1].strip() if len(parts) > 1 else ""

            match command:
                case "help":
                    ModalsListener._append_history(owner_id, command, "listed commands")
                    await ModalsListener._refresh_laptop_message(interaction, owner_id)
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="Available Commands",
                            description="`help` - show commands\n`code` - show challenge question\n`codeanswer <answer>` - use only after `code`\n`shutdown` - shut down laptop\n`datetime` - show current UTC date and time",
                            color=get_random_color(),
                        ),
                        ephemeral=True,
                    )
                case "code":
                    if (
                        owner_id not in global_state.inventory
                        or "Hacker Code" not in global_state.inventory[owner_id]
                        or global_state.inventory[owner_id]["Hacker Code"] <= 0
                    ):
                        ModalsListener._append_history(
                            owner_id, command, "failed: missing Hacker Code"
                        )
                        await ModalsListener._refresh_laptop_message(
                            interaction, owner_id
                        )
                        await interaction.followup.send(
                            embed=discord.Embed(
                                title="Error!",
                                description="You don't have the Hacker Code! Buy it from the shop.",
                                color=get_random_color(),
                            ),
                            ephemeral=True,
                        )
                        return

                    question, pattern, answer = HackerLaptop.challenge()
                    ModalsListener._append_history(
                        owner_id,
                        command,
                        "challenge ready",
                        secret1=question,
                        secret2=pattern,
                        secret3=answer,
                    )
                    await ModalsListener._refresh_laptop_message(interaction, owner_id)
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="Code Challenge",
                            description=(
                                f"{question}\nPattern: `{pattern}`\n"
                                "Run `codeanswer <answer>` to submit."
                            ),
                            color=get_random_color(),
                        ),
                        ephemeral=True,
                    )
                case "codeanswer":
                    if not command_arg:
                        await ModalsListener._defer_error(
                            interaction, "Usage: `codeanswer <answer>`"
                        )
                        return

                    last_cmd = LaptopHistory(owner_id).last()
                    if not last_cmd or last_cmd.get("command") != "code":
                        await ModalsListener._defer_error(
                            interaction, "Run `code` first."
                        )
                        return

                    answer_raw = last_cmd.get("secret3")
                    if not answer_raw:
                        await ModalsListener._defer_error(
                            interaction, "No active challenge found. Run `code` again."
                        )
                        return

                    try:
                        user_answer = int(command_arg)
                        correct_answer = int(answer_raw)
                    except ValueError:
                        if await debit(
                            global_state.PRIZE_OR_COST, interaction.user, interaction
                        ):
                            ModalsListener._append_history(
                                owner_id,
                                "codeanswer",
                                f"invalid input (-{global_state.PRIZE_OR_COST})",
                            )
                            await ModalsListener._refresh_laptop_message(
                                interaction, owner_id
                            )
                            await interaction.followup.send(
                                embed=discord.Embed(
                                    title="Failure!",
                                    description=f"Hacking failed due to incorrect input type. You lost :coin: {global_state.PRIZE_OR_COST}",
                                    color=get_random_color(),
                                ),
                            )
                        return

                    if user_answer == correct_answer:
                        if await credit(
                            global_state.PRIZE_OR_COST, interaction.user, interaction
                        ):
                            ModalsListener._append_history(
                                owner_id,
                                "codeanswer",
                                f"success (+{global_state.PRIZE_OR_COST})",
                            )
                            await ModalsListener._refresh_laptop_message(
                                interaction, owner_id
                            )
                            await interaction.followup.send(
                                embed=discord.Embed(
                                    title="Success!",
                                    description=f"Hacking successful! You got :coin: {global_state.PRIZE_OR_COST}",
                                    color=get_random_color(),
                                )
                            )
                    else:
                        if await debit(
                            global_state.PRIZE_OR_COST, interaction.user, interaction
                        ):
                            ModalsListener._append_history(
                                owner_id,
                                "codeanswer",
                                f"failed (-{global_state.PRIZE_OR_COST})",
                            )
                            await ModalsListener._refresh_laptop_message(
                                interaction, owner_id
                            )
                            await interaction.followup.send(
                                embed=discord.Embed(
                                    title="Failure!",
                                    description=f"Hacking failed due to wrong answer. You lost :coin: {global_state.PRIZE_OR_COST}",
                                    color=get_random_color(),
                                )
                            )
                case "shutdown":
                    ModalsListener._append_history(
                        owner_id, command, "laptop shut down"
                    )
                    await ModalsListener._refresh_laptop_message(
                        interaction,
                        owner_id,
                        shutdown=True,
                    )
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="Laptop",
                            description="You shut down the laptop.",
                            color=get_random_color(),
                        ),
                        ephemeral=True,
                    )
                case "datetime":
                    embed = discord.Embed(
                        title="Current Date & Time:", color=get_random_color()
                    )
                    embed.add_field(
                        name="Local Time",
                        value=f"<t:{int(datetime.now().timestamp())}:F>",
                    )
                    embed.add_field(
                        name="UTC/GMT",
                        value=datetime.now(UTC).strftime("%d %B %Y %I:%M:%S %p"),
                    )
                    ModalsListener._append_history(
                        owner_id, command, "displayed current utc datetime"
                    )
                    await ModalsListener._refresh_laptop_message(interaction, owner_id)
                    await interaction.followup.send(embed=embed, ephemeral=True)
                case _:
                    ModalsListener._append_history(owner_id, command, "unknown command")
                    await ModalsListener._refresh_laptop_message(interaction, owner_id)
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="Unknown Command",
                            description="Use `help` to view available commands.",
                            color=get_random_color(),
                        ),
                        ephemeral=True,
                    )
        except Exception as e:
            print(f"Error handling laptop command: {e}")
            await ModalsListener._defer_error(
                interaction, "An error occurred while executing your command."
            )
