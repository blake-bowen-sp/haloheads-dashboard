import base64
import json
import os

import requests

from .schema import CarnageReport, validate_report

DEFAULT_MODEL = "gemini-3.5-flash"

PROMPT = (
    "This is a photo of a video-game post-game scoreboard (Halo Master Chief Collection carnage report). "
    "Extract every player's stats. Use the row color for the team label (e.g. blue, red, green, gold). "
    "Keep the clan tag shown in [brackets] separate from the username. Map the visible columns to "
    "score, kills, assists, deaths when those columns are present; if a column is not shown, use null. "
    "The header states which team won and the gametype. "
    "If the image is NOT a game scoreboard (a random photo, a document, a book page, an unrelated screen), "
    'set is_scoreboard to false and players to []. Return ONLY JSON of the form: '
    '{"is_scoreboard": true, "winning_team": "GREEN", "gametype": "TEAM SLAYER", "map": null, '
    '"players": [{"gamertag": "Name", "clan_tag": "UNSC", "team": "GREEN", "score": 0, "kills": 0, '
    '"assists": 0, "deaths": 0}]}. Do not invent values you cannot read."'
)


class NotAScoreboard(Exception):
    pass


def extract_with_gemini(data: bytes, *, api_key: str | None = None, model: str | None = None) -> CarnageReport:
    api_key = api_key or os.environ["GEMINI_API_KEY"]
    model = model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
    b64 = base64.standard_b64encode(data).decode()
    body = {
        "contents": [{"parts": [
            {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
            {"text": PROMPT},
        ]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    resp = requests.post(url, json=body, timeout=120)
    resp.raise_for_status()
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    parsed = json.loads(text)
    if not parsed.get("is_scoreboard") or not parsed.get("players"):
        raise NotAScoreboard()
    return validate_report(parsed)
