"""Component interactions: the buttons, the dropdown, and the dispatcher.

The dispatcher is the way in for every button and select in the bot, so an
unrecognised custom_id has to be answered rather than left to time out. The
handlers behind it were the thinnest-tested code left after the cleanup.
"""

import asyncio
from types import SimpleNamespace

import pytest

from bot.listeners.components_listener import ComponentsListener
from bot.main import bot, setup_slash_commands
from tests.conftest import FakeInteraction, FakeUser

RPS_TITLES = {"You win!", "Bot wins!", "Tie!", "Error!"}


@pytest.fixture(scope="module", autouse=True)
def registered():
    """The dropdown reads its categories off the real tree, as /help does.

    Registration happens once for the process, so this only does it if some
    other module has not already.
    """
    if bot.get_cog("Utility") is None:
        asyncio.run(setup_slash_commands(bot))
    return bot


class FakeButton:
    """The two attributes TicTacToe.from_components reads off a button."""

    def __init__(self, custom_id: str, label: str) -> None:
        self.custom_id = custom_id
        self.label = label


class FakeRow:
    def __init__(self, *children: FakeButton) -> None:
        self.children = children


def board_rows(player_id: int = 1, marks: dict[tuple[int, int], str] | None = None):
    """A message's components for an empty tic tac toe board."""
    marks = marks or {}
    return [
        FakeRow(
            *[
                FakeButton(
                    f"ttt_{row}_{col}_{player_id}",
                    marks.get((row, col), "\u200b"),
                )
                for col in range(3)
            ]
        )
        for row in range(3)
    ]


def pressed(custom_id: str, user_id: int = 1, **data) -> FakeInteraction:
    interaction = FakeInteraction(FakeUser(user_id))
    interaction.data = {"custom_id": custom_id, **data}
    return interaction


def description(interaction: FakeInteraction) -> str:
    embed, _ = interaction.sent[0]
    return embed.description


# -------------------------------------------------------------- dispatcher


async def test_an_interaction_with_no_custom_id_is_ignored():
    interaction = FakeInteraction()
    interaction.data = None

    await ComponentsListener.on_interaction(interaction)

    assert interaction.sent == []
    assert interaction.edited == []


async def test_an_unrecognised_component_is_answered_rather_than_dropped():
    """An unanswered interaction is one the user watches spin and then fail."""
    interaction = pressed("something_else")

    await ComponentsListener.on_interaction(interaction)

    assert "Something went wrong" in description(interaction)


async def test_a_button_that_is_not_a_known_game_is_still_answered():
    interaction = pressed("ttt_not_a_move")

    await ComponentsListener.on_interaction(interaction)

    assert interaction.sent or interaction.edited or interaction.deferred


# -------------------------------------------------------------------- laptop


async def test_the_laptop_button_opens_the_command_prompt():
    interaction = pressed("laptop:1")

    await ComponentsListener.on_interaction(interaction)

    assert len(interaction.modals) == 1
    assert interaction.modals[0].custom_id == "laptop_cmd_input:1"


async def test_someone_elses_laptop_button_is_refused():
    interaction = pressed("laptop:2", user_id=1)

    await ComponentsListener.on_interaction(interaction)

    assert interaction.modals == []
    assert "someone else's PC" in description(interaction)


# ---------------------------------------------------------------------- rps


async def test_an_rps_button_plays_the_throw_and_clears_the_buttons():
    interaction = pressed("rps_rock")

    await ComponentsListener.on_interaction(interaction)

    assert len(interaction.edited) == 1
    assert interaction.edited[0].title in RPS_TITLES


# ---------------------------------------------------------------------- ttt


async def test_a_ttt_click_without_a_message_is_deferred():
    interaction = pressed("ttt_0_0_1")
    interaction.message = None

    await ComponentsListener.on_interaction(interaction)

    assert interaction.deferred is True
    assert interaction.edited == []


async def test_a_ttt_click_by_someone_else_is_refused():
    interaction = pressed("ttt_0_0_2", user_id=1)
    interaction.message = SimpleNamespace(components=board_rows(2))

    await ComponentsListener.on_interaction(interaction)

    assert "someone else's game" in description(interaction)
    assert interaction.edited == []


async def test_a_ttt_move_is_played_and_the_board_is_drawn_back():
    interaction = pressed("ttt_1_1_1")
    interaction.message = SimpleNamespace(components=board_rows(1))

    await ComponentsListener.on_interaction(interaction)

    assert len(interaction.edited) == 1
    assert interaction.edited[0].title == "Tic Tac Toe"


async def test_a_ttt_click_on_an_occupied_cell_does_nothing():
    """Tapping a cell that already has a mark should not spend a move."""
    interaction = pressed("ttt_0_0_1")
    interaction.message = SimpleNamespace(components=board_rows(1, {(0, 0): "X"}))

    await ComponentsListener.on_interaction(interaction)

    assert interaction.deferred is True
    assert interaction.edited == []


# --------------------------------------------------------------------- help


async def test_the_help_dropdown_swaps_in_the_category_embed():
    interaction = pressed("help_category", values=["economy"])
    interaction.client = bot

    await ComponentsListener.on_interaction(interaction)

    assert interaction.edited[0].title == "Maxis Economy commands:-"


async def test_the_help_dropdown_without_a_value_is_an_error():
    interaction = pressed("help_category")
    interaction.client = bot

    await ComponentsListener.on_interaction(interaction)

    assert "No category" in description(interaction)


async def test_the_help_dropdown_with_a_category_that_does_not_exist_is_an_error():
    interaction = pressed("help_category", values=["utillity"])
    interaction.client = bot

    await ComponentsListener.on_interaction(interaction)

    assert "Invalid category" in description(interaction)
