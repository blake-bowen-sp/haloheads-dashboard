import sys
import types
import pytest
from tests.fixtures.carnage_blue import CARNAGE_BLUE
from haloheads.docs import build_docs


def _docs():
    return build_docs(
        CARNAGE_BLUE,
        match_id="m1",
        source_image="pending/x.jpg",
        img_hash="hhh",
        uploaded_at="t0",
        analyzed_at="t1",
    )


class _FakeDoc:
    def __init__(self):
        self._data = None

    def set(self, data):
        self._data = data

    def to_dict(self):
        return self._data


class _FakeWhereQuery:
    def __init__(self, collection, field, op, value):
        self._collection = collection
        self._field = field
        self._op = op
        self._value = value
        self._limit_n = None
        self._queries = []

    def limit(self, n):
        self._limit_n = n
        self._queries.append(("limit", n))
        return self

    def get(self):
        results = [
            doc for doc in self._collection._docs.values()
            if doc._data and doc._data.get(self._field) == self._value
        ]
        if self._limit_n is not None:
            results = results[: self._limit_n]
        self._collection._where_queries.append({
            "field": self._field,
            "op": self._op,
            "value": self._value,
        })
        return results


class _FakeCollection:
    def __init__(self):
        self._docs: dict[str, _FakeDoc] = {}
        self._where_queries: list[dict] = []

    def document(self, doc_id: str) -> _FakeDoc:
        if doc_id not in self._docs:
            self._docs[doc_id] = _FakeDoc()
        return self._docs[doc_id]

    def where(self, field, op, value) -> _FakeWhereQuery:
        return _FakeWhereQuery(self, field, op, value)

    def stream(self):
        return list(self._docs.values())


class _FakeFirestoreClient:
    def __init__(self, project=None):
        self._collections: dict[str, _FakeCollection] = {}

    def collection(self, name: str) -> _FakeCollection:
        if name not in self._collections:
            self._collections[name] = _FakeCollection()
        return self._collections[name]


@pytest.fixture
def fake_firestore_store(monkeypatch):
    fake_client = _FakeFirestoreClient()

    gcs_mod = types.ModuleType("google.cloud.firestore")
    gcs_mod.Client = lambda project=None: fake_client

    google_mod = types.ModuleType("google")
    cloud_mod = types.ModuleType("google.cloud")
    google_mod.cloud = cloud_mod
    cloud_mod.firestore = gcs_mod

    monkeypatch.setitem(sys.modules, "google", google_mod)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud_mod)
    monkeypatch.setitem(sys.modules, "google.cloud.firestore", gcs_mod)

    from haloheads.store import FirestoreStore
    store = FirestoreStore(project="test-project")
    return store, fake_client


def test_add_match_writes_correct_counts(fake_firestore_store):
    store, client = fake_firestore_store
    match, players = _docs()
    store.add_match(match, players)
    assert len(client.collection("matches")._docs) == 1
    assert len(client.collection("player_stats")._docs) == 8


def test_match_exists_uses_where_query(fake_firestore_store):
    store, client = fake_firestore_store
    match, players = _docs()
    store.add_match(match, players)

    result = store.match_exists("hhh")
    assert result is True

    where_queries = client.collection("matches")._where_queries
    assert any(q["field"] == "image_hash" for q in where_queries)


def test_match_exists_false(fake_firestore_store):
    store, client = fake_firestore_store
    assert store.match_exists("nonexistent") is False
