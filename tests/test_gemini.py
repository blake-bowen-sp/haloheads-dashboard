import dataclasses
import json
from unittest.mock import MagicMock

import pytest

from haloheads.gemini import NotAScoreboard, extract_with_gemini
from tests.fixtures.carnage_blue import CARNAGE_BLUE


def _fake_response(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]
    }
    return resp


def test_extract_returns_carnage_report(monkeypatch):
    payload = {**dataclasses.asdict(CARNAGE_BLUE), "is_scoreboard": True}

    monkeypatch.setattr("haloheads.gemini.requests.post", lambda *a, **kw: _fake_response(payload))

    report = extract_with_gemini(b"img", api_key="x")
    assert len(report.players) == 8
    assert report.winning_team == "BLUE"
    assert report.gametype == "LEGENDARY SLAYER BR"


def test_extract_raises_not_a_scoreboard(monkeypatch):
    payload = {"is_scoreboard": False, "players": []}

    monkeypatch.setattr("haloheads.gemini.requests.post", lambda *a, **kw: _fake_response(payload))

    with pytest.raises(NotAScoreboard):
        extract_with_gemini(b"img", api_key="x")


def test_extract_raises_not_a_scoreboard_empty_players(monkeypatch):
    payload = {"is_scoreboard": True, "players": []}

    monkeypatch.setattr("haloheads.gemini.requests.post", lambda *a, **kw: _fake_response(payload))

    with pytest.raises(NotAScoreboard):
        extract_with_gemini(b"img", api_key="x")
