"""The utility commands: argument handling, state changes, and what they refuse.

The info commands (botinfo / userinfo / serverinfo) are not here. Driving them
means reimplementing large parts of Discord's Guild and Member surface, which
tests discord.py's own attribute plumbing more than this bot's decisions. What
is here is where the command actually decides something: validating input,
touching persisted state, or writing a file.
"""

from types import SimpleNamespace

import pytest

from bot import database_sync, global_state
from bot.commands.utility_commands import CURRENCY_CHOICES, Utility
from bot.objects.user_settings import UserSettings
from tests.conftest import FakeInteraction, FakeUser


@pytest.fixture(autouse=True)
def quiet_saves(monkeypatch):
    for name in (
        "save_replies",
        "save_user_settings",
        "save_balances",
        "save_inventory",
        "save_laptop_history",
    ):
        monkeypatch.setattr(database_sync, name, lambda: None)


@pytest.fixture
def utility():
    return Utility()


def description(interaction: FakeInteraction) -> str:
    embed, _ = interaction.sent[0]
    return embed.description


def fields(interaction: FakeInteraction) -> dict[str, str]:
    embed, _ = interaction.sent[0]
    return {field.name: field.value for field in embed.fields}


# ----------------------------------------------------------- simple replies


async def test_ping_reports_the_gateway_latency(utility):
    interaction = FakeInteraction()
    interaction.client = SimpleNamespace(latency=0.123)

    await utility.ping.callback(utility, interaction)

    assert description(interaction) == "Latency is 123 ms."


async def test_hello_uses_the_requesting_users_name(utility):
    interaction = FakeInteraction(FakeUser(1, "Arpan"))

    await utility.hello.callback(utility, interaction)

    assert "Arpan" in description(interaction)


# ----------------------------------------------------------------- datetime


async def test_datetime_reports_local_and_utc(utility):
    interaction = FakeInteraction()

    await utility.datetime_cmd.callback(utility, interaction)

    assert set(fields(interaction)) == {"Local Time", "UTC/GMT"}


async def test_datetime_adds_the_requested_timezone(utility):
    interaction = FakeInteraction()

    await utility.datetime_cmd.callback(utility, interaction, "Asia/Kolkata")

    assert "Asia/Kolkata" in fields(interaction)


async def test_an_unknown_timezone_is_refused_rather_than_raising(utility):
    """The value is autocompleted, but it is still just a string."""
    interaction = FakeInteraction()

    await utility.datetime_cmd.callback(utility, interaction, "Not/AZone")

    assert "timezone" in description(interaction).lower()


# --------------------------------------------------------- custom replies


async def test_replies_says_so_when_there_are_none(utility):
    interaction = FakeInteraction()

    await utility.replies.callback(utility, interaction)

    assert "No custom replies" in description(interaction)


async def test_replies_lists_what_is_set(utility):
    global_state.custom_replies = {"hi": "hello there"}
    interaction = FakeInteraction()

    await utility.replies.callback(utility, interaction)

    assert description(interaction) == "hi: hello there"


async def test_setting_a_reply_stores_it(utility):
    interaction = FakeInteraction()

    await utility.set_custom_reply.callback(utility, interaction, "hi", "hello")

    assert global_state.custom_replies == {"hi": "hello"}


async def test_a_reply_needs_both_halves(utility):
    interaction = FakeInteraction()

    await utility.set_custom_reply.callback(utility, interaction, "hi", "")

    assert global_state.custom_replies == {}
    assert "Both text and reply" in description(interaction)


async def test_disabling_a_reply_removes_it(utility):
    global_state.custom_replies = {"hi": "hello"}
    interaction = FakeInteraction()

    await utility.no_reply.callback(utility, interaction, "hi")

    assert global_state.custom_replies == {}


async def test_disabling_a_reply_matches_on_a_substring(utility):
    """The old /utility reply accepted partial text, so removal does too."""
    global_state.custom_replies = {"hello there": "hi"}
    interaction = FakeInteraction()

    await utility.no_reply.callback(utility, interaction, "hello")

    assert global_state.custom_replies == {}


async def test_disabling_something_that_was_never_set_is_an_error(utility):
    interaction = FakeInteraction()

    await utility.no_reply.callback(utility, interaction, "nothing")

    assert "No reply matching" in description(interaction)


# ---------------------------------------------------------------- makefile


async def test_makefile_rejects_a_name_with_no_file_in_it(utility):
    interaction = FakeInteraction()

    await utility.makefile.callback(utility, interaction, "  ", "content")

    assert "valid file name" in description(interaction)


async def test_makefile_rejects_a_path_that_tries_to_walk_out(utility):
    """The file lands in a temp dir, but the download name is the user's."""
    interaction = FakeInteraction()

    await utility.makefile.callback(utility, interaction, "../../etc/passwd", "x")

    assert description(interaction) == "Here's your file `passwd`"
    assert interaction.sent[0][0].title == "Success!"


async def test_makefile_refuses_content_over_the_attachment_limit(utility, monkeypatch):
    monkeypatch.setattr(global_state, "MAX_ATTACHMENT_BYTES", 8)
    interaction = FakeInteraction()

    await utility.makefile.callback(utility, interaction, "note.txt", "nine byte")

    assert "over the" in description(interaction)


async def test_makefile_writes_the_file(utility):
    interaction = FakeInteraction()

    await utility.makefile.callback(utility, interaction, "note.txt", "hello")

    assert "note.txt" in description(interaction)


# --------------------------------------------------------------- calculate


async def test_calculate_solves_an_expression(utility):
    interaction = FakeInteraction()

    await utility.calculate.callback(utility, interaction, "2 + 3 * 4")

    assert "14" in description(interaction)


async def test_calculate_reports_a_bad_expression(utility):
    interaction = FakeInteraction()

    await utility.calculate.callback(utility, interaction, "2 +")

    assert "Failed to calculate" in description(interaction)


# ---------------------------------------------------------------------- rps


async def test_rps_without_a_choice_offers_the_buttons(utility):
    interaction = FakeInteraction()

    await utility.rps.callback(utility, interaction)

    _, view = interaction.sent[0]
    assert view is not None
    assert len(view.children) == 3


async def test_rps_with_a_choice_plays_it_immediately(utility):
    interaction = FakeInteraction()

    await utility.rps.callback(utility, interaction, "rock")

    _, view = interaction.sent[0]
    assert view is None


# ------------------------------------------------------------------ setting


async def test_a_setting_is_created_for_a_user_who_has_none(utility):
    interaction = FakeInteraction(FakeUser(5))

    await utility.change_user_settings.callback(utility, interaction, "bankdm", "false")

    assert global_state.user_settings_map[5].bank_dm_enabled is False


async def test_both_setting_directions_work(utility):
    interaction = FakeInteraction(FakeUser(5))

    await utility.change_user_settings.callback(utility, interaction, "passive", "true")

    assert global_state.user_settings_map[5].bank_passive_enabled is True


async def test_a_value_that_is_not_a_boolean_is_refused(utility):
    interaction = FakeInteraction(FakeUser(5))

    await utility.change_user_settings.callback(utility, interaction, "bankdm", "maybe")

    settings: UserSettings = global_state.user_settings_map[5]
    assert settings.bank_dm_enabled is True, "the default was changed anyway"
    assert "Incorrect arguments" in description(interaction)


async def test_an_unknown_setting_is_refused(utility):
    interaction = FakeInteraction(FakeUser(5))

    await utility.change_user_settings.callback(
        utility, interaction, "nonsense", "true"
    )

    assert "not found" in description(interaction)


# ----------------------------------------------------------------------- dm


class DmTarget(FakeUser):
    def __init__(self, user_id: int) -> None:
        super().__init__(user_id)
        self.received: list = []

    async def send(self, *, embed=None, **kwargs):
        self.received.append(embed)


async def test_dm_sends_the_message(utility):
    target = DmTarget(9)
    interaction = FakeInteraction(FakeUser(1, "Arpan"))
    interaction.guild = SimpleNamespace(name="Server")

    await utility.dm.callback(utility, interaction, target, "hello there")

    assert target.received[0].description == "hello there"


async def test_a_dm_sent_from_a_server_names_the_server(utility):
    target = DmTarget(9)
    interaction = FakeInteraction(FakeUser(1, "Arpan"))
    interaction.guild = SimpleNamespace(name="Server")

    await utility.dm.callback(utility, interaction, target, "hi")

    assert target.received[0].title == "Alert! Message from Arpan at Server :-"


async def test_a_dm_sent_from_a_direct_message_does_not(utility):
    target = DmTarget(9)
    interaction = FakeInteraction(FakeUser(1, "Arpan"), guild=False)

    await utility.dm.callback(utility, interaction, target, "hi")

    assert target.received[0].title == "Alert! Message from Arpan :-"


# ------------------------------------------------------------------ currconv


class FakeRateResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def stub_rate_api(monkeypatch, response=None, *, raises=None):
    """Stand in for the exchangerate-api call the command makes off the loop."""

    def get(url, timeout=None):
        if raises is not None:
            raise raises
        return response

    monkeypatch.setattr("bot.commands.utility_commands.requests.get", get)


CONVERT = (10.0, "USD", "EUR")


def test_currconv_offers_every_supported_currency_as_a_choice():
    """Discord fixes the choice list when the command is defined, so it has to
    agree with the constant users are validated against."""
    assert [choice.value for choice in CURRENCY_CHOICES] == list(
        global_state.CURRENCY_CODES
    )


async def test_currconv_requires_an_unknown_currency_to_be_rejected(utility):
    interaction = FakeInteraction()

    await utility.currency_convert.callback(utility, interaction, 10.0, "XXX", "EUR")

    assert "Invalid currency code" in interaction.followups[0].description


async def test_currconv_needs_an_api_key(utility, monkeypatch):
    monkeypatch.setattr(global_state, "EXAPI", "")
    interaction = FakeInteraction()

    await utility.currency_convert.callback(utility, interaction, *CONVERT)

    assert "not configured" in interaction.followups[0].description


async def test_currconv_reports_the_converted_amount(utility, monkeypatch):
    monkeypatch.setattr(global_state, "EXAPI", "test-key")
    stub_rate_api(
        monkeypatch,
        FakeRateResponse(200, {"result": "success", "conversion_result": 9.25}),
    )
    interaction = FakeInteraction()

    await utility.currency_convert.callback(utility, interaction, *CONVERT)

    assert interaction.followups[0].description == "10.0 USD = 9.25 EUR"


async def test_currconv_reports_an_api_level_error(utility, monkeypatch):
    monkeypatch.setattr(global_state, "EXAPI", "test-key")
    stub_rate_api(monkeypatch, FakeRateResponse(200, {"result": "error"}))
    interaction = FakeInteraction()

    await utility.currency_convert.callback(utility, interaction, *CONVERT)

    assert interaction.followups[0].description == "Conversion failed!"


async def test_currconv_reports_a_bad_status(utility, monkeypatch):
    monkeypatch.setattr(global_state, "EXAPI", "test-key")
    stub_rate_api(monkeypatch, FakeRateResponse(500))
    interaction = FakeInteraction()

    await utility.currency_convert.callback(utility, interaction, *CONVERT)

    assert "Failed to connect" in interaction.followups[0].description


async def test_currconv_reports_a_network_failure(utility, monkeypatch, caplog):
    """The failure is reported to the user and logged, not swallowed."""
    import logging

    monkeypatch.setattr(global_state, "EXAPI", "test-key")
    stub_rate_api(monkeypatch, raises=ConnectionError("no route to host"))
    interaction = FakeInteraction()

    with caplog.at_level(logging.ERROR, logger="bot.commands.utility_commands"):
        await utility.currency_convert.callback(utility, interaction, *CONVERT)

    assert "Please try again" in interaction.followups[0].description
    assert "Error in currency conversion" in caplog.text


# ---------------------------------------------------------------------- ttt


async def test_ttt_defers_and_offers_a_board(utility):
    interaction = FakeInteraction()

    await utility.ttt.callback(utility, interaction)

    assert interaction.deferred is True
    assert interaction.followup_views[0] is not None
    assert len(interaction.followup_views[0].children) == 9
