"""The database writer and loader.

The writer's whole job is that saves reach MongoDB in the order they were
requested, on one shared connection, and that a failure never takes the rest
down with it.
"""

import threading
import time

import pytest

from bot import database_sync, global_state


class FakeCollection:
    """Records writes in arrival order; can be made to block or fail."""

    def __init__(self) -> None:
        self.writes: list[tuple[str, list]] = []
        self.fail_names: set[str] = set()
        self.gate: threading.Event | None = None
        self.upserts: list[bool] = []

    def replace_one(self, filt, doc, upsert=False):
        if self.gate is not None:
            self.gate.wait(2)
        if doc["name"] in self.fail_names:
            raise RuntimeError(f"simulated failure writing {doc['name']}")
        self.upserts.append(upsert)
        self.writes.append((doc["name"], list(doc["val"])))

    def find(self):
        return iter(())


@pytest.fixture
def collection(monkeypatch):
    """Point database_sync at a fake collection and drain any queued writes."""
    fake = FakeCollection()
    monkeypatch.setattr(database_sync, "_collection", lambda: fake, raising=False)
    database_sync.flush()
    yield fake
    fake.gate = None
    database_sync.flush()


def values(fake):
    return [v for _, v in fake.writes]


# --------------------------------------------------------------- ordering


def test_newest_snapshot_wins_however_fast_saves_arrive(collection):
    """The bug this guards: independent threads let an older write land last."""
    for n in range(200):
        database_sync._save("balance", [n], [n])
    database_sync.flush()

    assert values(collection) == [[199]]


def test_superseded_snapshots_are_collapsed(collection):
    """What /economy rob does: three balance saves inside one command."""
    database_sync._save("balance", [1], [100])
    database_sync._save("balance", [1], [200])
    database_sync._save("balance", [1], [300])
    database_sync.flush()

    assert collection.writes == [("balance", [300])]


def test_distinct_documents_are_not_collapsed_into_each_other(collection):
    for name in ("balance", "warn", "inventory"):
        database_sync._save(name, [1], [1])
    database_sync.flush()

    assert {name for name, _ in collection.writes} == {"balance", "warn", "inventory"}


def test_every_document_is_written_with_an_upsert(collection):
    """No count-then-insert: that races two writers into duplicates."""
    database_sync._save("balance", [1], [1])
    database_sync.flush()

    assert collection.upserts == [True]


# ----------------------------------------------------------------- safety


def test_one_failing_document_does_not_stop_the_others(collection):
    collection.fail_names = {"warn"}
    for name in ("balance", "warn", "inventory"):
        database_sync._save(name, [1], [1])
    database_sync.flush()

    assert {name for name, _ in collection.writes} == {"balance", "inventory"}


def test_saving_never_blocks_the_caller(collection):
    """A command must never wait on IO."""
    collection.gate = threading.Event()
    try:
        started = time.perf_counter()
        for _ in range(20):
            database_sync._save("balance", [1], [1])
        elapsed = time.perf_counter() - started
    finally:
        collection.gate.set()
        collection.gate = None

    assert elapsed < 0.5, f"save() blocked for {elapsed * 1000:.0f} ms"


def test_one_client_is_shared_and_its_timeout_is_bounded(monkeypatch):
    """A client per save threw away pymongo's pooling and leaked on error."""
    opened: list[dict] = []

    class FakeClient:
        def __init__(self, connstr, **kwargs):
            opened.append(kwargs)

        def __getitem__(self, key):
            return self

        def close(self):
            pass

    import pymongo

    monkeypatch.setattr(pymongo, "MongoClient", FakeClient)
    monkeypatch.setattr(database_sync, "_collection", database_sync._collection)
    monkeypatch.setattr(database_sync, "_client", None, raising=False)
    database_sync.flush()

    for _ in range(50):
        database_sync._save("balance", [1], [1])
    database_sync.flush()

    assert len(opened) == 1
    assert "serverSelectionTimeoutMS" in opened[0]
    database_sync.close()


def test_flush_waits_for_the_write_and_not_just_for_the_queue(monkeypatch):
    """flush() is a barrier, not a queue drain.

    close() shuts the shared client, so flush() returning while a write was
    still running would mean closing the client out from under it.
    """
    landed = threading.Event()
    release = threading.Event()

    class SlowCollection:
        def replace_one(self, filt, doc, upsert=False):
            release.wait(2)
            landed.set()

        def find(self):
            return iter(())

    monkeypatch.setattr(database_sync, "_collection", lambda: SlowCollection())

    database_sync._save("balance", [1], [1])

    # Wait until the writer has taken the document off the queue and started
    # the write, so the flush below is waiting on the write and not the queue.
    deadline = time.perf_counter() + 2
    while not database_sync._inflight and time.perf_counter() < deadline:
        time.sleep(0.005)
    assert database_sync._inflight, "the writer never picked the document up"

    returned = threading.Event()
    threading.Thread(
        target=lambda: (database_sync.flush(), returned.set()), daemon=True
    ).start()

    try:
        assert not returned.wait(0.2), "flush() returned during an in-flight write"
    finally:
        release.set()

    assert returned.wait(2), "flush() never returned"
    assert landed.is_set()


# --------------------------------------------------------------- the loader


def test_a_well_formed_document_loads():
    global_state.balance_map = {}
    database_sync._load_doc({"name": "balance", "key": [1, 2, 3], "val": [10, 20, 30]})

    assert global_state.balance_map == {1: 10, 2: 20, 3: 30}


def test_a_length_mismatch_is_rejected_rather_than_truncating():
    """A short `val` list used to silently drop users from the bank."""
    global_state.balance_map = {}
    with pytest.raises(ValueError):
        database_sync._load_doc({"name": "balance", "key": [1, 2, 3], "val": [10]})

    assert global_state.balance_map == {}


def test_a_mismatch_leaves_nothing_half_loaded():
    global_state.inventory = {99: {"Juice": 5}}
    with pytest.raises(ValueError):
        database_sync._load_doc(
            {"name": "item", "key": [1], "val": [{"key": ["Juice", "Nitro"], "val": [1]}]}
        )

    assert global_state.inventory == {99: {"Juice": 5}}


def test_missing_key_or_val_loads_as_empty():
    global_state.laptop_history = {"stale": []}
    database_sync._load_doc({"name": "laptop_history"})

    assert global_state.laptop_history == {}


def test_nested_documents_load():
    global_state.inventory = {}
    database_sync._load_doc(
        {"name": "item", "key": [1], "val": [{"key": ["Juice", "Nitro"], "val": [2, 1]}]}
    )

    assert global_state.inventory == {1: {"Juice": 2, "Nitro": 1}}


def test_each_document_is_loaded_independently(monkeypatch):
    """One unreadable group must not leave the bot with nothing, ready to
    save that emptiness back over the database."""

    def explode(doc):
        raise ValueError("bad")

    monkeypatch.setattr(database_sync, "_load_doc", explode)
    calls = []

    class Loader(FakeCollection):
        def find(self):
            calls.append(1)
            return iter([{"name": "balance"}, {"name": "warn"}])

    monkeypatch.setattr(database_sync, "_collection", lambda: Loader())
    database_sync.load_all()

    assert len(calls) == 1, "find() should have been walked to the end"