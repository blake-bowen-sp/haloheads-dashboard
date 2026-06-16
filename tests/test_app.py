import io
import pytest
from app import app as flask_app
from haloheads.docs import build_docs
from haloheads.store import SqliteStore
from tests.fixtures.carnage_blue import CARNAGE_BLUE


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "bucket"))
    monkeypatch.setenv("STORE_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "stats.db"))
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}


def test_upload_stores_image(client, tmp_path, monkeypatch, sample_image_bytes):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "bucket"))
    r = client.post(
        "/upload",
        data={"image": (io.BytesIO(sample_image_bytes), "shot.jpg"), "map": "Lockout"},
        content_type="multipart/form-data",
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["key"].startswith("pending/")

    from haloheads.storage import get_storage
    pending = get_storage().list_pending()
    assert len(pending) == 1


def test_upload_requires_image(client):
    r = client.post("/upload", data={}, content_type="multipart/form-data")
    assert r.status_code == 400
    assert r.get_json()["error"] == "no image"


def test_upload_too_large(client):
    original = flask_app.config["MAX_CONTENT_LENGTH"]
    flask_app.config["MAX_CONTENT_LENGTH"] = 50
    try:
        r = client.post(
            "/upload",
            data={"image": (io.BytesIO(b"x" * 500), "big.jpg")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 413
        assert r.get_json()["error"] == "file too large"
    finally:
        flask_app.config["MAX_CONTENT_LENGTH"] = original


def test_leaderboard(client, tmp_path, monkeypatch):
    monkeypatch.setenv("STORE_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "stats.db"))
    store = SqliteStore(str(tmp_path / "stats.db"))
    match, players = build_docs(
        CARNAGE_BLUE,
        match_id="m1",
        source_image="x",
        img_hash="h",
        uploaded_at="t",
        analyzed_at="t",
    )
    store.add_match(match, players)

    r = client.get("/api/leaderboard")
    assert r.status_code == 200
    data = r.get_json()
    assert data[0]["gamertag"] == "Cyborg800"


def test_mvps(client, tmp_path, monkeypatch):
    monkeypatch.setenv("STORE_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "stats.db"))
    store = SqliteStore(str(tmp_path / "stats.db"))
    match, players = build_docs(
        CARNAGE_BLUE,
        match_id="m1",
        source_image="x",
        img_hash="h",
        uploaded_at="t",
        analyzed_at="t",
    )
    store.add_match(match, players)

    r = client.get("/api/mvps")
    assert r.status_code == 200
    data = r.get_json()
    blue_mvp = next(e for e in data if e["team"] == "BLUE")
    red_mvp = next(e for e in data if e["team"] == "RED")
    assert blue_mvp == {"match_id": "m1", "team": "BLUE", "gamertag": "Cyborg800", "score": 250}
    assert red_mvp == {"match_id": "m1", "team": "RED", "gamertag": "ELIMINADOR", "score": 195}
