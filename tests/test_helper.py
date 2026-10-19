"""The shared helpers, and the currency reference data they sit next to.

Both were changed during the cleanup: the random helper had its arguments the
wrong way round relative to its own name, and the currency list used to be read
from disk at import of `global_state`, which everything imports.
"""

import json
import logging

import pytest

from bot import currencies
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


def test_the_shipped_currency_list_loads():
    assert "USD" in currencies.CURRENCY_CODES
    assert currencies.CURRENCIES[0]["code"] == "USD"


def _point_at(monkeypatch, tmp_path, content: str):
    """Make the module read a file of our choosing instead of the shipped one."""
    path = tmp_path / "currencies.json"
    path.write_text(content)
    monkeypatch.setattr(currencies, "resource_path", lambda name: path)
    return path


def test_a_missing_currency_file_is_reported_not_raised(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(
        currencies, "resource_path", lambda name: tmp_path / "gone.json"
    )

    with caplog.at_level(logging.ERROR, logger="bot.currencies"):
        loaded = currencies._load()

    assert loaded == []
    assert "Could not read the currency list" in caplog.text


def test_a_malformed_currency_file_is_reported(monkeypatch, tmp_path, caplog):
    _point_at(monkeypatch, tmp_path, "{not json at all")

    with caplog.at_level(logging.ERROR, logger="bot.currencies"):
        loaded = currencies._load()

    assert loaded == []
    assert "Could not read the currency list" in caplog.text


def test_a_wrong_shaped_currency_file_is_reported(monkeypatch, tmp_path, caplog):
    """Well-formed JSON is not the same as the shape we asked for."""
    _point_at(monkeypatch, tmp_path, json.dumps({"currencies": "USD, EUR"}))

    with caplog.at_level(logging.ERROR, logger="bot.currencies"):
        loaded = currencies._load()

    assert loaded == []
    assert "does not contain a 'currencies' list" in caplog.text


def test_a_good_currency_file_loads(monkeypatch, tmp_path):
    _point_at(monkeypatch, tmp_path, json.dumps({"currencies": [{"code": "GBP"}]}))

    assert currencies._load() == [{"code": "GBP"}]
