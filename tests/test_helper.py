"""The shared helpers.

`get_random_integer` had its arguments the wrong way round relative to its own
name, so the order is pinned here. What matters about the currency list now that
it is a constant in `global_state` is its shape: Discord rejects a command that
offers more choices than one option allows.
"""

import pytest

from bot import global_state
from bot.helper import get_random_integer

# ------------------------------------------------------------------- random


def test_a_range_of_one_value_returns_that_value():
    assert get_random_integer(7, 7) == 7


def test_every_draw_lands_inside_the_range():
    draws = [get_random_integer(100, 500) for _ in range(200)]
    assert all(100 <= draw <= 500 for draw in draws)


def test_both_bounds_are_reachable():
    """The bug this pins: passing the arguments the other way round used to be
    silently accepted, and returned 0 for an inverted range instead of the
    values the caller asked for."""
    draws = {get_random_integer(1, 2) for _ in range(100)}
    assert draws == {1, 2}


def test_an_inverted_range_is_an_error_rather_than_a_zero():
    with pytest.raises(ValueError):
        get_random_integer(500, 100)


# ---------------------------------------------------------------- currency


def test_the_currency_list_fits_the_choice_limit():
    """One command option may carry at most 25 choices, and currconv uses one."""
    assert len(global_state.CURRENCY_CODES) <= 25


def test_the_currency_list_is_unique_three_letter_codes():
    codes = global_state.CURRENCY_CODES
    assert len(set(codes)) == len(codes), "a duplicate choice would be rejected"
    assert all(code.isalpha() and code.isupper() and len(code) == 3 for code in codes)


def test_the_currency_list_still_contains_the_major_pair():
    """A cheap guard against the list being emptied or replaced wholesale."""
    assert "USD" in global_state.CURRENCY_CODES
    assert "EUR" in global_state.CURRENCY_CODES
