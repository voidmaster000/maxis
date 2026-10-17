"""
Account transactions for Maxis.

Every balance change in the bot goes through `credit` or `debit`, so the
"open the account if it is new, apply the change, DM the user, persist" sequence
lives in exactly one place.
"""

import discord

from bot import database_sync, global_state
from bot.helper import get_random_color


async def _error(interaction: discord.Interaction, message: str) -> None:
    await interaction.response.send_message(
        embed=discord.Embed(
            title="Error!",
            description=message,
            color=get_random_color(),
        )
    )


async def _notify(
    user: discord.User | discord.Member,
    opening: int,
    amount: int,
    closing: int,
    label: str,
) -> None:
    """DM the user about a balance change, if they have bank DMs enabled."""
    settings = global_state.user_settings_map.get(user.id)
    if not settings or not settings.bank_dm_enabled:
        return

    embed = discord.Embed(
        title="Successfully updated account! Details:-",
        color=get_random_color(),
    )
    embed.add_field(name="Opening Balance", value=f":coin: {opening}")
    embed.add_field(name=label, value=f":coin: {amount}")
    embed.add_field(name="Closing Balance", value=f":coin: {closing}")

    try:
        await user.send(embed=embed)
    except Exception as e:
        print(f"Error sending DM: {e}")


def _balance(user: discord.User | discord.Member) -> int:
    """Current balance for a user, defaulting to 0 for accounts never seen."""
    return global_state.balance_map.get(user.id, 0)


async def credit(
    amount: int,
    user: discord.User | discord.Member,
    interaction: discord.Interaction,
) -> bool:
    """Add `amount` to `user`'s balance. Replies on error and returns False."""
    opening = _balance(user)

    if amount <= 0:
        await _error(interaction, "Value should be more than 0.")
        return False

    closing = opening + amount
    global_state.balance_map[user.id] = closing
    await _notify(user, opening, amount, closing, "Deposited")
    database_sync.save_balances()
    return True


async def debit(
    amount: int,
    user: discord.User | discord.Member,
    interaction: discord.Interaction,
) -> bool:
    """Remove `amount` from `user`'s balance. Replies on error and returns False."""
    opening = _balance(user)

    if amount <= 0:
        await _error(interaction, "Value should be more than 0.")
        return False

    if amount > opening:
        await _error(
            interaction,
            (
                "You can't withdraw, because you have no money!"
                if opening == 0
                else "You can't withdraw more than you have in your bank!"
            ),
        )
        return False

    closing = opening - amount
    global_state.balance_map[user.id] = closing
    await _notify(user, opening, amount, closing, "Withdrawn")
    database_sync.save_balances()
    return True
