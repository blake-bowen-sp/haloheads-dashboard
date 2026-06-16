import pytest
from dataclasses import asdict

from haloheads.extraction import extract_carnage_report, get_extractor
from haloheads.schema import CarnageReport
from tests.fixtures.carnage_blue import CARNAGE_BLUE


class _FakeBlock:
    def __init__(self, type, name=None, input=None):
        self.type = type
        self.name = name
        self.input = input


class _FakeResp:
    def __init__(self, content):
        self.content = content


class _FakeMessages:
    def __init__(self, resp):
        self._resp = resp

    def create(self, **kwargs):
        self._kwargs = kwargs
        return self._resp


class _FakeClient:
    def __init__(self, resp):
        self.messages = _FakeMessages(resp)


def test_happy_path(sample_image_bytes):
    golden_dict = asdict(CARNAGE_BLUE)
    # asdict converts PlayerRow list to list of dicts, but validate_report expects
    # "players" key with list of dicts — that's exactly what asdict gives us.
    fake_resp = _FakeResp([
        _FakeBlock("text"),
        _FakeBlock("tool_use", "record_carnage_report", golden_dict),
    ])
    fake = _FakeClient(fake_resp)

    result = extract_carnage_report(sample_image_bytes, client=fake)

    assert isinstance(result, CarnageReport)
    assert result == CARNAGE_BLUE
    assert len(result.players) == 8
    assert result.winning_team == "BLUE"
    cyborg = next(p for p in result.players if p.gamertag == "Cyborg800")
    assert cyborg.kills == 19


def test_request_shape(sample_image_bytes):
    golden_dict = asdict(CARNAGE_BLUE)
    fake_resp = _FakeResp([
        _FakeBlock("tool_use", "record_carnage_report", golden_dict),
    ])
    fake = _FakeClient(fake_resp)

    extract_carnage_report(sample_image_bytes, client=fake)

    kwargs = fake.messages._kwargs
    assert kwargs["tool_choice"] == {"type": "tool", "name": "record_carnage_report"}

    content = kwargs["messages"][0]["content"]
    types = [b["type"] for b in content]
    assert "image" in types
    assert "text" in types

    image_block = next(b for b in content if b["type"] == "image")
    assert image_block["source"]["media_type"] == "image/jpeg"
    assert len(image_block["source"]["data"]) > 0


def test_no_tool_use_raises(sample_image_bytes):
    fake_resp = _FakeResp([_FakeBlock("text")])
    fake = _FakeClient(fake_resp)

    with pytest.raises(ValueError, match="no tool_use block in response"):
        extract_carnage_report(sample_image_bytes, client=fake)


def test_get_extractor_fake(monkeypatch, sample_image_bytes):
    monkeypatch.setenv("HALOHEADS_FAKE_EXTRACT", "1")
    extractor = get_extractor()
    result = extractor(sample_image_bytes)
    assert isinstance(result, CarnageReport)


def test_get_extractor_real(monkeypatch):
    monkeypatch.delenv("HALOHEADS_FAKE_EXTRACT", raising=False)
    extractor = get_extractor()
    assert extractor is extract_carnage_report
