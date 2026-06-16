from pathlib import Path

import pytest

from tests.fixtures.carnage_blue import fake_extract, CARNAGE_BLUE
from tests.fixtures.carnage_red import CARNAGE_RED

_ROOT = Path(__file__).resolve().parents[1]
_BLUE_PATH = _ROOT / "gameStatsImageFiles" / "testTeamResultData.jpeg"
_RED_PATH = _ROOT / "gameStatsImageFiles" / "scoreboard.png"


def test_fake_extract_is_content_addressed():
    blue_bytes = _BLUE_PATH.read_bytes()
    red_bytes = _RED_PATH.read_bytes()

    result_blue = fake_extract(blue_bytes)
    result_red = fake_extract(red_bytes)

    assert result_blue != result_red

    blue_tags = {p.gamertag for p in result_blue.players}
    red_tags = {p.gamertag for p in result_red.players}
    assert blue_tags.isdisjoint(red_tags)


def test_pipeline_stores_different_stats_per_image(tmp_path, monkeypatch):
    from scripts import analyze
    from haloheads.storage import get_storage
    from haloheads.store import get_store

    def _run_pipeline(img_bytes, base_dir):
        monkeypatch.setenv("STORAGE_BACKEND", "local")
        monkeypatch.setenv("STORAGE_DIR", str(base_dir / "bucket"))
        monkeypatch.setenv("STORE_BACKEND", "sqlite")
        monkeypatch.setenv("SQLITE_PATH", str(base_dir / "stats.db"))
        monkeypatch.setenv("HALOHEADS_FAKE_EXTRACT", "1")

        storage = get_storage()
        storage.save_upload(img_bytes, "image/jpeg", {})
        analyze.main([])
        return {r["gamertag"] for r in get_store().all_player_stats()}

    blue_tags = _run_pipeline(_BLUE_PATH.read_bytes(), tmp_path / "blue")
    red_tags = _run_pipeline(_RED_PATH.read_bytes(), tmp_path / "red")

    assert blue_tags != red_tags
    assert "Cyborg800" in blue_tags
    assert "Cyborg800" not in red_tags
    assert "Snipe King" in red_tags
    assert "Snipe King" not in blue_tags
