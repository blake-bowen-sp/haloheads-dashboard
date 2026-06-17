"""
End-to-end browser test: the dashboard's top-right Upload button -> native
multi-file <input> -> POST /upload -> analyzer -> assert the leaderboard renders.

Drives the real UI path a user touches. The Upload button is a <label> bound to a
hidden multi-file <input>; there is no separate upload page anymore. The Flask app
runs in a background thread sharing this process so env vars and temp paths are
shared between the test, server, and analyzer.
"""
import threading
import time
from pathlib import Path

import pytest
from werkzeug.serving import make_server

from haloheads.storage import get_storage


@pytest.fixture
def live_server(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "bucket"))
    monkeypatch.setenv("STORE_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "stats.db"))
    monkeypatch.setenv("HALOHEADS_FAKE_EXTRACT", "1")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("HALOHEADS_FAKE_GEMINI", raising=False)
    from app import app as flask_app
    server = make_server("127.0.0.1", 0, flask_app)
    port = server.server_port
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def _wait_pending(n, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        if len(get_storage().list_pending()) >= n:
            return
        time.sleep(0.2)
    raise AssertionError(
        f"expected >= {n} pending uploads, got {len(get_storage().list_pending())}"
    )


def test_dashboard_upload_button(live_server, page, sample_image_path):
    # 1. Open the dashboard and drive the real top-right Upload button's hidden input.
    page.goto(live_server)
    page.set_input_files("#up-input", str(sample_image_path))   # fires change -> POST /upload

    # 2. The button reflects progress, and the POST lands server-side (env shared in-process).
    page.wait_for_function(
        "() => /Upload(ing|ed)/.test(document.querySelector('label.up').textContent)",
        timeout=15000,
    )
    _wait_pending(1)

    # 3. Analyze the pending upload (FAKE_EXTRACT), reload, assert the leaderboard rendered.
    from scripts.analyze import main as analyze_main
    analyze_main([])
    page.goto(live_server)
    page.wait_for_selector("#leaderboard tbody tr", timeout=15000)
    body = page.inner_text("#leaderboard")
    assert "Cyborg800" in body
    assert "ELIMINADOR" in body


def test_dashboard_upload_multiple(live_server, page, sample_image_path):
    # Select two real files at once through the same multi-file input.
    second = Path(sample_image_path).parent / "scoreboard.png"
    page.goto(live_server)
    page.set_input_files("#up-input", [str(sample_image_path), str(second)])

    page.wait_for_function(
        "() => document.querySelector('label.up').textContent.includes('Uploaded 2')",
        timeout=20000,
    )
    _wait_pending(2)
    assert len(get_storage().list_pending()) == 2
