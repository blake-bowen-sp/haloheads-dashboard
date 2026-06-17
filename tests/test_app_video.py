import io

import pytest

from app import app as flask_app
from haloheads.storage import LocalStorage
from haloheads.store import SqliteStore


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "bucket"))
    monkeypatch.setenv("STORE_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "stats.db"))
    monkeypatch.setenv("HALOHEADS_FAKE_GEMINI", "1")  # inline fake multi-tab, no API key
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def _post_video(client, data=b"VIDEOBYTES", filename="clip.mp4", content_type="video/mp4"):
    return client.post(
        "/upload",
        data={"image": (io.BytesIO(data), filename, content_type)},
        content_type="multipart/form-data",
    )


def test_video_upload_analyzes_and_stores_tabs(client, tmp_path):
    r = _post_video(client)
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] == "analyzed"
    assert body["players"] == 8

    store = SqliteStore(str(tmp_path / "stats.db"))
    matches = store.all_matches()
    assert len(matches) == 1
    assert len(store.all_player_stats()) == 8

    m = store.get_match(matches[0]["match_id"])
    assert [t["name"] for t in m["tabs"]] == ["OVERVIEW", "DETAILED STATS"]

    storage = LocalStorage(str(tmp_path / "bucket"))
    assert storage.list_pending() == []
    analyzed = sorted((tmp_path / "bucket" / "analyzed").glob("*.mp4"))
    assert len(analyzed) == 1


def test_api_matches_lists_tab_names(client):
    _post_video(client)
    r = client.get("/api/matches")
    assert r.status_code == 200
    matches = r.get_json()
    assert len(matches) == 1
    assert "OVERVIEW" in matches[0]["tab_names"]
    assert "DETAILED STATS" in matches[0]["tab_names"]
    assert matches[0]["players"] == 8


def test_api_match_returns_tabs(client):
    _post_video(client)
    mid = client.get("/api/matches").get_json()[0]["match_id"]
    r = client.get(f"/api/match/{mid}")
    assert r.status_code == 200
    tabs = r.get_json()["tabs"]
    assert tabs[1]["name"] == "DETAILED STATS"
    assert tabs[1]["players"][0]["stats"]["AVERAGE LIFE"] == "1:02"


def test_api_match_not_found(client):
    assert client.get("/api/match/nope").status_code == 404


def test_api_tab_career_excludes_overview(client):
    _post_video(client)
    career = client.get("/api/tab-career").get_json()
    assert "OVERVIEW" not in career
    cy = next(row for row in career["DETAILED STATS"]["rows"] if row["gamertag"] == "Cyborg800")
    assert cy["games"] == 1
    assert cy["stats"]["AVERAGE LIFE"] == "1:02"
