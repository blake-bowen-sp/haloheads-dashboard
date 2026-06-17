"""
End-to-end browser tests for the ENTER splash + menu<->battle music crossfade.

The splash is the fix for autoplay: the "ENTER" tap is the user gesture that unlocks
audio (the only thing that works on mobile Safari). Flow: load -> splash visible ->
tap ENTER -> audio starts, control appears, the dashboard transitions in -> scrolling
drives the equal-power crossfade (choral on the Sniper, battle riff on Warthog->Crew).

`test_mobile_tap_enter_starts_audio` runs the same path under iPhone emulation (touch).
`test_enter_recovers_if_first_play_blocked` simulates a rejected first play() so the
control can still recover it. A committed silent .mp3 stands in for the git-ignored real
tracks, so the suite needs no copyrighted audio.
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
    # so the <audio> elements decode. Only clean up what we made.
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


def _enter(page):
    page.wait_for_selector("#loader", state="hidden", timeout=25000)  # full preload (shaders + audio) before the splash is interactable
    page.click("#splash")  # tap ENTER
    page.wait_for_selector("#snd-toggle:not([hidden])", timeout=10000)


def test_splash_then_enter_starts_audio(live_server, ensure_audio, page):
    page.goto(live_server)
    page.wait_for_selector("#loader", state="hidden", timeout=25000)
    # before entering: nothing plays, control hidden
    assert page.evaluate(f"{MENU}.paused") is True
    assert page.is_hidden("#snd-toggle")

    page.click("#splash")
    page.wait_for_selector("#snd-toggle:not([hidden])", timeout=10000)
    page.wait_for_function(
        "() => document.getElementById('splash').classList.contains('gone')", timeout=5000
    )
    page.wait_for_function(f"() => !{MENU}.paused && !{BATTLE}.paused", timeout=8000)
    t1 = page.evaluate(f"{MENU}.currentTime")
    page.wait_for_timeout(700)
    assert page.evaluate(f"{MENU}.currentTime") > t1 + 0.3  # genuinely advancing


def test_crossfade_is_locked_to_scroll(live_server, ensure_audio, page):
    page.goto(live_server)
    _enter(page)

    page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
    page.wait_for_function(
        f"() => {MENU}.volume > 0.40 && {BATTLE}.volume < 0.02", timeout=10000
    )
    page.evaluate("window.scrollTo({top: document.body.scrollHeight, behavior: 'instant'})")
    page.wait_for_function(
        f"() => {BATTLE}.volume > 0.40 && {MENU}.volume < 0.02", timeout=10000
    )
    page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
    page.wait_for_function(
        f"() => {MENU}.volume > 0.40 && {BATTLE}.volume < 0.02", timeout=10000
    )


def test_crossfade_overlaps(live_server, ensure_audio, page):
    page.goto(live_server)
    _enter(page)
    # gains track mesh-reveal, so somewhere mid-transition BOTH tracks are audible at once
    mx = page.evaluate("document.documentElement.scrollHeight - innerHeight")
    saw_overlap = False
    for i in range(41):
        page.evaluate(f"window.scrollTo({{top: {mx}*{i / 40}, behavior: 'instant'}})")
        page.wait_for_timeout(60)
        if page.evaluate(f"{MENU}.volume") > 0.1 and page.evaluate(f"{BATTLE}.volume") > 0.1:
            saw_overlap = True
            break
    assert saw_overlap, "tracks never overlap -- the crossfade is not blending"


def test_splash_locks_scroll_and_hides_content(live_server, ensure_audio, page):
    # The bug the empty-data tests missed: with real content, scrolling behind the splash
    # bled the leaderboard through the void. The splash must hide ALL content + lock scroll.
    page.goto(live_server)
    page.wait_for_selector("#loader", state="hidden", timeout=25000)
    op = page.evaluate(
        "() => { const o = s => { const el = document.querySelector(s);"
        " return el ? +getComputedStyle(el).opacity : 1; };"
        " return { header:o('header'), hero:o('.hero'), main:o('main'), bottom:o('.bottom'), crew:o('.crew') }; }"
    )
    assert all(v == 0 for v in op.values()), f"content visible during splash: {op}"
    page.mouse.move(400, 400)
    page.mouse.wheel(0, 2000)
    page.wait_for_timeout(300)
    assert page.evaluate("Math.round(scrollY)") == 0, "page scrolled behind the splash"
    # after ENTER the content is revealed
    page.click("#splash")
    page.wait_for_selector("#snd-toggle:not([hidden])", timeout=10000)
    page.wait_for_function(
        "() => +getComputedStyle(document.querySelector('main')).opacity === 1", timeout=5000
    )


def test_toggle_mutes_after_enter_and_persists(live_server, ensure_audio, page):
    page.goto(live_server)
    _enter(page)
    page.wait_for_function(f"() => !{MENU}.paused", timeout=8000)  # ENTER already started it

    page.click("#snd-toggle")  # now mutes
    page.wait_for_function(f"() => {MENU}.muted && {BATTLE}.muted", timeout=5000)
    assert page.evaluate("localStorage.getItem('hh-muted')") == "1"
    assert page.get_attribute("#snd-toggle", "aria-pressed") == "false"

    # reload + enter again: the muted choice sticks
    page.goto(live_server)
    _enter(page)
    assert page.evaluate(f"{MENU}.muted") is True
    assert page.get_attribute("#snd-toggle", "aria-pressed") == "false"


def test_enter_recovers_if_first_play_blocked(live_server, ensure_audio, page):
    # First play() pair (ENTER's) is rejected; the control must still recover it.
    page.add_init_script(
        "(() => { const o = HTMLMediaElement.prototype.play; let c = 0;"
        " HTMLMediaElement.prototype.play = function(){ c++;"
        "   if (c <= 2) return Promise.reject(new DOMException('blocked','NotAllowedError'));"
        "   return o.apply(this, arguments); }; })()"
    )
    page.goto(live_server)
    _enter(page)
    page.wait_for_timeout(300)
    assert page.evaluate(f"{MENU}.paused") is True  # ENTER's play() was rejected, not stuck
    page.click("#snd-toggle")  # control retries -> succeeds
    page.wait_for_function(f"() => !{MENU}.paused && !{BATTLE}.paused", timeout=8000)


def test_mobile_tap_enter_starts_audio(live_server, ensure_audio, browser, playwright):
    # Same path under iPhone emulation (touch) -- the case that motivated the splash.
    ctx = browser.new_context(**playwright.devices["iPhone 13"])
    try:
        page = ctx.new_page()
        page.goto(live_server)
        page.wait_for_selector("#loader", state="hidden", timeout=25000)
        assert page.evaluate(f"{MENU}.paused") is True
        page.tap("#splash")  # a real touch unlocks audio
        page.wait_for_selector("#snd-toggle:not([hidden])", timeout=10000)
        page.wait_for_function(f"() => !{MENU}.paused", timeout=8000)
        t1 = page.evaluate(f"{MENU}.currentTime")
        page.wait_for_timeout(600)
        assert page.evaluate(f"{MENU}.currentTime") > t1  # advancing on mobile
    finally:
        ctx.close()
