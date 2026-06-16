"""
End-to-end browser test: upload carnage report image -> analyze -> assert dashboard.

Uses a real Chromium browser (headless) via pytest-playwright.
The Flask app runs in a background thread sharing the same process so env vars
and temp paths are shared between the test, server, and analyzer.
"""
import threading

import pytest
from werkzeug.serving import make_server


@pytest.fixture
def live_server(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "bucket"))
    monkeypatch.setenv("STORE_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "stats.db"))
    monkeypatch.setenv("HALOHEADS_FAKE_EXTRACT", "1")
    from app import app as flask_app
    server = make_server("127.0.0.1", 0, flask_app)
    port = server.server_port
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def test_upload_then_dashboard(live_server, page, sample_image_path):
    # 1. Open the upload page, set the file input (real file), submit, assert success text.
    page.goto(f"{live_server}/upload")
    page.set_input_files("#file", str(sample_image_path))
    page.fill("#map", "Lockout")
    page.click("#submit")
    page.wait_for_selector("#result:has-text('Uploaded')", timeout=10000)

    # 2. Run the analyzer against the SAME temp backends (env is shared in-process).
    from scripts.analyze import main as analyze_main
    analyze_main([])

    # 3. Load the dashboard; assert the leaderboard rendered the extracted gamertags.
    page.goto(f"{live_server}/")
    page.wait_for_selector("#leaderboard tbody tr", timeout=10000)
    body = page.inner_text("#leaderboard")
    assert "Cyborg800" in body
    assert "ELIMINADOR" in body


def test_multi_upload(live_server, page, sample_image_path):
    from pathlib import Path
    from haloheads.storage import get_storage

    second = Path(sample_image_path).parent / "scoreboard.png"
    page.goto(f"{live_server}/upload")
    page.set_input_files("#file", [str(sample_image_path), str(second)])
    assert page.locator(".thumb").count() == 2
    page.click("#submit")
    page.wait_for_selector("#result:has-text('2/2')", timeout=15000)

    assert len(get_storage().list_pending()) == 2
