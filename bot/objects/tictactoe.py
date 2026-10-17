"""
Tic tac toe game for /utility ttt.

The object owns everything about one game: the board, the rules, the minimax
the bot plays with, and the Discord view that renders it. The command and the
button handler only have to say "play this cell", then send back whatever the
game says to show.
"""

import discord

from bot.helper import get_random_color


class TicTacToe:
    """A single game of tic tac toe, played against an optimal bot."""

    HUMAN = "X"
    BOT = "O"

    def __init__(self, board: list[list[str]] | None = None) -> None:
        self.board = (
            board if board is not None else [["" for _ in range(3)] for _ in range(3)]
        )

    # ------------------------------------------------------------------
    # Rebuilding a game from the buttons of an existing message
    # ------------------------------------------------------------------

    @classmethod
    def from_components(cls, components: list) -> "TicTacToe":
        """Recover the board from the tic tac toe buttons of a message.

        Discord builds Message.components out of the discord.components
        hierarchy, which is a different set of classes to discord.ui, so this
        reads the two attributes it needs by name rather than testing for
        types that differ between the two.
        """
        board = [["" for _ in range(3)] for _ in range(3)]
        for row in components:
            for item in getattr(row, "children", ()):
                custom_id = getattr(item, "custom_id", None)
                label = getattr(item, "label", None)
                if not isinstance(custom_id, str) or not custom_id.startswith("ttt_"):
                    continue
                if label not in (cls.HUMAN, cls.BOT):
                    continue
                _, r, c, _ = custom_id.split("_")
                board[int(r)][int(c)] = label
        return cls(board)

    # ------------------------------------------------------------------
    # Rules
    # ------------------------------------------------------------------

    def _lines(self) -> list[list[str]]:
        """Every winning line, in the order the game settles them."""
        lines = []
        for i in range(3):
            lines.append(self.board[i])
            lines.append([self.board[0][i], self.board[1][i], self.board[2][i]])
        lines.append([self.board[0][0], self.board[1][1], self.board[2][2]])
        lines.append([self.board[0][2], self.board[1][1], self.board[2][0]])
        return lines

    def value(self) -> int:
        """1 if the human has a line, -1 if the bot does, else 0."""
        for line in self._lines():
            if line[0] != "" and line[0] == line[1] == line[2]:
                return 1 if line[0] == self.HUMAN else -1
        return 0

    def full(self) -> bool:
        """True when no cell is left empty."""
        return all(cell != "" for row in self.board for cell in row)

    def is_over(self) -> bool:
        """True once somebody has a line, or the board is full."""
        return self.value() != 0 or self.full()

    def outcome(self) -> str:
        """`"human"`, `"bot"` or `"tie"`. Only meaningful once `is_over`."""
        value = self.value()
        if value == 1:
            return "human"
        return "bot" if value == -1 else "tie"

    def whose_turn(self) -> str:
        """`HUMAN` or `BOT`, whoever has made one fewer move."""
        human = sum(row.count(self.HUMAN) for row in self.board)
        bot = sum(row.count(self.BOT) for row in self.board)
        return self.HUMAN if human == bot else self.BOT

    def legal_moves(self) -> list[tuple[int, int]]:
        """Every empty cell, in row-major order."""
        return [(r, c) for r in range(3) for c in range(3) if self.board[r][c] == ""]

    # ------------------------------------------------------------------
    # Playing
    # ------------------------------------------------------------------

    def play(self, move: tuple[int, int]) -> None:
        """Put a mark down for whoever's turn it is."""
        r, c = move
        self.board[r][c] = self.whose_turn()

    def after(self, move: tuple[int, int]) -> "TicTacToe":
        """A copy of this game with `move` played. This game is untouched."""
        nxt = TicTacToe([row.copy() for row in self.board])
        nxt.play(move)
        return nxt

    def best_move(self) -> tuple[int, int] | None:
        """The bot's optimal move, or None if the game is already over."""
        if self.is_over():
            return None
        best: tuple[int, int] | None = None
        best_score = float("inf")
        for move in self.legal_moves():
            score = self.after(move)._minimax(float("-inf"), float("inf"))
            if score < best_score:
                best, best_score = move, score
        return best

    def play_bot_turn(self) -> bool:
        """Let the bot take its turn. False if it had nowhere to go."""
        move = self.best_move()
        if move is None:
            return False
        self.play(move)
        return True

    def _minimax(self, alpha: float, beta: float) -> int:
        """Board value for the bot, minimising, with alpha-beta pruning."""
        if self.is_over():
            return self.value()

        minimising = self.whose_turn() == self.BOT
        best = float("inf") if minimising else float("-inf")
        for move in self.legal_moves():
            score = self.after(move)._minimax(alpha, beta)
            best = min(best, score) if minimising else max(best, score)
            if minimising:
                beta = min(beta, best)
            else:
                alpha = max(alpha, best)
            if beta <= alpha:
                break
        return int(best)

    # ------------------------------------------------------------------
    # Discord rendering
    # ------------------------------------------------------------------

    _RESULTS = {
        "human": ("You win!", "Congratulations, you won the game!"),
        "bot": ("Bot wins!", "Sorry, the bot won this time."),
        "tie": ("It's a tie!", "The game ended in a draw."),
    }

    def embed(self) -> discord.Embed:
        """The message describing the current position."""
        if not self.is_over():
            return discord.Embed(
                title="Tic Tac Toe",
                description="Select a move.",
                color=get_random_color(),
            )
        title, description = self._RESULTS[self.outcome()]
        return discord.Embed(
            title=title, description=description, color=get_random_color()
        )

    def view(self, player_id: int) -> discord.ui.View:
        """The 3x3 grid of buttons, owned by `player_id`."""
        view = discord.ui.View()
        disabled = self.is_over()
        for r in range(3):
            for c in range(3):
                cell = self.board[r][c]
                if cell == self.HUMAN:
                    style = discord.ButtonStyle.success
                elif cell == self.BOT:
                    style = discord.ButtonStyle.danger
                else:
                    cell = "\u200b"
                    style = discord.ButtonStyle.secondary
                view.add_item(
                    discord.ui.Button(
                        label=cell,
                        style=style,
                        custom_id=f"ttt_{r}_{c}_{player_id}",
                        row=r,
                        disabled=disabled,
                    )
                )
        return view
