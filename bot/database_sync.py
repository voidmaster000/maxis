"""
Database sync for Maxis.

Loads and saves `bot.global_state` to MongoDB. Every group of state is stored as
one document holding parallel `key` and `val` lists, tagged by `name`.

Saving goes through a single background writer thread that shares one Mongo
client. That matters: handing each save its own thread and its own connection
let them race, so an older snapshot could land after a newer one and roll the
database back. One writer keeps saves in the order they were requested, and
superseded snapshots are collapsed rather than written.
"""

import threading
from datetime import UTC, datetime
from typing import Any, TypedDict

import pymongo

from bot import global_state
from bot.objects.user_settings import UserSettings
from bot.objects.warn import Warn


class Doc(TypedDict):
    """A persisted state group."""

    name: str
    key: list[Any]
    val: list[Any]


# --------------------------------------------------------------------------
# The writer
# --------------------------------------------------------------------------

_lock = threading.Lock()
_pending: dict[str, Doc] = {}
_inflight = 0
_wake = threading.Event()
_worker: threading.Thread | None = None
_client: pymongo.MongoClient | None = None

# Every document this bot persists. A name that is absent from the database is
# a fresh install rather than a failure, so writing one is allowed; a name that
# is present but could not be parsed stays unset here, and that is what makes
# its saves refuse.
DOCUMENTS = (
    "reply",
    "balance",
    "usersettings",
    "work",
    "rob",
    "daily",
    "weekly",
    "monthly",
    "warn",
    "laptop_history",
    "item",
)

# How many entries each document held when it was read. Unset means "not known
# to be good", which is what a save has to be sure of before replacing the
# whole document.
_loaded_counts: dict[str, int | None] = {}


def _collection() -> Any:
    """The shared client, opened on first use.

    One client for the whole process: pymongo pools connections inside it, so
    making one per save threw the pooling away and leaked sockets whenever a
    write raised before its close().
    """
    global _client
    with _lock:
        if _client is None:
            _client = pymongo.MongoClient(
                global_state.CONNSTR, serverSelectionTimeoutMS=5000
            )
    return _client[global_state.DATABASE][global_state.COLLECTION]


def _writer() -> None:
    """Drain pending documents until the process exits."""
    global _inflight

    while True:
        _wake.wait()
        _wake.clear()
        with _lock:
            batch = list(_pending.items())
            _pending.clear()
            _inflight += 1
        try:
            for name, doc in batch:
                try:
                    _collection().replace_one({"name": name}, doc, upsert=True)
                except Exception as e:
                    print(f"Error saving '{name}': {e}")
        finally:
            with _lock:
                _inflight -= 1


def _save(name: str, key: list[Any], val: list[Any]) -> None:
    """Queue a document to be written in the background.

    `key` and `val` must already be snapshots, taken by the caller: if they were
    read at write time they would describe newer state than the save asked for.
    """
    global _worker

    with _lock:
        _pending[name] = {"name": name, "key": key, "val": val}
        if _worker is None:
            _worker = threading.Thread(target=_writer, daemon=True)
            _worker.start()

    _wake.set()


def _may_replace(name: str, keys: list[Any]) -> bool:
    """Decide whether replacing this whole document with `keys` is safe.

    Every save is a whole-document replace, so a save that is wrong is not
    merged or corrected afterwards -- the old records are simply gone. Two
    ways of getting here look exactly like a bot that has no users yet, and
    both used to be silent:

    - the document was never read, because the database was unreachable or the
      document was malformed. The map being saved is then empty for a reason
      that has nothing to do with the users actually having no balances, and
      the very next /economy balance would erase everybody else's.
    - the document holds entries but the map in memory is empty.

    Refusing is loud on purpose. Silently not saving is its own failure, but it
    is the recoverable one; silently deleting every balance is not.
    """
    stored = _loaded_counts.get(name)
    if stored is None:
        print(
            f"Refusing to save '{name}': it was never loaded, so what is in "
            f"memory is not what is stored."
        )
        return False
    if not keys and stored:
        print(f"Refusing to replace {stored} stored '{name}' entry(ies) with none.")
        return False
    return True


def flush() -> None:
    """Block until every queued save has been written, not merely dequeued.

    Waiting only for the queue to empty would let close() shut the client while
    a write was still in flight.
    """
    while True:
        with _lock:
            if not _pending and not _inflight:
                return
        _wake.set()
        threading.Event().wait(0.02)


def close() -> None:
    """Flush anything outstanding and close the shared client."""
    flush()
    global _client
    with _lock:
        if _client is not None:
            _client.close()
            _client = None


def save_replies() -> None:
    keys = list(global_state.custom_replies)
    if _may_replace("reply", keys):
        _save("reply", keys, list(global_state.custom_replies.values()))


def save_balances() -> None:
    keys = list(global_state.balance_map)
    if _may_replace("balance", keys):
        _save("balance", keys, list(global_state.balance_map.values()))


def save_user_settings() -> None:
    keys = list(global_state.user_settings_map)
    if not _may_replace("usersettings", keys):
        return
    _save(
        "usersettings",
        keys,
        [
            {
                "dm": settings.bank_dm_enabled,
                "passive": settings.bank_passive_enabled,
            }
            for settings in global_state.user_settings_map.values()
        ],
    )


def _save_times(name: str, times: dict[int, datetime]) -> None:
    keys = list(times)
    if _may_replace(name, keys):
        _save(name, keys, list(times.values()))


def save_works() -> None:
    _save_times("work", global_state.user_worked_times)


def save_robs() -> None:
    _save_times("rob", global_state.user_robbed_times)


def save_dailies() -> None:
    _save_times("daily", global_state.user_daily_times)


def save_weeklies() -> None:
    _save_times("weekly", global_state.user_weekly_times)


def save_monthlies() -> None:
    _save_times("monthly", global_state.user_monthly_times)


def save_warns() -> None:
    keys = list(global_state.warn_map)
    if not _may_replace("warn", keys):
        return
    _save(
        "warn",
        keys,
        [
            {
                "key": list(members),
                "val": [
                    {
                        "id": warn.user_id,
                        "warns": warn.warns,
                        "causes": warn.warn_causes,
                    }
                    for warn in members.values()
                ],
            }
            for members in global_state.warn_map.values()
        ],
    )


def save_laptop_history() -> None:
    keys = list(global_state.laptop_history)
    if _may_replace("laptop_history", keys):
        _save("laptop_history", keys, list(global_state.laptop_history.values()))


def save_inventory() -> None:
    keys = list(global_state.inventory)
    if not _may_replace("item", keys):
        return
    _save(
        "item",
        keys,
        [
            {"key": list(items), "val": list(counts)}
            for items, counts in global_state.inventory.values()
        ],
    )


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def _utc(value: datetime | None) -> datetime | None:
    """Mongo returns naive datetimes; every in-memory one is UTC-aware."""
    return value.replace(tzinfo=UTC) if value is not None else None


def _replace(target: dict, loaded: dict) -> None:
    """Swap a whole state map for freshly loaded data.

    The caller builds `loaded` first, so a malformed document raises before
    anything is touched rather than leaving the map half overwritten.
    """
    target.clear()
    target.update(loaded)


def _warn(data: dict) -> Warn:
    """Rebuild one Warn from its stored form."""
    warn = Warn()
    warn.user_id = data.get("id") or 0
    warn.warns = data.get("warns") or 0
    warn.warn_causes = data.get("causes") or []
    return warn


def load_all() -> None:
    """Load every persisted document into memory.

    Each document is loaded on its own, so one unreadable group is reported and
    skipped rather than leaving the bot with nothing loaded and about to save
    that emptiness back over the database.

    A document that is skipped is left unset in _loaded_counts, which is what
    makes save_* refuse for it: the in-memory map is empty because the read
    failed, not because the users have no data. If the database itself could
    not be reached then every document stays unset and nothing is saved at all.
    """
    _loaded_counts.clear()
    connected = False
    seen: set[str] = set()

    try:
        for doc in _collection().find():
            name = doc.get("name")
            seen.add(name)
            try:
                _load_doc(doc)
            except Exception as e:
                # Explicit rather than absent: this one was seen and could not
                # be read, which is what save_* needs to know to refuse.
                _loaded_counts[name] = None
                print(f"Error loading document '{name}': {e}")
        connected = True
        print("Retrieved all data.")
    except Exception as e:
        print(f"Error initializing data: {e}")

    for name in DOCUMENTS:
        if name not in seen:
            # Absent from the database, which for a fresh install is correct
            # rather than a failure, so writing one is allowed.
            _loaded_counts[name] = 0 if connected else None


def _load_doc(doc: Doc) -> None:
    name = doc["name"]
    keys = doc.get("key") or []
    vals = doc.get("val") or []

    if name == "reply":
        _replace(global_state.custom_replies, dict(zip(keys, vals, strict=True)))

    elif name == "balance":
        _replace(global_state.balance_map, dict(zip(keys, vals, strict=True)))

    elif name == "usersettings":
        _replace(
            global_state.user_settings_map,
            {
                user_id: UserSettings(
                    bank_dm_enabled=entry.get("dm", True),
                    bank_passive_enabled=entry.get("passive", False),
                )
                for user_id, entry in zip(keys, vals, strict=True)
            },
        )

    elif name == "work":
        _load_times(global_state.user_worked_times, keys, vals)

    elif name == "rob":
        _load_times(global_state.user_robbed_times, keys, vals)

    elif name == "daily":
        _load_times(global_state.user_daily_times, keys, vals)

    elif name == "weekly":
        _load_times(global_state.user_weekly_times, keys, vals)

    elif name == "monthly":
        _load_times(global_state.user_monthly_times, keys, vals)

    elif name == "warn":
        _replace(
            global_state.warn_map,
            {
                server_id or 0: {
                    user_id: _warn(data)
                    for user_id, data in zip(
                        entry.get("key") or [], entry.get("val") or [], strict=True
                    )
                }
                for server_id, entry in zip(keys, vals, strict=True)
            },
        )

    elif name == "item":
        _replace(
            global_state.inventory,
            {
                user_id or 0: dict(
                    zip(
                        entry.get("key") or [],
                        entry.get("val") or [],
                        strict=True,
                    )
                )
                for user_id, entry in zip(keys, vals, strict=True)
            },
        )

    elif name == "laptop_history":
        _replace(global_state.laptop_history, dict(zip(keys, vals, strict=True)))

    else:
        print(f"Unknown document '{name}' found! Skipping")
        return

    # Only reached when the document parsed cleanly, which is what lets
    # save_* trust the map it is about to write.
    _loaded_counts[name] = len(keys)


def _load_times(target: dict[int, datetime], keys: list[Any], vals: list[Any]) -> None:
    _replace(
        target,
        {key: _utc(value) for key, value in zip(keys, vals, strict=True)},
    )
