"""The economy: money must be conserved, and cooldowns must actually gate."""

from datetime import UTC
from types import SimpleNamespace

import discord
import pytest

from bot import database_sync, global_state
from bot.commands.economy_commands import Economy, _split_duration
from bot.objects.shop import Shop
from tests.conftest import FakeInteraction, FakeUser

COGS = {"balance": 500, "work": 500, "daily": 5000, "weekly": 10000, "monthly": 50000}


@pytest.fixture
def economy():
    return Economy()


@pytest.fixture(autouse=True)
def quiet_saves(monkeypatch):
    for name in (
        "save_balances",
        "save_robs",
        "save_dailies",
        "save_weeklies",
        "save_monthlies",
        "save_works",
        "save_inventory",
        "save_replies",
        "save_warns",
        "save_laptop_history",
        "save_user_settings",
    ):
        monkeypatch.setattr(database_sync, name, lambda: None)
    global_state.user_settings_map = {}


def total() -> int:
    return sum(global_state.balance_map.values())


# --------------------------------------------------------------------- rob


@pytest.mark.asyncio
async def test_rob_moves_money_from_the_target_to_the_caller(economy):
    """Regression: this once credited the target too, so a robbery moved
    nothing at all while reporting success."""
    robber, victim = FakeUser(1, "Robber"), FakeUser(2, "Victim")
    global_state.balance_map = {1: 500, 2: 1_000_000}
    global_state.user_robbed_times = {}
    before = total()

    await economy.rob.callback(economy, FakeInteraction(robber), victim)

    taken = 1_000_000 - global_state.balance_map[2]
    gained = global_state.balance_map[1] - 500
    assert taken > 0
    assert gained == taken
    assert total() == before


@pytest.mark.asyncio
async def test_rob_sets_a_cooldown_that_blocks_a_second_attempt(economy):
    robber, victim = FakeUser(1), FakeUser(2)
    global_state.balance_map = {1: 500, 2: 1_000_000}
    global_state.user_robbed_times = {}
    await economy.rob.callback(economy, FakeInteraction(robber), victim)
    snapshot = dict(global_state.balance_map)

    await economy.rob.callback(economy, FakeInteraction(robber), victim)

    assert global_state.balance_map == snapshot


@pytest.mark.asyncio
async def test_rob_will_not_take_from_someone_broke(economy):
    robber, victim = FakeUser(1), FakeUser(2)
    global_state.balance_map = {1: 500, 2: 10}
    global_state.user_robbed_times = {}
    before = total()

    await economy.rob.callback(economy, FakeInteraction(robber), victim)

    assert total() == before


@pytest.mark.asyncio
async def test_passive_mode_stops_a_rob(economy):
    from bot.objects.user_settings import UserSettings

    robber, victim = FakeUser(1), FakeUser(2)
    global_state.balance_map = {1: 500, 2: 1_000_000}
    global_state.user_robbed_times = {}
    global_state.user_settings_map = {1: UserSettings(bank_passive_enabled=True)}

    await economy.rob.callback(economy, FakeInteraction(robber), victim)

    assert global_state.balance_map[2] == 1_000_000


# -------------------------------------------------------------------- give


@pytest.mark.asyncio
async def test_give_moves_money_from_the_caller_to_the_target(economy):
    giver, receiver = FakeUser(3), FakeUser(4)
    global_state.balance_map = {3: 10_000, 4: 0}
    before = total()

    await economy.give.callback(economy, FakeInteraction(giver), receiver, 2500)

    assert global_state.balance_map[3] == 7500
    assert global_state.balance_map[4] == 2500
    assert total() == before


@pytest.mark.asyncio
async def test_give_refuses_to_overdraw(economy):
    giver, receiver = FakeUser(3), FakeUser(4)
    global_state.balance_map = {3: 100, 4: 0}

    await economy.give.callback(economy, FakeInteraction(giver), receiver, 100_000)

    assert global_state.balance_map == {3: 100, 4: 0}


@pytest.mark.asyncio
async def test_give_refuses_a_negative_amount(economy):
    giver, receiver = FakeUser(3), FakeUser(4)
    global_state.balance_map = {3: 100, 4: 0}

    await economy.give.callback(economy, FakeInteraction(giver), receiver, -50)

    assert global_state.balance_map == {3: 100, 4: 0}


# ---------------------------------------------------------- reward commands


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("command", "times", "amount"),
    [
        ("daily", "user_daily_times", 5000),
        ("weekly", "user_weekly_times", 10000),
        ("monthly", "user_monthly_times", 50000),
    ],
)
async def test_a_reward_pays_once_and_then_goes_on_cooldown(
    economy, command, times, amount
):
    user = FakeUser(10)
    global_state.balance_map = {10: 0}
    setattr(global_state, times, {})
    callback = getattr(economy, command).callback

    await callback(economy, FakeInteraction(user))
    assert global_state.balance_map[10] == amount

    await callback(economy, FakeInteraction(user))
    assert global_state.balance_map[10] == amount


@pytest.mark.asyncio
async def test_a_reward_pays_again_once_the_cooldown_lapses(economy):
    from datetime import datetime, timedelta

    user = FakeUser(10)
    global_state.balance_map = {10: 0}
    global_state.user_daily_times = {
        10: datetime.now(UTC) - timedelta(seconds=global_state.DAILY_COOLDOWN + 1)
    }

    await economy.daily.callback(economy, FakeInteraction(user))

    assert global_state.balance_map[10] == 5000


@pytest.mark.asyncio
async def test_work_pays_a_random_amount_and_then_cools_down(economy):
    user = FakeUser(11)
    global_state.balance_map = {11: 0}
    global_state.user_worked_times = {}

    await economy.work.callback(economy, FakeInteraction(user))
    first = global_state.balance_map[11]

    await economy.work.callback(economy, FakeInteraction(user))

    assert 100 <= first <= 500
    assert global_state.balance_map[11] == first


# ------------------------------------------------------------- durations


@pytest.mark.parametrize(
    ("seconds", "parts"),
    [
        (0, (0, 0, 0, 0)),
        (59, (0, 0, 0, 59)),
        (60, (0, 0, 1, 0)),
        (3661, (0, 1, 1, 1)),
        (86399, (0, 23, 59, 59)),
        (86400, (1, 0, 0, 0)),
        (90061, (1, 1, 1, 1)),
        (604800, (7, 0, 0, 0)),
    ],
)
def test_durations_split_into_days_hours_minutes_seconds(seconds, parts):
    assert _split_duration(seconds) == parts


# -------------------------------------------------------------- shop lookups


@pytest.mark.parametrize("item", Shop.items, ids=[i.name for i in Shop.items])
def test_every_item_is_reachable_by_its_command(item):
    """`/economy use <command>` names the item by its command slug."""
    assert Shop.find(item.command) is item
    assert Shop.find(item.command.upper()) is item
    assert Shop.find(f"  {item.command}  ") is item
    assert Shop.by_name(item.name) is item


def test_an_unknown_item_is_not_found():
    assert Shop.find("nonexistent") is None
    assert Shop.by_name("nonexistent") is None


def test_find_and_by_name_do_not_overlap():
    """The two lookups key on different strings, so a slug is never a name."""
    assert all(
        item.command != other.name for item in Shop.items for other in Shop.items
    )


def test_the_choice_list_matches_the_catalogue():
    assert [(c.name, c.value) for c in Shop.choices()] == [
        (i.name, i.command) for i in Shop.items
    ]


def test_amount_owned_defaults_to_zero():
    global_state.inventory = {7: {"Juice": 2}}

    assert Shop.amount_owned(7, "Juice") == 2
    assert Shop.amount_owned(7, "Nitro") == 0
    assert Shop.amount_owned(99, "Juice") == 0


@pytest.mark.asyncio
async def test_buying_uses_the_item_its_effect_before_returning(economy):
    """The effect used to run in a fire-and-forget task the event loop could
    collect mid-flight, so the message arrived but nothing happened."""
    from datetime import datetime

    nitro = next(i for i in Shop.items if i.name == "Nitro")
    global_state.inventory = {12: {"Nitro": 1}}
    global_state.balance_map = {12: 5000}
    global_state.user_worked_times = {12: datetime.now(UTC)}
    global_state.user_daily_times = {}

    await nitro.use_item(FakeInteraction(FakeUser(12)))

    left = (
        global_state.BASIC_COOLDOWN
        - (datetime.now(UTC) - global_state.user_worked_times[12]).total_seconds()
    )
    assert left <= 1, f"{left:.1f}s still on cooldown"
    assert global_state.inventory[12]["Nitro"] == 0


# ------------------------------------------------------------- leaderboards
#
# The two leaderboards shared a copy of the same ranking. These pin the
# behaviour on both sides of the split, since that is what the shared helper
# has to keep agreeing with.


class FakeGuild:
    """The two attributes /economy leaderboard reads."""

    def __init__(self, name: str = "Server", members=None) -> None:
        self.name = name
        self.members = members or []


class FakeClient:
    """fetch_user, with the ids it is supposed to be unable to resolve."""

    def __init__(self, known: dict[int, FakeUser], missing=()) -> None:
        self.known = known
        self.missing = set(missing)

    async def fetch_user(self, user_id: int):
        if user_id in self.missing:
            raise discord.NotFound(
                SimpleNamespace(status=404, reason="Not Found"), "unknown user"
            )
        return self.known[user_id]


def server_interaction(interaction: FakeInteraction, members) -> FakeInteraction:
    interaction.guild = FakeGuild("Server", members)
    return interaction


@pytest.mark.asyncio
async def test_leaderboard_ranks_the_server_and_stops_at_five(economy):
    members = [FakeUser(user_id, f"user{user_id}") for user_id in range(1, 8)]
    global_state.balance_map = {user_id: user_id * 100 for user_id in range(1, 8)}
    interaction = server_interaction(FakeInteraction(FakeUser(1)), members)

    await economy.leaderboard.callback(economy, interaction)

    embed, _ = interaction.sent[0]
    assert embed.title == "Top 5 richest user(s) in Server:-"
    lines = embed.description.splitlines()
    assert len(lines) == 5
    assert lines[0].startswith("1) user7 (")
    assert lines[-1].startswith("5) user3 (")


@pytest.mark.asyncio
async def test_leaderboard_leaves_out_bots_and_non_members(economy):
    """Only people in this server who have an account here can be ranked."""
    robot = FakeUser(2, "robot")
    robot.bot = True
    members = [FakeUser(1, "member"), robot, FakeUser(3, "stranger")]
    # 3 is in the server but has never been paid; 4 has an account elsewhere
    global_state.balance_map = {1: 50, 2: 900, 4: 900}
    interaction = server_interaction(FakeInteraction(FakeUser(1)), members)

    await economy.leaderboard.callback(economy, interaction)

    embed, _ = interaction.sent[0]
    assert embed.title == "Top 1 richest user(s) in Server:-"
    assert "member" in embed.description
    assert "robot" not in embed.description
    assert "stranger" not in embed.description


@pytest.mark.asyncio
async def test_leaderboard_says_so_when_nobody_has_an_account(economy):
    interaction = server_interaction(FakeInteraction(FakeUser(1)), [FakeUser(1)])

    await economy.leaderboard.callback(economy, interaction)

    embed, _ = interaction.sent[0]
    assert embed.title == "No one has more than :coin: 0 in this server!"
    assert embed.description is None


@pytest.mark.asyncio
async def test_leaderboard_is_for_servers_only(economy):
    interaction = FakeInteraction(FakeUser(1), guild=False)

    await economy.leaderboard.callback(economy, interaction)

    embed, _ = interaction.sent[0]
    assert "only works in servers" in embed.description


@pytest.mark.asyncio
async def test_global_leaderboard_spans_the_whole_database(economy):
    global_state.balance_map = {1: 10, 2: 900, 3: 500}
    interaction = FakeInteraction(FakeUser(1))
    interaction.client = FakeClient(
        {1: FakeUser(1), 2: FakeUser(2, "rich"), 3: FakeUser(3)}
    )

    await economy.global_leaderboard.callback(economy, interaction)

    embed = interaction.followups[0]
    assert embed.title == "Top 3 richest user(s) of Maxis:-"
    assert embed.description.splitlines()[0] == "1) rich (:coin: 900)"


@pytest.mark.asyncio
async def test_global_leaderboard_skips_accounts_discord_will_not_return(economy):
    """A closed account stays in balance_map, and must not break the ranking."""
    global_state.balance_map = {1: 10, 2: 900}
    interaction = FakeInteraction(FakeUser(1))
    interaction.client = FakeClient({1: FakeUser(1)}, missing={2})

    await economy.global_leaderboard.callback(economy, interaction)

    embed = interaction.followups[0]
    assert embed.title == "Top 1 richest user(s) of Maxis:-"


@pytest.mark.asyncio
async def test_global_leaderboard_says_so_when_the_database_is_empty(economy):
    interaction = FakeInteraction(FakeUser(1))
    interaction.client = FakeClient({})

    await economy.global_leaderboard.callback(economy, interaction)

    embed = interaction.followups[0]
    assert embed.title == "No one has more than :coin: 0 in our database!"
