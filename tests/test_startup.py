"""Starting up the bot: what on_ready is allowed to do, and when.

The bug this exists for: database_sync.load_all() is blocking Mongo I/O.
Called straight from the event loop it stalls the whole bot for as long as the
server takes to answer, and Discord gives an interaction three seconds to be
answered. Anything arriving in that window is dead, and comes back as error
10062, Unknown interaction.
"""

import asyncio
import threading
import time

import pytest

import bot.main as main
from bot import database_sync


@pytest.fixture(autouse=True)
def reset_startup_flags(monkeypatch):
    """Each test starts as though the bot has never been ready."""
    monkeypatch.setattr(main, "_cogs_loaded", False)
    monkeypatch.setattr(main, "_initialised", False)
    monkeypatch.setattr(main, "_start_status_page", lambda: None)


async def _nothing(*args, **kwargs):
    return None


def stub_ready_environment(monkeypatch, load_seconds: float = 0.0) -> threading.Event:
    """Neutralise everything on_ready touches except load_all, and report when
    load_all actually ran."""
    ran = threading.Event()

    def slow_load() -> None:
        ran.set()
        time.sleep(load_seconds)

    monkeypatch.setattr(database_sync, "load_all", slow_load)
    monkeypatch.setattr(main, "setup_slash_commands", _nothing)
    monkeypatch.setattr(main, "ensure_user_settings", _nothing)
    monkeypatch.setattr(main.bot, "change_presence", _nothing)
    monkeypatch.setattr(main.bot.tree, "sync", _nothing)
    return ran


async def test_loading_the_database_does_not_block_the_event_loop(monkeypatch):
    """The loop must stay free to answer other commands while Mongo is read."""
    load_seconds = 0.5
    ran = stub_ready_environment(monkeypatch, load_seconds=load_seconds)

    task = asyncio.create_task(main.on_ready())

    # Count how often the loop can run while load_all sits in its thread.
    # sleep(0) yields without waiting, so a free loop spins thousands of times
    # and a blocked one gets through none at all.
    ticks = 0
    started = time.perf_counter()
    while time.perf_counter() - started < load_seconds / 2:
        await asyncio.sleep(0)
        ticks += 1

    assert ran.is_set(), "load_all never started"
    assert ticks > 100, f"loop managed only {ticks} ticks while load_all was running"

    await task


async def test_the_database_is_loaded_off_the_event_loop_thread(monkeypatch):
    """to_thread is what frees the loop; assert the read is genuinely elsewhere."""
    stub_ready_environment(monkeypatch)
    loop_thread = threading.get_ident()
    load_thread: list[int] = []

    monkeypatch.setattr(
        database_sync, "load_all", lambda: load_thread.append(threading.get_ident())
    )

    await main.on_ready()

    assert load_thread, "load_all never ran"
    assert load_thread[0] != loop_thread


async def test_startup_work_happens_once_across_reconnects(monkeypatch):
    """on_ready fires again on every reconnect; re-reading Mongo and
    re-fetching every member of every guild each time burns API quota for no
    new information."""
    calls: list[str] = []

    def counted(label):
        async def record(*args, **kwargs):
            calls.append(label)

        return record

    monkeypatch.setattr(main, "setup_slash_commands", counted("cogs"))
    monkeypatch.setattr(database_sync, "load_all", lambda: calls.append("load_all"))
    monkeypatch.setattr(main, "ensure_user_settings", counted("settings"))
    monkeypatch.setattr(main.bot, "change_presence", _nothing)
    monkeypatch.setattr(main.bot.tree, "sync", _nothing)

    for _ in range(3):
        await main.on_ready()

    assert calls == ["cogs", "load_all", "settings"]


async def test_commands_are_registered_again_never(monkeypatch):
    """on_ready can fire repeatedly; re-adding a cog raises."""
    calls: list[str] = []

    async def record(bot):
        calls.append("cogs")

    monkeypatch.setattr(main, "setup_slash_commands", record)
    monkeypatch.setattr(database_sync, "load_all", lambda: None)
    monkeypatch.setattr(main, "ensure_user_settings", _nothing)
    monkeypatch.setattr(main.bot, "change_presence", _nothing)
    monkeypatch.setattr(main.bot.tree, "sync", _nothing)

    for _ in range(3):
        await main.on_ready()

    assert calls == ["cogs"]