"""The command tree, how commands are installed, and /help."""

import pytest
from discord import app_commands

from bot.helper import help_category_embed, help_group, help_groups
from bot.main import bot, setup_slash_commands
from tests.conftest import FakeInteraction

CATEGORIES = ["utility", "moderation", "economy", "image"]


@pytest.fixture(scope="module", autouse=True)
def registered():
    import asyncio

    asyncio.run(setup_slash_commands(bot))
    return bot


def top_level():
    return {c.name: c for c in bot.tree.get_commands()}


def groups():
    return [c for c in bot.tree.get_commands() if isinstance(c, app_commands.Group)]


# ------------------------------------------------------------------- shape


def test_the_categories_register_in_the_declared_order():
    assert [g.name for g in groups()] == CATEGORIES


def test_the_commands_live_under_their_category():
    assert "ping" in [c.name for c in top_level()["utility"].commands]
    assert "daily" in [c.name for c in top_level()["economy"].commands]
    assert "ban" in [c.name for c in top_level()["moderation"].commands]
    assert "makecolor" in [c.name for c in top_level()["image"].commands]


def test_help_is_top_level_because_a_group_would_force_slash_help_help():
    """A group is never invocable on its own."""
    assert "help" in top_level()
    assert not isinstance(top_level()["help"], app_commands.Group)


def test_utility_no_longer_owns_help():
    assert "help" not in [c.name for c in top_level()["utility"].commands]


def test_there_are_no_prefix_commands():
    """discord.py's built-in help walks Cog.__cog_commands__, which a GroupCog
    never populates, so it is switched off rather than left half working."""
    assert bot.help_command is None
    assert [c.name for c in bot.commands] == []


# ------------------------------------------------------------ installation


@pytest.mark.parametrize("group", CATEGORIES)
def test_every_category_is_installable_and_usable_everywhere(group):
    cmd = top_level()[group]
    installs, contexts = cmd.allowed_installs, cmd.allowed_contexts

    assert installs and installs.guild and installs.user
    assert (
        contexts and contexts.guild and contexts.dm_channel and contexts.private_channel
    )


@pytest.mark.parametrize("group", CATEGORIES)
def test_children_inherit_rather_than_repeat_the_flags(group):
    for command in top_level()[group].commands:
        assert command.allowed_contexts is None
        assert command.allowed_installs is None


def test_help_gets_the_same_treatment_as_the_categories():
    cmd = top_level()["help"]

    assert cmd.allowed_installs.guild and cmd.allowed_installs.user
    assert cmd.allowed_contexts.dm_channel and cmd.allowed_contexts.private_channel


# ------------------------------------------------------------------- help


def test_help_groups_returns_the_categories_not_help():
    assert [g.name for g in help_groups(bot)] == CATEGORIES


@pytest.mark.parametrize("name", CATEGORIES)
def test_a_category_lookup_finds_its_group(name):
    found = help_group(bot, name)

    assert found is not None
    assert found.name == name


@pytest.mark.parametrize("junk", ["nope", "", "  "])
def test_an_unknown_category_is_not_found(junk):
    assert help_group(bot, junk) is None


@pytest.mark.parametrize("typed", ["economy", "ECONOMY", "  Economy  "])
def test_a_category_lookup_tolerates_case_and_spaces(typed):
    assert help_group(bot, typed).name == "economy"


@pytest.mark.parametrize("name", CATEGORIES)
def test_each_category_embed_lists_its_commands(name):
    embed = help_category_embed(help_group(bot, name))

    assert embed.title == f"Maxis {name.title()} commands:-"
    assert embed.fields
    assert all(f.inline for f in embed.fields)
    assert all(f.value for f in embed.fields)


def test_a_signature_shows_the_qualified_name_and_its_parameters():
    embed = help_category_embed(help_group(bot, "economy"))

    assert embed.fields[0].name == "/economy balance (user)"


async def ask_help(*args) -> FakeInteraction:
    """Run /help the way discord.py would, and hand back what it replied with."""
    interaction = FakeInteraction()
    interaction.client = bot
    await top_level()["help"].callback(interaction, *args)
    return interaction


async def test_help_with_no_argument_shows_the_index():
    interaction = await ask_help()

    embed, _ = interaction.sent[0]
    assert embed.title == "Maxis help docs"
    assert len(
        [line for line in embed.description.splitlines() if "```" in line]
    ) == len(CATEGORIES)


async def test_the_index_does_not_repeat_the_category_name():
    """The old shape read `economy help economy`, three times over."""
    interaction = await ask_help()

    for line in interaction.sent[0][0].description.splitlines():
        if "/help " not in line:
            continue
        name = line.split("/help ")[1].split()[0].strip("`")
        assert line.count(name) == 1, line


async def test_the_index_offers_the_dropdown():
    _, view = (await ask_help()).sent[0]

    assert view is not None
    assert view.children[0].custom_id == "help_category"
    assert [option.value for option in view.children[0].options] == CATEGORIES


@pytest.mark.parametrize("name", CATEGORIES)
async def test_help_with_a_category_shows_that_category(name):
    interaction = await ask_help(name)

    assert interaction.sent[0][0].title == f"Maxis {name.title()} commands:-"


@pytest.mark.parametrize("junk", ["nonsense", "utillity"])
async def test_help_with_a_bad_category_falls_back_to_the_index(junk):
    interaction = await ask_help(junk)

    assert interaction.sent[0][0].title == "Maxis help docs"


def test_help_takes_one_optional_category():
    parameters = top_level()["help"].parameters

    assert [p.name for p in parameters] == ["category"]
    assert parameters[0].required is False
