"""
Nitro shop item.

The boost works by clearing whatever is left of the cooldowns it refunds, so
that is modelled as an object with the two timers it touches rather than as a
loop over a tuple built at the call site.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from bot.core import database_sync, global_state


class NitroBoost:
    """Clears the remaining work and daily cooldown for one user."""

    def __init__(self, user_id: int) -> None:
        self.user_id = user_id

    def _clear(
        self,
        times: dict,
        cooldown: float,
        save: Callable[[], None],
    ) -> None:
        """Refund whatever is left on one timer, if it is still counting down."""
        if self.user_id not in times:
            return

        elapsed = (datetime.now(UTC) - times[self.user_id]).total_seconds()
        remaining = cooldown - elapsed
        if remaining > 0:
            times[self.user_id] -= timedelta(seconds=remaining)
            save()

    def apply(self) -> None:
        """Refund both cooldowns."""
        self._clear(
            global_state.user_worked_times,
            global_state.BASIC_COOLDOWN,
            database_sync.save_works,
        )
        self._clear(
            global_state.user_daily_times,
            global_state.DAILY_COOLDOWN,
            database_sync.save_dailies,
        )


async def use_nitro(interaction) -> None:
    """Shop hook: apply the boost to whoever used the item."""
    NitroBoost(interaction.user.id).apply()
