import io
from pathlib import Path

import pytest

from app import app as flask_app
from haloheads.gemini import NotAScoreboard
from haloheads.storage import LocalStorage
from haloheads.store import SqliteStore
from tests.fixtures.carnage_blue import CARNAGE_BLUE


@pytest.fixture
def sample_bytes():
    root = Path(__file__).resolve().parents[1]
    return (root / "gameStatsImageFiles" / "testTeamResultData.jpeg").read_bytes()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "bucket"))
    monkeypatch.setenv("STORE_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "stats.db"))
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def _post_image(client, data: bytes, filename: str = "shot.jpg"):
    return client.post(
        "/upload",
        data={"image": (io.BytesIO(data), filename)},
        content_type="multipart/form-data",
    )


def test_analyze(client, tmp_path, monkeypatch, sample_bytes):
    monkeypatch.setattr("app.extract_with_gemini", lambda data: CARNAGE_BLUE)

    r = _post_image(client, sample_bytes)
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] == "analyzed"
    assert body["players"] == 8

    store = SqliteStore(str(tmp_path / "stats.db"))
    assert len(store.all_player_stats()) == 8
    assert len(store.all_matches()) == 1

    storage = LocalStorage(str(tmp_path / "bucket"))
    assert storage.list_pending() == []
    analyzed = sorted((tmp_path / "bucket" / "analyzed").glob("*.jpg"))
    assert len(analyzed) == 1


def test_duplicate_image(client, tmp_path, monkeypatch, sample_bytes):
    monkeypatch.setattr("app.extract_with_gemini", lambda data: CARNAGE_BLUE)

    r1 = _post_image(client, sample_bytes)
    assert r1.get_json()["status"] == "analyzed"

    r2 = _post_image(client, sample_bytes)
    assert r2.status_code == 200
    assert r2.get_json()["status"] == "duplicate_image"

    store = SqliteStore(str(tmp_path / "stats.db"))
    assert len(store.all_matches()) == 1


def test_duplicate_game(client, tmp_path, monkeypatch, sample_bytes):
    monkeypatch.setattr("app.extract_with_gemini", lambda data: CARNAGE_BLUE)

    r1 = _post_image(client, sample_bytes)
    assert r1.get_json()["status"] == "analyzed"

    different_bytes = sample_bytes + b"X"
    r2 = _post_image(client, different_bytes)
    assert r2.status_code == 200
    assert r2.get_json()["status"] == "duplicate_game"

    store = SqliteStore(str(tmp_path / "stats.db"))
    assert len(store.all_matches()) == 1
    assert len(store.all_player_stats()) == 8


def test_not_a_scoreboard(client, tmp_path, monkeypatch, sample_bytes):
    def raise_not_scoreboard(data):
        raise NotAScoreboard()

    monkeypatch.setattr("app.extract_with_gemini", raise_not_scoreboard)

    r = _post_image(client, sample_bytes)
    assert r.status_code == 200
    assert r.get_json()["status"] == "not_a_scoreboard"

    store = SqliteStore(str(tmp_path / "stats.db"))
    assert len(store.all_matches()) == 0
    assert len(store.all_player_stats()) == 0

    storage = LocalStorage(str(tmp_path / "bucket"))
    assert storage.list_pending() == []
    rejected = sorted((tmp_path / "bucket" / "rejected").glob("*.jpg"))
    assert len(rejected) == 1


def test_graceful_degrade(client, tmp_path, monkeypatch, sample_bytes):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    r = _post_image(client, sample_bytes)
    assert r.status_code == 200
    assert r.get_json()["status"] == "stored"

    store = SqliteStore(str(tmp_path / "stats.db"))
    assert len(store.all_matches()) == 0

    storage = LocalStorage(str(tmp_path / "bucket"))
    assert len(storage.list_pending()) == 1


def test_analysis_failed(client, tmp_path, monkeypatch, sample_bytes):
    def raise_runtime(data):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.extract_with_gemini", raise_runtime)

    r = _post_image(client, sample_bytes)
    assert r.status_code == 200
    assert r.get_json()["status"] == "analysis_failed"

    store = SqliteStore(str(tmp_path / "stats.db"))
    assert len(store.all_matches()) == 0

    storage = LocalStorage(str(tmp_path / "bucket"))
    assert len(storage.list_pending()) == 1
