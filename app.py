import os
from datetime import datetime, timezone
from uuid import uuid4

from flask import Flask, jsonify, render_template, request

from haloheads.docs import build_docs
from haloheads.gemini import NotAScoreboard, extract_with_gemini
from haloheads.schema import image_hash
from haloheads.storage import get_storage
from haloheads.store import get_store
from haloheads.aggregate import leaderboard, mvps, by_gametype

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024


@app.errorhandler(413)
def too_large(e):
    return jsonify({"error": "file too large"}), 413


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/upload", methods=["GET"])
def upload_page():
    return render_template("upload.html")


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
    key = storage.save_upload(data, file.mimetype or "image/jpeg", meta)

    if not os.environ.get("GEMINI_API_KEY"):
        return jsonify({"ok": True, "key": key, "status": "stored"})

    h = image_hash(data)
    if store.match_exists(h):
        storage.move(key, "analyzed/")
        return jsonify({"ok": True, "key": key, "status": "duplicate_image"})

    try:
        report = extract_with_gemini(data)
    except NotAScoreboard:
        storage.move(key, "rejected/")
        return jsonify({"ok": True, "key": key, "status": "not_a_scoreboard"})
    except Exception:
        app.logger.exception("gemini analysis failed")
        return jsonify({"ok": True, "key": key, "status": "analysis_failed"})

    now = datetime.now(timezone.utc).isoformat()
    match, players = build_docs(
        report,
        match_id=uuid4().hex,
        source_image=key,
        img_hash=h,
        uploaded_at=uploaded_at,
        analyzed_at=now,
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


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
