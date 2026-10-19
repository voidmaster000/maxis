"""The events the bot hangs off Discord, and the status page.

on_message and on_interaction are the front door for everything that is not a
slash command, and the status page is the only thing the web server serves.
Neither was covered before, so the dispatch itself was untested.
"""

from types import SimpleNamespace

import discord
import pytest

import bot.main as main
from bot import global_state
from tests.conftest import FakeUser


class FakeMessage:
    """Enough of a discord.Message for on_message."""

    def __init__(self, content: str, author=None, mentions=None) -> None:
        self.content = content
        self.author = author or FakeUser(1, "someone")
        self.mentions = mentions or []
        self.replies: list = []

        message = self

        class _Channel:
            async def send(_self, content=None, *, embed=None, **kwargs):
                message.replies.append(embed if embed is not None else content)

        self.channel = _Channel()


@pytest.fixture(autouse=True)
def fake_bot_user(monkeypatch):
    """on_message compares mentions against the bot's own id.

    main.bot is swapped rather than patched in place because a real Client
    keeps its user inside connection state that this bot has never filled in.
    """
    monkeypatch.setattr(main, "bot", SimpleNamespace(user=FakeUser(99, "Maxis")))


# ----------------------------------------------------------------- on_message


async def test_a_message_from_a_bot_is_ignored():
    author = FakeUser(2, "other")
    author.bot = True
    message = FakeMessage("hi", author=author)

    await main.on_message(message)

    assert message.replies == []


async def test_a_custom_reply_is_sent_when_the_text_matches():
    global_state.custom_replies = {"hello": "hi there!"}
    message = FakeMessage("well hello everyone")

    await main.on_message(message)

    assert message.replies == ["hi there!"]


async def test_a_custom_reply_only_fires_once_per_message():
    """The loop breaks on the first match rather than sending every one."""
    global_state.custom_replies = {"a": "first", "b": "second"}
    message = FakeMessage("a and b")

    await main.on_message(message)

    assert message.replies == ["first"]


async def test_a_mention_is_answered_with_the_slash_command_hint():
    message = FakeMessage("hey", mentions=[FakeUser(99, "Maxis")])

    await main.on_message(message)

    assert message.replies[0].description.startswith("I use slash commands!")


async def test_a_mention_of_somebody_else_is_left_alone():
    message = FakeMessage("hey", mentions=[FakeUser(5, "someone")])

    await main.on_message(message)

    assert message.replies == []


# ------------------------------------------------------------- on_interaction


class RecordingComponents:
    calls: list = []

    @staticmethod
    async def on_interaction(interaction):
        RecordingComponents.calls.append(("component", interaction))


class RecordingModals:
    @staticmethod
    async def on_modal_submit(interaction):
        RecordingComponents.calls.append(("modal", interaction))


@pytest.fixture(autouse=True)
def quiet_listeners(monkeypatch):
    RecordingComponents.calls = []
    monkeypatch.setattr(main, "ComponentsListener", RecordingComponents)
    monkeypatch.setattr(main, "ModalsListener", RecordingModals)


async def test_a_button_press_goes_to_the_component_listener():
    interaction = SimpleNamespace(type=discord.InteractionType.component)

    await main.on_interaction(interaction)

    assert RecordingComponents.calls == [("component", interaction)]


async def test_a_modal_submission_goes_to_the_modal_listener():
    interaction = SimpleNamespace(type=discord.InteractionType.modal_submit)

    await main.on_interaction(interaction)

    assert RecordingComponents.calls == [("modal", interaction)]


async def test_an_interaction_of_any_other_type_is_left_alone():
    """Application commands arrive here too, and discord.py already routes them."""
    interaction = SimpleNamespace(type=discord.InteractionType.application_command)

    await main.on_interaction(interaction)

    assert RecordingComponents.calls == []


# ---------------------------------------------------------------- status page


async def test_the_status_page_reports_offline_with_the_version(monkeypatch):
    monkeypatch.setattr(main, "bot", SimpleNamespace(is_ready=lambda: False, guilds=[]))

    response = await main.status_page(SimpleNamespace())

    body = response.body.decode()
    assert "Online - 0 servers" in body
    assert global_state.VERSION in body
    # Jinja escapes the ampersands in the invite URL, so check a part of it.
    assert "client_id=891518158790361138" in body


async def test_the_status_page_counts_the_guilds_once_it_is_ready(monkeypatch):
    monkeypatch.setattr(
        main, "bot", SimpleNamespace(is_ready=lambda: True, guilds=[1, 2, 3])
    )

    response = await main.status_page(SimpleNamespace())

    assert "Online - 3 servers" in response.body.decode()
