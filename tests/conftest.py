"""Stand-ins for the Discord objects the commands under test touch.

Nothing here talks to Discord or MongoDB. Tests that need the database layer
patch it themselves, so that a missing patch shows up as a test that talks to a
fake collection rather than one that quietly succeeds.
"""

from typing import Any

import pytest

from bot import database_sync, global_state

# The mutable containers the commands read and write. Tests are free to assign
# straight over these, which is why they are listed rather than discovered.
MUTABLE_STATE = (
    "custom_replies",
    "balance_map",
    "inventory",
    "user_settings_map",
    "user_worked_times",
    "user_robbed_times",
    "user_daily_times",
    "user_weekly_times",
    "user_monthly_times",
    "warn_map",
    "laptop_history",
)


@pytest.fixture(autouse=True)
def isolated_state():
    """Give every test the bot's start-up state, and take it away afterwards.

    The commands read and write these dicts in place, so without this a test
    would inherit whatever the previous one left behind and the suite would
    only pass in one order. All of them start empty, so replacing them with a
    fresh dict is exactly the start-up state; the original objects are handed
    back untouched on the way out.
    """
    saved = {name: getattr(global_state, name) for name in MUTABLE_STATE}
    for name in MUTABLE_STATE:
        setattr(global_state, name, {})
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(global_state, name, value)


class _Discarded:
    """A collection that accepts writes and keeps nothing."""

    def replace_one(self, *args, **kwargs):
        pass


@pytest.fixture(autouse=True)
def drained_writer():
    """Keep one test's queued writes out of the next test.

    The writer's pending dict is module-level and shared, so a save a test
    triggered but did not wait for would land in whichever collection the next
    test installed, and show up there as an unexpected extra write. Anything
    still queued on the way out is drained into a throwaway collection.

    Only the teardown is redirected: patching the collection for the whole test
    would hide the shared-client behaviour that test_database_sync checks.
    """
    yield

    real_collection = database_sync._collection
    database_sync._collection = _Discarded
    try:
        database_sync.flush()
    finally:
        database_sync._collection = real_collection


class FakeUser:
    """Enough of a discord.User for the code under test."""

    def __init__(self, user_id: int, name: str = "user") -> None:
        self.id = user_id
        self.name = name
        self.display_name = name
        self.bot = False

    def __str__(self) -> str:
        return self.display_name


class FakeInteraction:
    """Records replies instead of sending them.

    `sent` holds an (embed, view) pair for every response.send_message call.
    Set `client` for the commands that read the command tree off the
    interaction, which is how /help finds its categories.
    """

    def __init__(self, user: FakeUser | None = None, *, guild: bool = True) -> None:
        self.user = user or FakeUser(1)
        self.guild = object() if guild else None
        self.client: Any = None
        self.data: Any = None
        self.sent: list[tuple[Any, Any]] = []
        self.edited: list[Any] = []
        self.followups: list[Any] = []
        self.deferred = False

        interaction = self

        class _Response:
            """Mirrors the real response object closely enough that code
            guarding against a double response is exercised for real."""

            def is_done(_self):
                return interaction.deferred or bool(
                    interaction.sent or interaction.edited
                )

            async def send_message(_self, *, embed=None, view=None, content=None,
                                    ephemeral=False, **kwargs):
                interaction.sent.append((embed, view))

            async def edit_message(_self, *, embed=None, view=None, **kwargs):
                interaction.edited.append(embed)

            async def defer(_self, *, ephemeral=False, thinking=False):
                interaction.deferred = True

        class _Followup:
            async def send(_self, *, embed=None, view=None, content=None,
                           ephemeral=False, **kwargs):
                interaction.followups.append(embed)

        self.response = _Response()
        self.followup = _Followup()