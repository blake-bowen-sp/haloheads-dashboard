from flask import Flask, request, jsonify, render_template
from google.cloud import firestore
from google.cloud import storage
from datetime import datetime
import io, logging, re, uuid
from PIL import Image  # For optional downscaling

app = Flask(__name__)

db = firestore.Client()

def get_db():
    return firestore.Client()

def parse_player_stats(raw_text: str) -> dict:
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

    data = {}

    # Example: "Dec the Wise WON SLAYER"
    header_match = re.search(r"(.+?)\s+(WON|LOST)\s+(\w+)", raw_text)
    if header_match:
        data["gamertag"] = header_match.group(1)
        data["result"] = header_match.group(2)
        data["gametype"] = header_match.group(3)

    # Team: "(UNSC)"
    team_match = re.search(r"\(([^)]+)\)", raw_text)
    if team_match:
        data["team"] = team_match.group(1)

    # SCORE
    score_match = re.search(r"SCORE\s*(-?\d+)", raw_text)
    if score_match:
        data["score"] = int(score_match.group(1))

    # KILLS
    kills_match = re.search(r"KILLS\s*(\d+)", raw_text)
    if kills_match:
        data["kills"] = int(kills_match.group(1))

    # DEATHS
    deaths_match = re.search(r"DEATHS\s*(\d+)", raw_text)
    if deaths_match:
        data["deaths"] = int(deaths_match.group(1))

    data["gametime"] = datetime.now()

    return data

def parse_match_stats(raw_text: str):
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

    # -------------------------
    # Extract match header
    # -------------------------
    header_match = re.search(
        r"(BLUE TEAM|RED TEAM)\s+(WON|LOST)\s+(.+)",
        raw_text
    )

    if not header_match:
        raise ValueError("Could not parse match header")

    team = header_match.group(1)
    result = header_match.group(2)
    gametype = header_match.group(3).strip()

    # -------------------------
    # Extract player names
    # -------------------------
    player_section = raw_text.split("PLAYERS")[-1]

    # Grab names between brackets and next stat header
    player_names = re.findall(
        r"\]\n([A-Za-z0-9 xX]+)",
        player_section
    )

    # -------------------------
    # Extract stat numbers
    # -------------------------
    numbers = re.findall(r"\b\d+\b", raw_text)

    # Remove obvious non-stat numbers (like countdown 19 etc)
    numbers = [int(n) for n in numbers if int(n) > 20 or int(n) < 20]

    # We expect stat blocks of 4 numbers each:
    # score, kills, assists, deaths
    stat_blocks = []

    for i in range(0, len(numbers), 4):
        block = numbers[i:i+4]
        if len(block) == 4:
            stat_blocks.append(block)

    # Align players with stats
    players = []
    for i in range(min(len(player_names), len(stat_blocks))):
        score, kills, assists, deaths = stat_blocks[i]

        players.append({
            "gamertag": player_names[i],
            "team": team,
            "result": result,
            "gametype": gametype,
            "score": score,
            "kills": kills,
            "assists": assists,
            "deaths": deaths
        })

    return {
        "team": team,
        "result": result,
        "gametype": gametype,
        "players": players
    }


def write_match_to_firestore(raw_text: str):
    parsed = parse_match_stats(raw_text)

    match_id = datetime.utcnow().isoformat()

    # -------------------------
    # Write player documents
    # -------------------------
    for player in parsed["players"]:
        player["match_id"] = match_id

        db.collection("playerstats").add(player)

    # -------------------------
    # Compute team summary
    # -------------------------
    total_score = sum(p["score"] for p in parsed["players"])
    total_kills = sum(p["kills"] for p in parsed["players"])
    total_deaths = sum(p["deaths"] for p in parsed["players"])

    team_doc = {
        "team": parsed["team"],
        "result": parsed["result"],
        "gametype": parsed["gametype"],
        "total_score": total_score,
        "total_kills": total_kills,
        "total_deaths": total_deaths,
        "player_count": len(parsed["players"]),
        "match_id": match_id
    }

    db.collection("teamstats").add(team_doc)

    return {
        "players_written": len(parsed["players"]),
        "team_summary": team_doc
    }

def process_image_ocr(image_bytes):
    """
    Lazy-imports Vision client inside this function to avoid startup memory spikes.
    Optionally downscales image to reduce memory usage.
    """
    from google.cloud import vision  # Import inside function
    
    # Optional: downscale large images to ~1024x1024
    pil_image = Image.open(io.BytesIO(image_bytes))
    max_size = (1024, 1024)
    pil_image.thumbnail(max_size)
    
    buffer = io.BytesIO()
    pil_image.save(buffer, format="JPEG")
    downsized_bytes = buffer.getvalue()

    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=downsized_bytes)
    response = client.text_detection(image=image)

    if response.error.message:
        raise RuntimeError(response.error.message)

    texts = response.text_annotations
    return texts[0].description if texts else ""

@app.route("/generate-upload-url")
def generate_upload_url():
    storage_client = storage.Client()
    bucket = storage_client.bucket("haloheads-uploads")

    blob_name = f"uploads/{uuid.uuid4()}.jpg"
    blob = bucket.blob(blob_name)

    url = blob.generate_signed_url(
        version="v4",
        expiration=900,
        method="PUT",
        content_type="image/jpeg",
    )

    return jsonify({
        "upload_url": url,
        "file_path": blob_name
    })

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/api/playerstats")
def get_playerstats():
    docs = db.collection("playerstats").stream()

    players = []
    for doc in docs:
        data = doc.to_dict()
        players.append(data)

    return jsonify(players)

@app.route("/health")
def health():
    return {"status": "ok"}

@app.route("/ingest", methods=["POST"])
def ingest():
    if "image" not in request.files:
        return {"error": "no image uploaded"}, 400

    image_file = request.files["image"]
    image_bytes = image_file.read()

    try:
        raw_image_text = process_image_ocr(image_bytes)
    except Exception as e:
        logging.exception("OCR failed")
        return {"error": str(e)}, 500
    
    parsed_stats = write_match_to_firestore(raw_image_text)

    return jsonify({
    "raw_text": raw_image_text,
    "parsed_stats": parsed_stats
})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
