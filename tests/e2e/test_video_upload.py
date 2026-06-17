"""End-to-end: the real Upload button accepts a video, the inline (faked) Gemini
path extracts tabs, and the dashboard renders the leaderboard, the career-by-tab
panels, and per-match tab pages. Real clicks, real DOM assertions, no skips.

HALOHEADS_FAKE_GEMINI=1 makes the inline /upload path return a deterministic
multi-tab report (no API key), so this drives the same code prod runs.
"""
import threading
from pathlib import Path

import pytest
from werkzeug.serving import make_server

SAMPLE = str(Path(__file__).resolve().parents[1] / "fixtures" / "multitab_sample.mp4")


@pytest.fixture
def live_server(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "bucket"))
    monkeypatch.setenv("STORE_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "stats.db"))
    monkeypatch.setenv("HALOHEADS_FAKE_GEMINI", "1")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from app import app as flask_app
    server = make_server("127.0.0.1", 0, flask_app)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def _enter(page):
    # The ENTER splash overlays the dashboard until tapped; dismiss it so the content
    # underneath is interactive (otherwise clicks land on the splash).
    page.wait_for_selector("#loader", state="hidden", timeout=25000)
    page.click("#splash")
    page.wait_for_function(
        "() => document.getElementById('splash').classList.contains('gone')", timeout=5000
    )


def test_video_upload_renders_tab_pages(live_server, page):
    page.goto(live_server)
    _enter(page)

    # 1. Drive the real top-right Upload button's hidden input with a video file.
    page.set_input_files("#up-input", SAMPLE)
    page.wait_for_function(
        "() => /Uploaded/.test(document.querySelector('label.up').textContent)",
        timeout=20000,
    )

    # 2. Reload; the OVERVIEW tab feeds the existing leaderboard.
    page.goto(live_server)
    _enter(page)
    page.wait_for_selector("#leaderboard tbody tr", timeout=15000)
    assert "Cyborg800" in page.inner_text("#leaderboard")

    # 3. Career-by-tab shows the extra (non-OVERVIEW) tab with its columns.
    page.wait_for_selector("#tab-career .panel", timeout=15000)
    career = page.inner_text("#tab-career")
    assert "DETAILED STATS" in career
    assert "AVERAGE LIFE" in career

    # 4. Matches list -> click a match -> per-tab pages render (OVERVIEW + DETAILED).
    page.wait_for_selector("#matches .mrow", timeout=15000)
    page.click("#matches .mrow")
    page.wait_for_selector("#match-detail .tabbtn", timeout=15000)
    detail = page.inner_text("#match-detail")
    assert "OVERVIEW" in detail
    assert "DETAILED STATS" in detail
