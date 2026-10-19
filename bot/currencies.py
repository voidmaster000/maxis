"""
The supported currency list, read from resources/currencies.json.

This lives outside `global_state` because `global_state` is imported by every
module in the bot and should not depend on the filesystem. Only `/utility
currconv` needs this data.

The read still happens at import time. That is not avoidable: discord.py takes
the `Choice` list when the command is defined, so the data has to exist by then.

A missing or malformed file is reported here and yields an empty list, which
`currconv` then refuses to run with. Starting the rest of the bot is better than
crashing over one command's reference data.
"""

import json
import logging
from typing import TypedDict

from bot.global_state import resource_path

logger = logging.getLogger(__name__)


class Currency(TypedDict):
    """One currency as it appears in resources/currencies.json."""

    code: str
    name: str


def _load() -> list[Currency]:
    """Read the supported currency list, or report why it could not be read."""
    path = resource_path("currencies.json")
    try:
        with open(path) as file:
            data: dict[str, list[Currency]] = json.load(file)
    except Exception:
        logger.exception("Could not read the currency list from %s", path)
        return []

    currencies = data.get("currencies")
    if not isinstance(currencies, list):
        logger.error("%s does not contain a 'currencies' list", path)
        return []
    return currencies


CURRENCIES: list[Currency] = _load()

# The codes the command accepts, in file order.
CURRENCY_CODES: list[str] = [entry["code"] for entry in CURRENCIES if "code" in entry]
