"""credit / debit: the single path every balance change in the bot goes through.

These were the least-covered code in the bot, and they are also the only thing
that moves money, so each branch is pinned here rather than left to the commands
that happen to call them.
"""

import pytest

from bot.core import database_sync, global_state
from bot.core.transactions import credit, debit
from bot.objects.user_settings import UserSettings
from tests.conftest import FakeInteraction, FakeUser


class FakeBankUser(FakeUser):
    """A user who can be DMed, recording what they were sent."""

    def __init__(self, user_id: int, name: str = "user") -> None:
        super().__init__(user_id, name)
        self.dms: list = []

    async def send(self, *, embed=None, **kwargs):
        self.dms.append(embed)


class ClosedDMsUser(FakeBankUser):
    """A user whose DMs are shut, which is ordinary rather than an error."""

    async def send(self, *, embed=None, **kwargs):
        raise RuntimeError("Cannot send messages to this user")


@pytest.fixture(autouse=True)
def quiet_saves(monkeypatch):
    """Recording a save is the writer's job, tested in test_database_sync."""
    monkeypatch.setattr(database_sync, "save_balances", lambda: None)


def description(interaction: FakeInteraction) -> str:
    embed, _ = interaction.sent[0]
    return embed.description


# ------------------------------------------------------------------- credit


async def test_credit_opens_an_account_for_someone_new():
    """Nobody is in balance_map until they are paid for the first time."""
    user = FakeBankUser(1)
    assert await credit(500, user, FakeInteraction(user)) is True
    assert global_state.balance_map[1] == 500


async def test_credit_adds_to_an_existing_balance():
    user = FakeBankUser(1)
    global_state.balance_map = {1: 200}
    assert await credit(300, user, FakeInteraction(user)) is True
    assert global_state.balance_map[1] == 500


async def test_credit_of_nothing_or_less_is_refused():
    user = FakeBankUser(1)
    interaction = FakeInteraction(user)
    assert await credit(0, user, interaction) is False
    assert await credit(-50, user, interaction) is False
    assert global_state.balance_map == {}


async def test_a_credit_is_persisted(monkeypatch):
    """The balance change is worthless if the save is skipped."""
    saved: list[int] = []
    user = FakeBankUser(1)
    monkeypatch.setattr(database_sync, "save_balances", lambda: saved.append(1))
    await credit(500, user, FakeInteraction(user))
    assert saved == [1]


# -------------------------------------------------------------------- debit


async def test_debit_takes_from_the_balance():
    user = FakeBankUser(1)
    global_state.balance_map = {1: 500}
    assert await debit(200, user, FakeInteraction(user)) is True
    assert global_state.balance_map[1] == 300


async def test_debit_will_not_overdraw():
    user = FakeBankUser(1)
    global_state.balance_map = {1: 100}
    interaction = FakeInteraction(user)
    assert await debit(101, user, interaction) is False
    assert global_state.balance_map[1] == 100
    assert "more than you have" in description(interaction)


async def test_debit_from_an_empty_account_says_so_plainly():
    user = FakeBankUser(1)
    global_state.balance_map = {1: 0}
    interaction = FakeInteraction(user)
    assert await debit(1, user, interaction) is False
    assert "no money" in description(interaction)


async def test_debit_of_nothing_or_less_is_refused():
    user = FakeBankUser(1)
    global_state.balance_map = {1: 500}
    assert await debit(0, user, FakeInteraction(user)) is False
    assert await debit(-1, user, FakeInteraction(user)) is False
    assert global_state.balance_map[1] == 500


async def test_an_overdraft_attempt_does_not_save(monkeypatch):
    saved: list[int] = []
    user = FakeBankUser(1)
    global_state.balance_map = {1: 100}
    monkeypatch.setattr(database_sync, "save_balances", lambda: saved.append(1))
    await debit(500, user, FakeInteraction(user))
    assert saved == []


# --------------------------------------------------------------- bank DMs


async def test_a_bank_dm_reports_the_three_figures():
    user = FakeBankUser(1)
    global_state.balance_map = {1: 100}
    global_state.user_settings_map = {1: UserSettings(bank_dm_enabled=True)}

    await credit(50, user, FakeInteraction(user))

    assert len(user.dms) == 1
    opening, deposited, closing = (field.value for field in user.dms[0].fields)
    assert (opening, deposited, closing) == (":coin: 100", ":coin: 50", ":coin: 150")


async def test_a_bank_dm_is_not_sent_when_it_is_turned_off():
    user = FakeBankUser(1)
    global_state.user_settings_map = {1: UserSettings(bank_dm_enabled=False)}
    await credit(50, user, FakeInteraction(user))
    assert user.dms == []


async def test_a_bank_dm_is_not_attempted_for_a_user_with_no_settings():
    user = FakeBankUser(1)
    global_state.user_settings_map = {}
    await credit(50, user, FakeInteraction(user))
    assert user.dms == []


async def test_a_shut_dm_does_not_fail_the_transaction():
    """The money has already moved by the time the DM is attempted."""
    user = ClosedDMsUser(1)
    global_state.user_settings_map = {1: UserSettings(bank_dm_enabled=True)}

    assert await credit(50, user, FakeInteraction(user)) is True
    assert global_state.balance_map[1] == 50
