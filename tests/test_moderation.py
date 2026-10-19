"""Moderation: who is allowed to run these, and what happens when they run.

`require_moderator` stands in front of every destructive command in the category
and was the least-covered code in the bot, so the three ways through it are
pinned individually here. The commands behind it are then pinned for both
outcomes: Discord doing the thing, and Discord refusing because the bot lacks
the standing to do it.
"""

from types import SimpleNamespace

import discord
import pytest

from bot.commands.moderation_commands import Moderation, require_moderator
from bot.core import database_sync, global_state
from bot.objects.warn import Warn
from tests.conftest import FakeInteraction, FakeUser


class FakeGuild:
    """The guild attributes the mod commands actually read."""

    def __init__(self, guild_id: int = 1, name: str = "Server") -> None:
        self.id = guild_id
        self.name = name


class FakeMember(FakeUser):
    """A user that satisfies require_moderator's isinstance check.

    That check is how the code tells a guild interaction (a Member) from a DM
    one (a User). Constructing a real discord.Member means standing up a fake
    gateway state and reimplementing the library's own role-override
    resolution, which would be testing discord.py rather than this bot, so the
    stand-in is registered under that name for the duration of the test.
    """

    def __init__(self, user_id: int, *, administrator: bool) -> None:
        super().__init__(user_id)
        self.guild_permissions = discord.Permissions(administrator=administrator)


class WarnedUser(FakeUser):
    """A user who can be DMed a warning."""

    def __init__(self, user_id: int, name: str = "user") -> None:
        super().__init__(user_id, name)
        self.dms: list = []

    async def send(self, *, embed=None, **kwargs):
        self.dms.append(embed)


@pytest.fixture(autouse=True)
def fake_members(monkeypatch):
    monkeypatch.setattr(discord, "Member", FakeMember)


@pytest.fixture(autouse=True)
def quiet_saves(monkeypatch):
    monkeypatch.setattr(database_sync, "save_warns", lambda: None)


@pytest.fixture
def moderation():
    return Moderation()


def admin_interaction(user_id: int = 3) -> FakeInteraction:
    interaction = FakeInteraction(FakeMember(user_id, administrator=True))
    interaction.guild = FakeGuild()
    return interaction


def description(interaction: FakeInteraction) -> str:
    embed, _ = interaction.sent[0]
    return embed.description


# ----------------------------------------------------------------- the gate


async def test_a_dm_interaction_is_refused():
    """A User rather than a Member: mod commands are meaningless outside one."""
    interaction = FakeInteraction(FakeUser(1), guild=False)
    assert await require_moderator(interaction) is None
    assert "servers" in description(interaction)


async def test_a_member_without_admin_is_refused():
    interaction = FakeInteraction(FakeMember(2, administrator=False))
    assert await require_moderator(interaction) is None
    assert "admin" in description(interaction)


async def test_an_admin_is_allowed():
    interaction = admin_interaction()
    assert await require_moderator(interaction) is interaction.guild
    assert interaction.sent == []


# --------------------------------------------------------------- commands


async def test_a_non_admin_cannot_warn_anyone(moderation):
    interaction = FakeInteraction(FakeMember(2, administrator=False))
    await moderation.warn.callback(moderation, interaction, WarnedUser(9), "spam")
    assert global_state.warn_map == {}


async def test_an_admin_warning_records_it_and_reports_the_count(moderation):
    interaction = admin_interaction()
    target = WarnedUser(9)

    await moderation.warn.callback(moderation, interaction, target, "spam")

    assert global_state.warn_map[1][9].warns == 1
    assert "1 warn(s)" in description(interaction)
    assert len(target.dms) == 1


async def test_a_second_warning_accumulates(moderation):
    interaction = admin_interaction()
    target = WarnedUser(9)

    await moderation.warn.callback(moderation, interaction, target, "spam")
    await moderation.warn.callback(moderation, interaction, target, "again")

    assert global_state.warn_map[1][9].warns == 2
    assert global_state.warn_map[1][9].warn_causes == ["spam", "again"]


# ------------------------------------------------------- moderation actions
#
# Everything in this group is the same shape: ask Discord to do something, then
# report either that it worked or that the bot lacks the standing to do it. The
# second half is the one users see, so both are pinned.


class FakeActionGuild(FakeGuild):
    """A guild that can be asked to act, and can refuse."""

    def __init__(self, *, refuses: bool = False) -> None:
        super().__init__()
        self.refuses = refuses
        self.calls: list[tuple[str, object, object]] = []

    async def _act(self, what: str, user, reason=None):
        self.calls.append((what, user, reason))
        if self.refuses:
            raise discord.Forbidden(
                SimpleNamespace(status=403, reason="Forbidden"), "no permission"
            )

    async def kick(self, user, reason=None):
        await self._act("kick", user, reason)

    async def ban(self, user, reason=None):
        await self._act("ban", user, reason)

    async def unban(self, user, reason=None):
        await self._act("unban", user, reason)


class MutableTarget(FakeUser):
    """A member that can be muted and unmuted."""

    def __init__(self, user_id: int, *, refuses: bool = False) -> None:
        super().__init__(user_id)
        self.refuses = refuses
        self.edits: list[dict] = []

    async def edit(self, **kwargs):
        self.edits.append(kwargs)
        if self.refuses:
            raise discord.Forbidden(
                SimpleNamespace(status=403, reason="Forbidden"), "no permission"
            )


def action_interaction(refuses: bool = False) -> FakeInteraction:
    interaction = admin_interaction()
    interaction.guild = FakeActionGuild(refuses=refuses)
    return interaction


async def test_kick_asks_the_guild_and_reports_success(moderation):
    interaction = action_interaction()
    target = FakeUser(9)

    await moderation.kick.callback(moderation, interaction, target, "spamming")

    assert interaction.guild.calls == [("kick", target, "spamming")]
    assert "Successfully kicked" in description(interaction)


async def test_a_kick_the_bot_cannot_do_is_reported_not_raised(moderation):
    interaction = action_interaction(refuses=True)

    await moderation.kick.callback(moderation, interaction, FakeUser(9))

    assert "I can't kick that user" in description(interaction)


async def test_ban_passes_the_reason_through(moderation):
    interaction = action_interaction()
    target = FakeUser(9)

    await moderation.ban.callback(moderation, interaction, target, "raiding")

    assert interaction.guild.calls == [("ban", target, "raiding")]
    assert "Reason: raiding" in description(interaction)


async def test_a_ban_without_a_reason_says_nothing_about_one(moderation):
    interaction = action_interaction()

    await moderation.ban.callback(moderation, interaction, FakeUser(9))

    assert "Reason" not in description(interaction)


async def test_a_ban_the_bot_cannot_do_is_reported(moderation):
    interaction = action_interaction(refuses=True)

    await moderation.ban.callback(moderation, interaction, FakeUser(9))

    assert "I can't ban that user" in description(interaction)


async def test_unban_asks_the_guild(moderation):
    interaction = action_interaction()

    await moderation.unban.callback(moderation, interaction, FakeUser(9))

    assert interaction.guild.calls[0][0] == "unban"
    assert "Successfully unbanned" in description(interaction)


async def test_mute_and_unmute_toggle_chat_and_voice(moderation):
    """Mute covers voice as well as chat, so it sets both flags."""
    muted = MutableTarget(9)
    interaction = action_interaction()

    await moderation.mute.callback(moderation, interaction, muted)
    await moderation.unmute.callback(moderation, interaction, muted)

    assert muted.edits == [
        {"mute": True, "deafen": True},
        {"mute": False, "deafen": False},
    ]


async def test_a_mute_the_bot_cannot_do_is_reported(moderation):
    interaction = action_interaction()

    await moderation.mute.callback(
        moderation, interaction, MutableTarget(9, refuses=True)
    )

    assert "I can't mute that user" in description(interaction)


# ----------------------------------------------------------- warn management


async def test_clearing_warns_removes_them(moderation):
    global_state.warn_map = {1: {9: Warn("spam", 9)}}
    interaction = admin_interaction()

    await moderation.clear_warn.callback(moderation, interaction, FakeUser(9))

    assert global_state.warn_map[1] == {}
    assert "Successfully removed all warnings" in description(interaction)


async def test_clearing_warns_that_were_never_set_says_so(moderation):
    interaction = admin_interaction()

    await moderation.clear_warn.callback(moderation, interaction, FakeUser(9))

    assert "No warns were found" in description(interaction)


async def test_getting_warns_lists_the_causes(moderation):
    global_state.warn_map = {1: {9: Warn("spam", 9)}}
    global_state.warn_map[1][9].new_warn("again")
    interaction = admin_interaction()

    await moderation.get_warns.callback(moderation, interaction, FakeUser(9))

    assert description(interaction) == "spam\nagain"


async def test_getting_warns_for_a_clean_user_says_so(moderation):
    interaction = admin_interaction()

    await moderation.get_warns.callback(moderation, interaction, FakeUser(9))

    assert "No warns were found" in description(interaction)


# ------------------------------------------ commands that need a real channel
#
# clear and nuke both narrow to discord.TextChannel, which cannot be built
# without standing up gateway state. What is testable is the refusal, and that
# is the half that tells a user why nothing happened.


async def test_clear_refuses_outside_a_text_channel(moderation):
    interaction = admin_interaction()
    interaction.channel = None

    await moderation.clear_messages.callback(moderation, interaction, 5)

    assert "only works in servers" in description(interaction)


async def test_nuke_refuses_outside_a_text_channel(moderation):
    interaction = admin_interaction()
    interaction.channel = None

    await moderation.nuke.callback(moderation, interaction)

    assert "only works in text channels" in description(interaction)
