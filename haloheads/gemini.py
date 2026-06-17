import base64
import json
import os
import time

import requests

from .schema import CarnageReport, MultiTabReport, validate_multitab, validate_report

DEFAULT_MODEL = "gemini-3.5-flash"
GEN_BASE = "https://generativelanguage.googleapis.com"

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


PROMPT_TABS = (
    "This is a short video panning through the tabs of ONE Halo (Master Chief Collection) "
    "post-game carnage report. The player cycles the tabs with the bumper; the current tab's "
    "name is shown top-right (e.g. OVERVIEW, DETAILED STATS, MEDALS, ACCURACY). "
    "For EACH distinct tab that appears, read its name, its column headers, and every player's "
    "row. Use the row color for the team label (blue, red, green, gold). Keep the clan tag shown "
    "in [brackets] separate from the username. The header states which team won and the gametype. "
    "Return one entry per distinct tab (do not repeat a tab that appears in several frames; merge "
    "a player's identity across tabs by gamertag). Keep stat values exactly as shown — times like "
    "'0:58' stay strings, counts are integers. "
    "If the video is NOT a game scoreboard, set is_scoreboard to false and tabs to []. "
    'Return ONLY JSON of the form: {"is_scoreboard": true, "winning_team": "BLUE", '
    '"gametype": "TEAM SLAYER", "map": null, "tabs": [{"name": "OVERVIEW", '
    '"columns": ["SCORE","KILLS","ASSISTS","DEATHS"], "players": [{"gamertag": "Name", '
    '"clan_tag": "UNSC", "team": "BLUE", "stats": {"SCORE": 0, "KILLS": 0, "ASSISTS": 0, '
    '"DEATHS": 0}}]}]}. Do not invent values you cannot read.'
)


def _upload_video_file(data: bytes, mime_type: str, api_key: str) -> dict:
    start = requests.post(
        f"{GEN_BASE}/upload/v1beta/files?key={api_key}",
        headers={
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(len(data)),
            "X-Goog-Upload-Header-Content-Type": mime_type,
            "Content-Type": "application/json",
        },
        json={"file": {"display_name": "carnage_video"}},
        timeout=60,
    )
    start.raise_for_status()
    upload_url = start.headers["X-Goog-Upload-URL"]

    finalize = requests.post(
        upload_url,
        headers={
            "Content-Length": str(len(data)),
            "X-Goog-Upload-Offset": "0",
            "X-Goog-Upload-Command": "upload, finalize",
        },
        data=data,
        timeout=180,
    )
    finalize.raise_for_status()
    return finalize.json()["file"]


def _wait_active(name: str, api_key: str, poll_interval: float, max_polls: int) -> dict:
    for _ in range(max_polls):
        resp = requests.get(f"{GEN_BASE}/v1beta/{name}?key={api_key}", timeout=30)
        resp.raise_for_status()
        file_obj = resp.json()
        state = file_obj.get("state")
        if state == "ACTIVE":
            return file_obj
        if state == "FAILED":
            raise RuntimeError("Gemini video processing failed")
        time.sleep(poll_interval)
    raise RuntimeError("Gemini video did not become ACTIVE in time")


def extract_tabs_from_video(
    data: bytes,
    *,
    mime_type: str = "video/mp4",
    api_key: str | None = None,
    model: str | None = None,
    fps: int = 5,
    media_resolution: str = "MEDIA_RESOLUTION_HIGH",
    poll_interval: float = 1.0,
    max_polls: int = 60,
) -> MultiTabReport:
    api_key = api_key or os.environ["GEMINI_API_KEY"]
    model = model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)

    file_obj = _upload_video_file(data, mime_type, api_key)
    if file_obj.get("state") != "ACTIVE":
        file_obj = _wait_active(file_obj["name"], api_key, poll_interval, max_polls)
    file_uri = file_obj["uri"]

    body = {
        "contents": [{"parts": [
            {"file_data": {"mime_type": mime_type, "file_uri": file_uri},
             "video_metadata": {"fps": fps}},
            {"text": PROMPT_TABS},
        ]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "mediaResolution": media_resolution,
        },
    }
    url = f"{GEN_BASE}/v1beta/models/{model}:generateContent?key={api_key}"
    resp = requests.post(url, json=body, timeout=180)
    resp.raise_for_status()
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    parsed = json.loads(text)
    if not parsed.get("is_scoreboard") or not parsed.get("tabs"):
        raise NotAScoreboard()
    return validate_multitab(parsed)


def get_video_extractor():
    if os.environ.get("HALOHEADS_FAKE_GEMINI") == "1":
        from tests.fixtures.multitab_fake import fake_extract_video
        return fake_extract_video
    return extract_tabs_from_video
