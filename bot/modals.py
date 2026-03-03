"""
Modal submission handlers
"""

from datetime import datetime, timezone
import discord
from bot.helper import get_random_color, credit_balance, debit_balance, generate_pattern
from bot.objects.shop import Shop
from bot.objects.hacker_laptop import (
    format_user_cmd_history,
    append_user_cmd_history,
    get_last_user_cmd,
)

PRIZE_OR_COST = 9000


def _get_main():
    """Lazy import Main to avoid circular imports with bot.main."""
    from bot.main import Main  # type: ignore

    return Main


class ModalsListener:
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
        append_user_cmd_history(
            user_id,
            command,
            result,
            secret1=secret1,
            secret2=secret2,
            secret3=secret3,
        )

    @staticmethod
    async def _refresh_laptop_message(
        interaction: discord.Interaction,
        message_id: int,
        user_id: int,
        shutdown: bool = False,
    ):
        """Refresh command history in original laptop message."""
        if message_id <= 0:
            return

        try:
            if not shutdown:
                updated = discord.Embed(
                    title=f"{interaction.user.display_name}'s PC",
                    color=get_random_color(),
                )
                updated.add_field(name="OS", value="MaxisOS")
                updated.add_field(name="VPN Status", value="Connected to MaxisVPN")
                updated.add_field(
                    name="Command History",
                    value=format_user_cmd_history(user_id),
                    inline=False,
                )
                await interaction.response.edit_message(embed=updated)
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
            if len(parts) != 3:
                return

            _, user_id_raw, message_id_raw = parts
            owner_id = int(user_id_raw)
            message_id = int(message_id_raw)

            if owner_id != interaction.user.id:
                await interaction.response.defer()
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Error!",
                        description="You can't use someone else's PC!",
                        color=get_random_color(),
                    ),
                    ephemeral=True,
                )
                return

            command_input = (
                interaction.data.get("components", [{}])[0].get("components", [{}])[0]
                if interaction.data
                else None
            )
            if not command_input:
                await interaction.response.defer()
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Error!",
                        description="No command entered.",
                        color=get_random_color(),
                    ),
                    ephemeral=True,
                )
                return

            command_text = (command_input.get("value", "") or "").strip()
            if not command_text:
                await interaction.response.defer()
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Error!",
                        description="Command cannot be empty.",
                        color=get_random_color(),
                    ),
                    ephemeral=True,
                )
                return

            parts = command_text.split(maxsplit=1)
            command = parts[0].lower()
            command_arg = parts[1].strip() if len(parts) > 1 else ""

            if command == "help":
                ModalsListener._append_history(owner_id, command, "listed commands")
                await ModalsListener._refresh_laptop_message(
                    interaction, message_id, owner_id
                )
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Available Commands",
                        description="`help` - show commands\n`code` - show challenge question\n`codeanswer <answer>` - use only after `code`\n`shutdown` - shut down laptop\n`datetime` - show current UTC date and time",
                        color=get_random_color(),
                    ),
                    ephemeral=True,
                )
                return

            if command == "code":
                if (
                    owner_id not in Shop.owned_items
                    or "Hacker Code" not in Shop.owned_items[owner_id]
                    or Shop.owned_items[owner_id]["Hacker Code"] <= 0
                ):
                    ModalsListener._append_history(
                        owner_id, command, "failed: missing Hacker Code"
                    )
                    await ModalsListener._refresh_laptop_message(
                        interaction, message_id, owner_id
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

                question, pattern, answer = generate_pattern()
                ModalsListener._append_history(
                    owner_id,
                    command,
                    "challenge ready",
                    secret1=question,
                    secret2=pattern,
                    secret3=answer,
                )
                await ModalsListener._refresh_laptop_message(
                    interaction, message_id, owner_id
                )
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
                return

            if command == "codeanswer":
                if not command_arg:
                    await interaction.response.defer()
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="Error!",
                            description="Usage: `codeanswer <answer>`",
                            color=get_random_color(),
                        ),
                        ephemeral=True,
                    )
                    return

                last_cmd = get_last_user_cmd(owner_id)
                if not last_cmd or last_cmd.get("command") != "code":
                    await interaction.response.defer()
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="Error!",
                            description="Run `code` first.",
                            color=get_random_color(),
                        ),
                        ephemeral=True,
                    )
                    return

                answer_raw = last_cmd.get("secret3")
                if not answer_raw:
                    await interaction.response.defer()
                    await interaction.followup.send(
                        embed=discord.Embed(
                            title="Error!",
                            description="No active challenge found. Run `code` again.",
                            color=get_random_color(),
                        ),
                        ephemeral=True,
                    )
                    return

                Main = _get_main()
                try:
                    user_answer = int(command_arg)
                    correct_answer = int(answer_raw)
                except ValueError:
                    if await debit_balance(
                        PRIZE_OR_COST,
                        interaction,
                        Main.CONNSTR,
                        Main.user_settings_map,
                        Main.balance_map,
                    ):
                        ModalsListener._append_history(
                            owner_id, "codeanswer", f"invalid input (-{PRIZE_OR_COST})"
                        )
                        await ModalsListener._refresh_laptop_message(
                            interaction, message_id, owner_id
                        )
                        await interaction.followup.send(
                            embed=discord.Embed(
                                title="Failure!",
                                description=f"Hacking failed due to incorrect input type. You lost :coin: {PRIZE_OR_COST}",
                                color=get_random_color(),
                            ),
                        )
                    return

                if user_answer == correct_answer:
                    if await credit_balance(
                        PRIZE_OR_COST,
                        interaction,
                        Main.CONNSTR,
                        Main.user_settings_map,
                        Main.balance_map,
                    ):
                        ModalsListener._append_history(
                            owner_id, "codeanswer", f"success (+{PRIZE_OR_COST})"
                        )
                        await ModalsListener._refresh_laptop_message(
                            interaction, message_id, owner_id
                        )
                        await interaction.followup.send(
                            embed=discord.Embed(
                                title="Success!",
                                description=f"Hacking successful! You got :coin: {PRIZE_OR_COST}",
                                color=get_random_color(),
                            )
                        )
                else:
                    if await debit_balance(
                        PRIZE_OR_COST,
                        interaction,
                        Main.CONNSTR,
                        Main.user_settings_map,
                        Main.balance_map,
                    ):
                        ModalsListener._append_history(
                            owner_id, "codeanswer", f"failed (-{PRIZE_OR_COST})"
                        )
                        await ModalsListener._refresh_laptop_message(
                            interaction, message_id, owner_id
                        )
                        await interaction.followup.send(
                            embed=discord.Embed(
                                title="Failure!",
                                description=f"Hacking failed due to wrong answer. You lost :coin: {PRIZE_OR_COST}",
                                color=get_random_color(),
                            )
                        )
                return

            if command == "shutdown":
                ModalsListener._append_history(owner_id, command, "laptop shut down")
                await ModalsListener._refresh_laptop_message(
                    interaction,
                    message_id,
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
                return

            if command == "datetime":
                embed = discord.Embed(
                    title="Current Date & Time:", color=get_random_color()
                )
                embed.add_field(
                    name="Local Time", value=f"<t:{int(datetime.now().timestamp())}:F>"
                )
                embed.add_field(
                    name="UTC/GMT",
                    value=datetime.now(timezone.utc).strftime("%d %B %Y %I:%M:%S %p"),
                )
                ModalsListener._append_history(
                    owner_id, command, "displayed current utc datetime"
                )
                await ModalsListener._refresh_laptop_message(
                    interaction, message_id, owner_id
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            ModalsListener._append_history(owner_id, command, "unknown command")
            await ModalsListener._refresh_laptop_message(
                interaction, message_id, owner_id
            )
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
            await interaction.response.defer()
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Error!",
                    description="An error occurred while executing your command.",
                    color=get_random_color(),
                ),
                ephemeral=True,
            )
