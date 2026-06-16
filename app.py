from flask import Flask, request, jsonify, render_template
from datetime import datetime, timezone
from haloheads.storage import get_storage
from haloheads.store import get_store
from haloheads.aggregate import leaderboard, mvps, by_gametype

app = Flask(__name__)


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
    key = get_storage().save_upload(
        data,
        file.mimetype or "image/jpeg",
        {
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "map": request.form.get("map") or None,
            "uploader": request.form.get("uploader") or None,
        },
    )
    return jsonify({"ok": True, "key": key})


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
