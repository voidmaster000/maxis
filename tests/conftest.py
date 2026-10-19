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

# Captured before any fixture replaces it, for the few tests that exercise how
# a client is obtained rather than what gets written to it.
REAL_COLLECTION = database_sync._collection


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

    def find(self):
        return iter(())


@pytest.fixture(autouse=True)
def no_real_database():
    """Point the writer at a throwaway collection for the whole test.

    global_state.CONNSTR is the production connection string on this machine,
    and _collection() opens a real MongoClient from it on first use. The writer
    thread runs concurrently with the test, so anything queued during the test
    could be written before a teardown-only redirect took effect -- and was.
    That is how test data reached the live balance document: a balance entry
    for user 1, which is not a Discord snowflake, sits in production next to a
    real one.

    Tests that want to see writes install their own collection over this one.
    """
    collection = _Discarded()
    real = database_sync._collection
    database_sync._collection = lambda: collection

    # Pretend every document loaded cleanly and empty, so the guards in
    # save_*() let a test write freely. A fresh install is the same thing.
    real_counts = database_sync._loaded_counts
    database_sync._loaded_counts = dict.fromkeys(database_sync.DOCUMENTS, 0)

    try:
        yield collection
        database_sync.flush()
    finally:
        database_sync._collection = real
        database_sync._loaded_counts = real_counts


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
        self.message: Any = None
        self.sent: list[tuple[Any, Any]] = []
        self.edited: list[Any] = []
        self.followups: list[Any] = []
        self.followup_views: list[Any] = []
        self.modals: list[Any] = []
        self.deferred = False

        interaction = self

        class _Response:
            """Mirrors the real response object closely enough that code
            guarding against a double response is exercised for real."""

            def is_done(_self):
                return interaction.deferred or bool(
                    interaction.sent or interaction.edited
                )

            async def send_message(
                _self, *, embed=None, view=None, content=None, ephemeral=False, **kwargs
            ):
                interaction.sent.append((embed, view))

            async def edit_message(_self, *, embed=None, view=None, **kwargs):
                interaction.edited.append(embed)

            async def defer(_self, *, ephemeral=False, thinking=False):
                interaction.deferred = True

            async def send_modal(_self, modal, **kwargs):
                interaction.modals.append(modal)

        class _Followup:
            async def send(
                _self, *, embed=None, view=None, content=None, ephemeral=False, **kwargs
            ):
                interaction.followups.append(embed)
                interaction.followup_views.append(view)

        self.response = _Response()
        self.followup = _Followup()
