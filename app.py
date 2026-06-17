import os
from datetime import datetime, timezone
from uuid import uuid4

from flask import Flask, jsonify, make_response, render_template, request

from haloheads.docs import build_docs
from haloheads.gemini import NotAScoreboard, extract_with_gemini, get_video_extractor
from haloheads.schema import canonical_report, image_hash, overview_tab, tabs_to_dicts
from haloheads.storage import get_storage
from haloheads.store import get_store
from haloheads.aggregate import leaderboard, mvps, by_gametype, tab_career

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024


@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "file too large"}), 413


@app.route("/")
def dashboard():
    # The page carries its JS inline, so never let a stale HTML get cached — always
    # revalidate. (The big static assets keep their own long cache.) Stops the
    # "Enter looks broken because the browser is running an old build" trap.
    resp = make_response(render_template("dashboard.html"))
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("image")
    if file is None:
        return jsonify({"error": "no image"}), 400

    data = file.read()
    uploaded_at = datetime.now(timezone.utc).isoformat()
    meta = {
        "uploaded_at": uploaded_at,
        "map": request.form.get("map") or None,
        "uploader": request.form.get("uploader") or None,
    }

    storage = get_storage()
    store = get_store()
    mime_type = file.mimetype or "image/jpeg"
    key = storage.save_upload(data, mime_type, meta)

    if not os.environ.get("GEMINI_API_KEY") and os.environ.get("HALOHEADS_FAKE_GEMINI") != "1":
        return jsonify({"ok": True, "key": key, "status": "stored"})

    h = image_hash(data)
    if store.match_exists(h):
        storage.move(key, "analyzed/")
        return jsonify({"ok": True, "key": key, "status": "duplicate_image"})

    try:
        if mime_type.startswith("video/"):
            multi = get_video_extractor()(data, mime_type=mime_type)
            report = canonical_report(multi)
            tabs = tabs_to_dicts(multi.tabs)
        else:
            report = extract_with_gemini(data)
            tabs = tabs_to_dicts([overview_tab(report)])
    except NotAScoreboard:
        storage.move(key, "rejected/")
        return jsonify({"ok": True, "key": key, "status": "not_a_scoreboard"})
    except Exception:
        app.logger.exception("gemini analysis failed")
        return jsonify({"ok": True, "key": key, "status": "analysis_failed"})

    if all(p.score == 0 and p.kills == 0 and p.assists == 0 and p.deaths == 0 for p in report.players):
        storage.move(key, "review/")
        return jsonify({"ok": True, "key": key, "status": "no_readable_stats"})

    now = datetime.now(timezone.utc).isoformat()
    match, players = build_docs(
        report,
        match_id=uuid4().hex,
        source_image=key,
        img_hash=h,
        uploaded_at=uploaded_at,
        analyzed_at=now,
        tabs=tabs,
    )

    if store.game_exists(match["game_hash"]):
        storage.move(key, "analyzed/")
        return jsonify({"ok": True, "key": key, "status": "duplicate_game"})

    store.add_match(match, players)
    storage.move(key, "analyzed/")
    return jsonify({
        "ok": True,
        "key": key,
        "status": "analyzed",
        "players": len(players),
        "winning_team": report.winning_team,
        "gametype": report.gametype,
    })


@app.route("/api/leaderboard")
def api_leaderboard():
    return jsonify(leaderboard(get_store().all_player_stats()))


@app.route("/api/mvps")
def api_mvps():
    store = get_store()
    return jsonify(mvps(store.all_matches(), store.all_player_stats()))


@app.route("/api/gametypes")
def api_gametypes():
    return jsonify(by_gametype(get_store().all_player_stats()))


@app.route("/api/player/<gamertag>")
def api_player(gamertag):
    rows = [r for r in get_store().all_player_stats() if r["gamertag"] == gamertag]
    return jsonify({"gamertag": gamertag, "games": len(rows), "rows": rows})


def _player_count(tabs):
    overview = next((t for t in tabs if (t.get("name") or "").upper() == "OVERVIEW"), None)
    chosen = overview or (tabs[0] if tabs else None)
    return len(chosen.get("players") or []) if chosen else 0


@app.route("/api/matches")
def api_matches():
    out = []
    for m in get_store().recent_matches(100):
        tabs = m.get("tabs") or []
        out.append({
            "match_id": m["match_id"],
            "gametype": m.get("gametype"),
            "map": m.get("map"),
            "winning_team": m.get("winning_team"),
            "uploaded_at": m.get("uploaded_at"),
            "tab_names": [t.get("name") for t in tabs],
            "players": _player_count(tabs),
        })
    return jsonify(out)


@app.route("/api/match/<match_id>")
def api_match(match_id):
    m = get_store().get_match(match_id)
    if m is None:
        return jsonify({"error": "not found"}), 404
    return jsonify({
        "match_id": m["match_id"],
        "gametype": m.get("gametype"),
        "map": m.get("map"),
        "winning_team": m.get("winning_team"),
        "uploaded_at": m.get("uploaded_at"),
        "tabs": m.get("tabs") or [],
    })


@app.route("/api/tab-career")
def api_tab_career():
    return jsonify(tab_career(get_store().recent_matches(10000)))


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
