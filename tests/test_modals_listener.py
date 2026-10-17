"""The hacker laptop modal: dispatch, history, and error reporting.

The regression this exists for: _defer_error used to call itself, so every
laptop error path recursed until the stack ran out. A recursion storm on the
event loop is slow enough to blow the three seconds Discord gives an
interaction to answer.
"""

import pytest

from bot import global_state
from bot.modals_listener import ModalsListener
from tests.conftest import FakeInteraction, FakeUser

OWNER_ID = 42


def submit(command: str, user_id: int = OWNER_ID) -> FakeInteraction:
    """A modal submission in the shape Discord delivers it."""
    interaction = FakeInteraction(FakeUser(user_id, "Arpan"))
    interaction.data = {
        "custom_id": f"laptop_cmd_input:{OWNER_ID}",
        "components": [{"components": [{"value": command}]}],
    }
    return interaction


def error_texts(interaction: FakeInteraction) -> list[str]:
    return [embed.description for embed in interaction.followups]


@pytest.fixture(autouse=True)
def quiet_saves(monkeypatch):
    """Nothing in this file may reach MongoDB."""
    for name in (
        "save_laptop_history",
        "save_balances",
        "save_inventory",
        "save_user_settings",
        "save_replies",
    ):
        monkeypatch.setattr(f"bot.database_sync.{name}", lambda: None)
    global_state.laptop_history.clear()
    global_state.inventory = {}


# --------------------------------------------------------------- _defer_error


async def test_defer_error_answers_the_modal_privately():
    """Defer, then report. Calling itself instead would recurse until the
    stack ran out, and the RecursionError would look like nothing at all."""
    interaction = submit("shutdown")

    await ModalsListener._defer_error(interaction, "Something went wrong.")

    assert interaction.deferred is True
    assert [embed.title for embed in interaction.followups] == ["Error!"]
    assert interaction.followups[0].description == "Something went wrong."


async def test_defer_error_still_reports_when_already_responded():
    """Some paths edit the laptop message before failing, so the interaction
    is spent. Deferring a second time raises."""
    interaction = submit("shutdown")
    interaction.deferred = True

    await ModalsListener._defer_error(interaction, "Something went wrong.")

    assert [embed.title for embed in interaction.followups] == ["Error!"]


# ------------------------------------------------------------------- dispatch


async def test_a_submission_with_no_custom_id_is_ignored():
    interaction = FakeInteraction()
    interaction.data = {}

    await ModalsListener.on_modal_submit(interaction)

    assert interaction.sent == [] and interaction.followups == []


async def test_a_malformed_custom_id_is_ignored():
    interaction = FakeInteraction()
    interaction.data = {"custom_id": "laptop_cmd_input:42:extra"}

    await ModalsListener.on_modal_submit(interaction)

    assert interaction.sent == [] and interaction.followups == []


async def test_someone_elses_laptop_is_refused():
    interaction = submit("help", user_id=99)

    await ModalsListener.on_modal_submit(interaction)

    assert error_texts(interaction) == ["You can't use someone else's PC!"]


@pytest.mark.parametrize("blank", ["", "   "])
async def test_an_empty_command_is_refused(blank):
    interaction = submit(blank)

    await ModalsListener.on_modal_submit(interaction)

    assert error_texts(interaction) == ["Command cannot be empty."]


async def test_help_is_recorded_in_the_history():
    await ModalsListener.on_modal_submit(submit("help"))

    entry = global_state.laptop_history[str(OWNER_ID)][0]
    assert entry["command"] == "help"
    assert entry["result"] == "listed commands"


async def test_an_unknown_command_says_so():
    interaction = submit("rm -rf /")

    await ModalsListener.on_modal_submit(interaction)

    assert global_state.laptop_history[str(OWNER_ID)][0]["result"] == (
        "unknown command"
    )


async def test_the_history_is_keyed_by_the_owner():
    await ModalsListener.on_modal_submit(submit("datetime"))

    assert list(global_state.laptop_history) == [str(OWNER_ID)]


async def test_a_code_challenge_needs_the_hacker_code_item():
    await ModalsListener.on_modal_submit(submit("code"))

    assert global_state.laptop_history[str(OWNER_ID)][0]["result"] == (
        "failed: missing Hacker Code"
    )


async def test_answering_a_challenge_that_was_never_asked_for():
    interaction = submit("codeanswer 5")

    await ModalsListener.on_modal_submit(interaction)

    assert error_texts(interaction) == ["Run `code` first."]


async def test_answering_with_no_answer_is_a_usage_error():
    interaction = submit("codeanswer")

    await ModalsListener.on_modal_submit(interaction)

    assert error_texts(interaction) == ["Usage: `codeanswer <answer>`"]
