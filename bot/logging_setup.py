"""
Logging configuration for Maxis.

Called once from the entry point. Modules elsewhere only ask for a logger with
`logging.getLogger(__name__)`; they never configure handlers, so the format and
destination are decided in exactly one place.
"""

import logging


def setup_logging(level: int = logging.INFO) -> None:
    """Send log records to stderr with a timestamp, level and module name.

    basicConfig is a no-op when the root logger already has a handler, which is
    what keeps this safe to call from a test run or from a host that has already
    configured logging.
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
