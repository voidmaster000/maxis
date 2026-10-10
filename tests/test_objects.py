"""The objects in bot/objects: the games, the calculator, the laptop, nitro."""

import itertools
from datetime import UTC, datetime, timedelta
from io import BytesIO

import pytest
from PIL import Image as PILImage
from PIL import ImageDraw

from bot import database_sync, global_state
from bot.objects.calculator import Calculator
from bot.objects.hacker_laptop import HackerLaptop, LaptopHistory
from bot.objects.nitro import NitroBoost
from bot.objects.rps import RpsGame, RpsResult
from bot.objects.tictactoe import TicTacToe

EMPTY = [["" for _ in range(3)] for _ in range(3)]


def board(*rows):
    return [list(r) for r in rows]


# ============================================================ tic tac toe

WINNING_LINES = (
    ((0, 0), (0, 1), (0, 2)),
    ((1, 0), (1, 1), (1, 2)),
    ((2, 0), (2, 1), (2, 2)),
    ((0, 0), (1, 0), (2, 0)),
    ((0, 1), (1, 1), (2, 1)),
    ((0, 2), (1, 2), (2, 2)),
    ((0, 0), (1, 1), (2, 2)),
    ((0, 2), (1, 1), (2, 0)),
)


def marks_with_a_line(b):
    """Which marks, if any, hold a complete line. Read straight off the board,
    so it is an independent check rather than a restatement of _lines()."""
    marks = set()
    for (r1, c1), (r2, c2), (r3, c3) in WINNING_LINES:
        first = b[r1][c1]
        if first != "" and first == b[r2][c2] == b[r3][c3]:
            marks.add(first)
    return marks


def test_the_rules_hold_for_every_board_a_real_game_can_reach():
    """Sweep all 3^9 boards at once.

    `value` is only asserted where at most one mark holds a line. 312 boards
    hand a line to both players at once, which no sequence of legal moves can
    produce, and the winner the code picks there is arbitrary.
    """
    decided = 0
    unreachable = 0
    swept = 0

    for cells in itertools.product(["", "X", "O"], repeat=9):
        b = [list(cells[0:3]), list(cells[3:6]), list(cells[6:9])]
        game = TicTacToe([row[:] for row in b])
        swept += 1

        assert game.full() == all(c for row in b for c in row)
        assert game.legal_moves() == [
            (r, c) for r in range(3) for c in range(3) if b[r][c] == ""
        ]

        marks = marks_with_a_line(b)
        assert game.is_over() == bool(marks) or game.full()

        if len(marks) == 1:
            decided += 1
            expected = 1 if marks.pop() == "X" else -1
            assert game.value() == expected, b
            assert game.outcome() == ("human" if expected == 1 else "bot"), b
        elif marks:
            unreachable += 1

    assert swept == 3**9
    assert decided == 8246, "boards with exactly one line, the only ones a "\
                             "real game ends on"
    assert unreachable == 312, "boards giving both players a line at once"


def test_whose_turn_follows_the_move_count():
    assert TicTacToe(EMPTY).whose_turn() == "X"
    assert TicTacToe(board(("X", "", ""), ("", "", ""), ("", "", ""))).whose_turn() == "O"
    assert TicTacToe(board(("X", "O", ""), ("", "", ""), ("", "", ""))).whose_turn() == "X"


def test_a_won_board_reports_its_winner():
    won = TicTacToe(board(("X", "X", "X"), ("O", "O", ""), ("", "", "")))

    assert won.outcome() == "human"
    assert won.is_over()
    assert won.best_move() is None
    assert all(b.disabled for b in won.view(player_id=1).children)


def test_a_full_board_is_a_tie():
    drawn = TicTacToe(board(("X", "O", "X"), ("X", "O", "O"), ("O", "X", "X")))

    assert drawn.outcome() == "tie"
    assert drawn.is_over()


def test_play_fills_the_cell_for_whose_turn_it_is():
    game = TicTacToe()
    game.play((0, 0))

    assert game.board[0][0] == "X"
    assert game.whose_turn() == "O"


def test_after_leaves_the_original_game_untouched():
    game = TicTacToe()
    nxt = game.after((1, 1))

    assert nxt.board[1][1] == "X"
    assert game.board[1][1] == ""


def test_minimax_from_the_empty_board_is_a_draw():
    assert TicTacToe(EMPTY)._minimax(float("-inf"), float("inf")) == 0


def test_minimax_scores_a_won_position():
    won = TicTacToe(board(("X", "X", "X"), ("O", "O", ""), ("", "", "")))
    lost = TicTacToe(board(("O", "O", "O"), ("X", "X", ""), ("", "", "")))

    assert won._minimax(float("-inf"), float("inf")) == 1
    assert lost._minimax(float("-inf"), float("inf")) == -1


def test_minimax_finds_a_win_the_human_can_force():
    """X has the diagonal and row 1, so O is already lost whatever it plays."""
    forked = TicTacToe(board(("X", "O", ""), ("", "X", ""), ("", "", "")))

    assert forked.whose_turn() == "O"
    assert forked._minimax(float("-inf"), float("inf")) == 1


def test_minimax_says_draw_where_nobody_can_do_better():
    """O to move with X holding two of the third column: blocking it is the
    only game, and the game then runs out without a line."""
    level = TicTacToe(board(("X", "O", "X"), ("O", "", "X"), ("", "", "")))

    assert level.whose_turn() == "O"
    assert level._minimax(float("-inf"), float("inf")) == 0


def test_the_bot_never_loses_against_arbitrary_play():
    """The bot minimises on its own turns, so it must never lose."""

    def self_play():
        def walk(game):
            if game.is_over():
                yield game
                return
            for move in game.legal_moves():
                nxt = game.after(move)
                nxt.play_bot_turn()
                yield from walk(nxt)

        yield from walk(TicTacToe())

    outcomes = [g.outcome() for g in self_play()]

    assert "human" not in outcomes
    assert "bot" in outcomes


def test_the_view_round_trips_through_discord_components():
    """Message.components is built from discord.components, not discord.ui,
    so this is the path a real click takes."""
    from discord.components import _component_factory

    game = TicTacToe()
    game.play((0, 0))
    game.play((1, 1))
    game.play_bot_turn()

    rebuilt = [_component_factory(d, None) for d in game.view(player_id=42).to_components()]

    assert TicTacToe.from_components(rebuilt).board == game.board


def test_an_unknown_button_is_ignored():
    from discord.components import _component_factory

    view = TicTacToe().view(player_id=7)
    payload = view.to_components()
    payload[0]["components"][0]["custom_id"] = "something_else"

    rebuilt = [_component_factory(d, None) for d in payload]

    assert TicTacToe.from_components(rebuilt).board[0][0] == ""


# ==================================================================== rps

OUTCOMES = {
    ("r", "r"): RpsResult.TIE, ("r", "p"): RpsResult.USER_WIN, ("r", "s"): RpsResult.BOT_WIN,
    ("p", "r"): RpsResult.BOT_WIN, ("p", "p"): RpsResult.TIE, ("p", "s"): RpsResult.USER_WIN,
    ("s", "r"): RpsResult.USER_WIN, ("s", "p"): RpsResult.BOT_WIN, ("s", "s"): RpsResult.TIE,
}


@pytest.mark.parametrize(("bot", "user"), list(OUTCOMES))
def test_rock_paper_scissors_outcomes(bot, user):
    game = RpsGame(user)
    game.bot_choice = bot
    game.result = game._settle()

    assert game.result is OUTCOMES[(bot, user)]


@pytest.mark.parametrize("junk", ["x", "", "lizard"])
def test_an_unknown_choice_is_an_error(junk):
    assert RpsGame(junk).result is RpsResult.ERROR


@pytest.mark.parametrize(
    ("asked", "letter"),
    [("rock", "r"), ("Rock", "r"), ("paper", "p"), ("scissors", "s"), ("R", "r")],
)
def test_the_choice_argument_is_normalised(asked, letter):
    assert RpsGame(asked).user_choice == letter


def test_the_bot_can_pick_anything():
    assert {RpsGame("rock").bot_choice for _ in range(300)} == {"r", "p", "s"}


@pytest.mark.parametrize(
    ("user", "bot", "title"),
    [("rock", "s", "You win!"), ("rock", "p", "Bot wins!"), ("rock", "r", "Tie!")],
)
def test_the_result_wording(user, bot, title):
    game = RpsGame(user)
    game.bot_choice = bot
    game.result = game._settle()

    assert game.embed().title == title
    assert game.embed().description == (
        f"You chose {RpsGame.CHOICES[user[0]]} and bot chose {RpsGame.CHOICES[bot]}."
    )


@pytest.mark.parametrize(
    ("button", "letter"),
    [("rps_rock", "r"), ("rps_paper", "p"), ("rps_scissors", "s")],
)
def test_buttons_map_to_choices(button, letter):
    assert RpsGame.from_button(button).user_choice == letter


def test_the_buttons_are_unchanged():
    view = RpsGame.choice_view()

    assert [b.custom_id for b in view.children] == [
        "rps_rock", "rps_paper", "rps_scissors"
    ]
    assert [b.label for b in view.children] == ["Rock", "Paper", "Scissors"]


# =============================================================== calculator

EVALUATIONS = {
    "1": "1",
    "2+3": "5",
    "2+3*4": "14",
    "2*3+4": "10",
    "(2+3)*4": "20",
    "10-(2+3)": "5",
    "((1+2)*(3+4))": "21",
    "2*3^2": "18",
    "2^3^2": "512",
    "2^(3^2)": "512",
    "10-2^2": "6",
    "10/4": "2.5",
    "10%3": "1",
    "1+2*3-4/2": "5",
    "5-(3-(2-1))": "3",
    "100-50-25": "25",
    "8/4/2": "1",
    "0.1+0.2": "0.3",
    "-3": "-3",
    "2*-3": "-6",
    "2--3": "5",
    "3+4*5-6/2": "20",
    "1.5*2.5": "3.75",
}


@pytest.mark.parametrize(("expr", "want"), EVALUATIONS.items())
def test_expressions_evaluate(expr, want):
    result = Calculator(expr).evaluate()

    assert result.success, result.error
    assert str(result.result) == want


@pytest.mark.parametrize(
    ("expr", "error"),
    [
        ("abc", "Invalid characters in expression"),
        ("1e5", "Invalid characters in expression"),
        ("((1+2)", "Mismatched parentheses in expression"),
        ("1+2)", "Mismatched parentheses in expression"),
        ("", "Invalid expression format"),
        ("1..2", "Invalid expression format"),
        ("5//2", "Invalid expression format"),
        ("^2", "Invalid expression format"),
    ],
)
def test_bad_expressions_say_why(expr, error):
    result = Calculator(expr).evaluate()

    assert not result.success
    assert result.error == error


def test_dividing_by_zero_is_reported_not_raised():
    assert not Calculator("1/0").evaluate().success


# ================================================================= laptop


def test_history_records_and_persists(monkeypatch):
    saved = []
    monkeypatch.setattr(database_sync, "save_laptop_history", lambda: saved.append(1))
    global_state.laptop_history.clear()

    history = LaptopHistory(42)
    history.append("help", "listed commands", secret1="q", secret2="p", secret3=7)

    entry = global_state.laptop_history["42"][0]
    assert entry["command"] == "help"
    assert entry["result"] == "listed commands"
    assert entry["secret1"] == "q"
    assert entry["secret3"] == "7"
    assert entry["timestamp"].isdigit()
    assert saved == [1]


def test_an_empty_history_says_so():
    global_state.laptop_history.clear()

    assert LaptopHistory(1).formatted() == "No commands executed yet."
    assert LaptopHistory(1).recent() == []
    assert LaptopHistory(1).last() is None


def test_history_honours_its_limit():
    global_state.laptop_history.clear()
    history = LaptopHistory(1)
    for i in range(12):
        history.append(f"c{i}", f"r{i}")

    assert len(history.recent()) == global_state.MAX_HISTORY_LINES
    assert len(history.recent(3)) == 3
    assert history.last()["command"] == "c11"


def test_history_is_per_user():
    global_state.laptop_history.clear()
    LaptopHistory(1).append("a", "b")

    assert LaptopHistory(2).entries == []


def test_the_screen_shows_the_history():
    global_state.laptop_history.clear()
    LaptopHistory(7).append("help", "listed commands")

    embed = HackerLaptop(7, "Arpan").screen()

    assert embed.title == "Arpan's PC"
    assert [f.name for f in embed.fields] == ["OS", "VPN Status", "Command History"]
    assert embed.fields[2].inline is False
    assert "`help` -> listed commands" in embed.fields[2].value


@pytest.mark.parametrize("_attempt", range(25))
def test_a_challenge_is_solvable(_attempt):
    """n(i) - n(i-1) = i*m + a, so the differences grow by exactly m each
    step. Drawn 25 times because the numbers come from a random source."""
    question, pattern, answer = HackerLaptop.challenge()
    series = [int(x) for x in pattern.split(", ")]

    assert question == "n(i) = n(i - 1) + (i * m) + a, find n(10):"
    assert len(series) == 9
    diffs = [series[i + 1] - series[i] for i in range(len(series) - 1)]
    steps = {diffs[i + 1] - diffs[i] for i in range(len(diffs) - 1)}
    assert len(steps) == 1, "the series must be linear in i"
    multiplier = steps.pop()
    adder = diffs[0] - 2 * multiplier
    assert 1 <= multiplier <= 3
    assert 1 <= adder <= 8
    assert answer == series[-1] + 10 * multiplier + adder


# ================================================================== nitro


def test_nitro_clears_both_cooldowns(monkeypatch):
    saved = []
    monkeypatch.setattr(database_sync, "save_works", lambda: saved.append("work"))
    monkeypatch.setattr(database_sync, "save_dailies", lambda: saved.append("daily"))

    now = datetime.now(UTC)
    global_state.user_worked_times = {5: now}
    global_state.user_daily_times = {5: now}

    NitroBoost(5).apply()

    for times, cooldown in (
        (global_state.user_worked_times, global_state.BASIC_COOLDOWN),
        (global_state.user_daily_times, global_state.DAILY_COOLDOWN),
    ):
        left = cooldown - (datetime.now(UTC) - times[5]).total_seconds()
        assert left <= 1, f"{left:.1f}s still on cooldown"
    assert sorted(saved) == ["daily", "work"]


def test_nitro_leaves_a_lapsed_cooldown_alone(monkeypatch):
    monkeypatch.setattr(database_sync, "save_works", lambda: None)
    monkeypatch.setattr(database_sync, "save_dailies", lambda: None)

    stale = datetime.now(UTC) - timedelta(days=5)
    global_state.user_worked_times = {5: stale}
    global_state.user_daily_times = {}

    NitroBoost(5).apply()

    assert global_state.user_worked_times[5] == stale


def test_nitro_only_touches_the_user_who_used_it(monkeypatch):
    monkeypatch.setattr(database_sync, "save_works", lambda: None)
    monkeypatch.setattr(database_sync, "save_dailies", lambda: None)

    now = datetime.now(UTC)
    global_state.user_worked_times = {5: now, 6: now}
    global_state.user_daily_times = {}

    NitroBoost(5).apply()

    assert global_state.user_worked_times[6] == now


def test_nitro_does_nothing_for_someone_who_never_claimed(monkeypatch):
    monkeypatch.setattr(database_sync, "save_works", lambda: None)
    monkeypatch.setattr(database_sync, "save_dailies", lambda: None)

    global_state.user_worked_times = {}
    global_state.user_daily_times = {}

    NitroBoost(404).apply()  # must not raise

    assert global_state.user_worked_times == {}


# ========================================================== colour swatch


def reference_swatch(red, green, blue, font):
    """The image builder as it was before it was shared out."""
    img = PILImage.new("RGB", (500, 500), color=(red, green, blue))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, 200, 55], radius=55 // 2, fill="white")
    draw.text((10, 6), f"RGB: {red}, {green}, {blue}", fill="black", font=font)
    draw.text((10, 26), f"HEX: #{red:02X}{green:02X}{blue:02X}", fill="black", font=font)
    mask = PILImage.new("L", (500, 500), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, 500, 500], radius=55 // 2, fill=255)
    img.putalpha(mask)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()


@pytest.mark.parametrize("rgb", [(255, 0, 0), (0, 128, 255), (18, 52, 86), (0, 0, 0)])
def test_the_swatch_is_the_image_it_used_to_be(rgb):
    from bot.commands.image_commands import _colour_swatch, _font

    assert _colour_swatch(*rgb).fp.read() == reference_swatch(*rgb, _font(18))


def test_the_swatch_is_named_for_the_embed_url():
    from bot.commands.image_commands import _colour_swatch

    assert _colour_swatch(1, 2, 3).filename == "color.png"


def test_the_font_falls_back_when_the_bundled_one_is_missing(monkeypatch):
    """The realistic failure is the font not being installed at all.

    Patching ImageFont.truetype wholesale would not do: Pillow's own
    load_default() reaches for truetype internally, so that patches the
    fallback too and the test passes for the wrong reason.
    """
    import bot.commands.image_commands as image_commands

    monkeypatch.setattr(
        global_state, "resource_path", lambda name: f"no/such/{name}"
    )

    assert image_commands._font(18) is not None


def test_the_font_comes_from_the_bundled_file_when_it_is_there():
    import bot.commands.image_commands as image_commands

    font = image_commands._font(18)

    assert font is not None
    assert str(font.path).endswith("Inter-SemiBold.ttf"), font.path