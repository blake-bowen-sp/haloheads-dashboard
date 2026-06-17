import json
from unittest.mock import MagicMock

import pytest

from haloheads.gemini import NotAScoreboard, extract_tabs_from_video, get_video_extractor
from haloheads.schema import MultiTabReport

MULTITAB_PAYLOAD = {
    "is_scoreboard": True,
    "winning_team": "BLUE",
    "gametype": "SLAYER",
    "map": None,
    "tabs": [
        {"name": "OVERVIEW", "columns": ["SCORE", "KILLS", "ASSISTS", "DEATHS"], "players": [
            {"gamertag": "Cyborg800", "clan_tag": "4039", "team": "BLUE",
             "stats": {"SCORE": 250, "KILLS": 19, "ASSISTS": 5, "DEATHS": 4}}]},
        {"name": "DETAILED STATS", "columns": ["AVERAGE LIFE", "SPREAD"], "players": [
            {"gamertag": "Cyborg800", "clan_tag": "4039", "team": "BLUE",
             "stats": {"AVERAGE LIFE": "0:58", "SPREAD": 15}}]},
    ],
}


class FakeHTTP:
    """Canned File-API + generateContent responses; records every request."""

    def __init__(self, payload, upload_state="ACTIVE"):
        self.payload = payload
        self.upload_state = upload_state
        self.posts = []
        self.gets = []

    def post(self, url, **kw):
        self.posts.append((url, kw))
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        if "/upload/v1beta/files" in url:
            resp.headers = {"X-Goog-Upload-URL": "https://upload.example/u1"}
            resp.json.return_value = {}
        elif url == "https://upload.example/u1":
            resp.json.return_value = {"file": {
                "name": "files/abc", "uri": "https://files.example/abc", "state": self.upload_state}}
        elif ":generateContent" in url:
            resp.json.return_value = {
                "candidates": [{"content": {"parts": [{"text": json.dumps(self.payload)}]}}]}
        else:
            raise AssertionError(f"unexpected POST {url}")
        return resp

    def get(self, url, **kw):
        self.gets.append((url, kw))
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "name": "files/abc", "uri": "https://files.example/abc", "state": "ACTIVE"}
        return resp


def _patch(monkeypatch, http):
    monkeypatch.setattr("haloheads.gemini.requests.post", http.post)
    monkeypatch.setattr("haloheads.gemini.requests.get", http.get)


def test_extract_tabs_from_video_returns_multitab(monkeypatch):
    http = FakeHTTP(MULTITAB_PAYLOAD)
    _patch(monkeypatch, http)
    multi = extract_tabs_from_video(b"VIDEOBYTES", mime_type="video/mp4", api_key="x")
    assert isinstance(multi, MultiTabReport)
    assert [t.name for t in multi.tabs] == ["OVERVIEW", "DETAILED STATS"]
    assert multi.tabs[0].players[0].gamertag == "Cyborg800"
    assert multi.tabs[1].players[0].stats["AVERAGE LIFE"] == "0:58"


def test_video_request_uses_file_uri_fps_and_media_resolution(monkeypatch):
    http = FakeHTTP(MULTITAB_PAYLOAD)
    _patch(monkeypatch, http)
    extract_tabs_from_video(b"VIDEOBYTES", mime_type="video/quicktime", api_key="x", fps=5)
    gen = next(kw for url, kw in http.posts if ":generateContent" in url)
    part = gen["json"]["contents"][0]["parts"][0]
    assert part["file_data"]["file_uri"] == "https://files.example/abc"
    assert part["file_data"]["mime_type"] == "video/quicktime"
    assert part["video_metadata"]["fps"] == 5
    assert gen["json"]["generationConfig"]["mediaResolution"] == "MEDIA_RESOLUTION_HIGH"
    assert gen["json"]["generationConfig"]["responseMimeType"] == "application/json"


def test_video_upload_sends_content_type_and_length(monkeypatch):
    http = FakeHTTP(MULTITAB_PAYLOAD)
    _patch(monkeypatch, http)
    extract_tabs_from_video(b"ABCDE", mime_type="video/mp4", api_key="x")
    start = next(kw for url, kw in http.posts if "/upload/v1beta/files" in url)
    assert start["headers"]["X-Goog-Upload-Header-Content-Type"] == "video/mp4"
    assert start["headers"]["X-Goog-Upload-Header-Content-Length"] == "5"


def test_video_polls_until_active(monkeypatch):
    http = FakeHTTP(MULTITAB_PAYLOAD, upload_state="PROCESSING")
    _patch(monkeypatch, http)
    multi = extract_tabs_from_video(b"V", mime_type="video/mp4", api_key="x", poll_interval=0)
    assert isinstance(multi, MultiTabReport)
    assert len(http.gets) >= 1


def test_video_not_a_scoreboard(monkeypatch):
    http = FakeHTTP({"is_scoreboard": False, "tabs": []})
    _patch(monkeypatch, http)
    with pytest.raises(NotAScoreboard):
        extract_tabs_from_video(b"V", mime_type="video/mp4", api_key="x")


def test_get_video_extractor_fake(monkeypatch):
    monkeypatch.setenv("HALOHEADS_FAKE_GEMINI", "1")
    extractor = get_video_extractor()
    multi = extractor(b"anything", mime_type="video/mp4")
    assert isinstance(multi, MultiTabReport)
    assert len(multi.tabs) >= 2
