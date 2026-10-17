"""
Mathematical expression evaluation for /utility calculate.

Recursive descent over PEMDAS. Each level of the grammar is one method, so the
precedence lives in the call structure rather than in a hand-rolled pass per
operator group: `^` binds tightest and is right associative, then `* / %`,
then `+ -`.
"""

from decimal import Decimal


class ExpressionResult:
    """The outcome of an evaluation: a value, or why there wasn't one."""

    def __init__(self, success: bool, result: Decimal = Decimal("0"), error: str = ""):
        self.success = success
        self.result = result
        self.error = error

    def __repr__(self) -> str:
        if self.success:
            return f"ExpressionResult(success, {self.result})"
        return f"ExpressionResult(failure, error={self.error!r})"


class Calculator:
    """Evaluates one arithmetic expression.

    Supports `+ - * / % ^`, parentheses, decimals, and unary signs.
    """

    ALLOWED = "+-*/%^(). "

    def __init__(self, expression: str) -> None:
        self.expression = expression
        self.text = ""
        self.pos = 0

    # ------------------------------------------------------------------

    def evaluate(self) -> ExpressionResult:
        """Work the expression out, or say why it could not be worked out."""
        try:
            if not all(c.isdigit() or c in self.ALLOWED for c in self.expression):
                return ExpressionResult(
                    success=False, error="Invalid characters in expression"
                )
            if self.expression.count("(") != self.expression.count(")"):
                return ExpressionResult(
                    success=False, error="Mismatched parentheses in expression"
                )

            self.text = self.expression.replace(" ", "")
            self.pos = 0
            if not self.text:
                return ExpressionResult(
                    success=False, error="Invalid expression format"
                )

            value = self._sum()
            if self.pos != len(self.text):
                return ExpressionResult(
                    success=False, error="Invalid expression format"
                )
            return ExpressionResult(success=True, result=value)
        except Exception as e:
            return ExpressionResult(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Grammar:  sum -> product -> power -> unary -> primary
    # ------------------------------------------------------------------

    def _peek(self) -> str:
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def _sum(self) -> Decimal:
        value = self._product()
        while self._peek() in ("+", "-"):
            operator = self.text[self.pos]
            self.pos += 1
            right = self._product()
            value = value + right if operator == "+" else value - right
        return value

    def _product(self) -> Decimal:
        value = self._power()
        while self._peek() in ("*", "/", "%"):
            operator = self.text[self.pos]
            self.pos += 1
            right = self._power()
            if operator == "*":
                value = value * right
            elif operator == "/":
                value = value / right
            else:
                value = value % right
        return value

    def _power(self) -> Decimal:
        base = self._unary()
        if self._peek() == "^":
            self.pos += 1
            # right associative: 2^3^2 is 2^(3^2)
            return base ** self._power()
        return base

    def _unary(self) -> Decimal:
        if self._peek() in ("+", "-"):
            operator = self.text[self.pos]
            self.pos += 1
            value = self._unary()
            return -value if operator == "-" else value
        return self._primary()

    def _primary(self) -> Decimal:
        if self._peek() == "(":
            self.pos += 1
            value = self._sum()
            if self._peek() != ")":
                raise ValueError("Invalid expression format")
            self.pos += 1
            return value

        start = self.pos
        while self._peek().isdigit() or self._peek() == ".":
            self.pos += 1
        if start == self.pos:
            raise ValueError("Invalid expression format")
        try:
            return Decimal(self.text[start : self.pos])
        except ArithmeticError as e:
            # a run of digits and dots that is not a number, such as "1..2"
            raise ValueError("Invalid expression format") from e
