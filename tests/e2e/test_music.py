"""
End-to-end browser test for the menu<->battle music crossfade.

Drives the real UI a user touches: the page loads, the music control appears in the
header, the equal-power crossfade is *locked to scroll position* (choral on the Sniper,
battle riff on the Warthog -> Crew), the first scroll starts playback, the toggle mutes,
and the mute choice persists across reloads via localStorage.

A committed silent .mp3 stands in for the (git-ignored) real tracks, so the suite needs
no copyrighted audio. The crossfade assertions read each <audio> element's live `.volume`
straight off the same scroll signal that drives the 3D dissolve -- a semantic check that
scrolling actually moves the music, not just that some audio element exists.
"""
import threading
from pathlib import Path

import pytest
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parents[2]
SILENT = Path(__file__).parent / "fixtures" / "silent.mp3"

MENU = "document.getElementById('snd-menu')"
BATTLE = "document.getElementById('snd-battle')"


@pytest.fixture
def live_server(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "bucket"))
    monkeypatch.setenv("STORE_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "stats.db"))
    from app import app as flask_app

    server = make_server("127.0.0.1", 0, flask_app)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture
def ensure_audio():
    # The real tracks are git-ignored; stand in a silent clip wherever one is missing
    # so the <audio> elements decode and the control un-hides. Only clean up what we made.
    audio_dir = ROOT / "static" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    created = []
    for name in ("menu.mp3", "battle.mp3"):
        f = audio_dir / name
        if not f.exists():
            f.write_bytes(SILENT.read_bytes())
            created.append(f)
    yield
    for f in created:
        f.unlink(missing_ok=True)


def _ready(page):
    # The control stays [hidden] until both tracks decode; visible == music wired up.
    page.wait_for_selector("#snd-toggle:not([hidden])", timeout=15000)


def test_music_control_appears_unmuted(live_server, ensure_audio, page):
    page.goto(live_server)
    _ready(page)
    assert page.get_attribute("#snd-toggle", "aria-pressed") == "true"


def test_crossfade_is_locked_to_scroll(live_server, ensure_audio, page):
    page.goto(live_server)
    _ready(page)

    # Top of page (Sniper): pure choral -- menu near the ceiling, battle silent.
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_function(
        f"() => {MENU}.volume > 0.40 && {BATTLE}.volume < 0.02", timeout=10000
    )

    # Scrolled past the Sniper->Warthog dissolve: the riff takes over, choral is gone.
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_function(
        f"() => {BATTLE}.volume > 0.40 && {MENU}.volume < 0.02", timeout=10000
    )

    # Back up: it crossfades the other way -- proves it tracks scroll, not a one-shot.
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_function(
        f"() => {MENU}.volume > 0.40 && {BATTLE}.volume < 0.02", timeout=10000
    )


def test_music_starts_on_scroll(live_server, ensure_audio, page):
    page.goto(live_server)
    _ready(page)
    assert page.evaluate(f"{MENU}.paused") is True  # nothing plays until the user acts
    page.mouse.wheel(0, 900)  # the real trigger
    page.wait_for_function(
        f"() => !{MENU}.paused && !{BATTLE}.paused", timeout=10000
    )


def test_mute_toggles_and_persists(live_server, ensure_audio, page):
    page.goto(live_server)
    _ready(page)

    page.click("#snd-toggle")
    page.wait_for_function(f"() => {MENU}.muted && {BATTLE}.muted", timeout=5000)
    assert page.evaluate("localStorage.getItem('hh-muted')") == "1"
    assert "muted" in (page.get_attribute("#snd-toggle", "class") or "")

    # Reload in the same context: the muted choice sticks.
    page.goto(live_server)
    _ready(page)
    assert page.evaluate(f"{MENU}.muted") is True
    assert page.get_attribute("#snd-toggle", "aria-pressed") == "false"
