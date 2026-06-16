import base64
import os

import anthropic
from PIL import Image
import io

from haloheads.schema import CarnageReport, validate_report

TOOL = {
    "name": "record_carnage_report",
    "description": "Record the stats from a Halo post-game carnage report scoreboard.",
    "input_schema": {
        "type": "object",
        "required": ["winning_team", "gametype", "map", "players"],
        "properties": {
            "winning_team": {"type": ["string", "null"]},
            "gametype": {"type": "string"},
            "map": {"type": ["string", "null"]},
            "players": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["gamertag"],
                    "properties": {
                        "gamertag": {"type": "string"},
                        "clan_tag": {"type": ["string", "null"]},
                        "team": {"type": ["string", "null"]},
                        "score": {"type": "integer"},
                        "kills": {"type": "integer"},
                        "assists": {"type": "integer"},
                        "deaths": {"type": "integer"},
                    },
                },
            },
        },
    },
}

PROMPT = (
    "This is a photo of a Halo post-game carnage report scoreboard. "
    "Read the scoreboard and extract every player's username (gamertag) and whatever stats are shown. "
    "Teams can be any color or label (blue, red, green, gold, etc.) — record the team label exactly as shown; use null if no team is visible. "
    "The winning team is whatever the header says (e.g. 'BLUE TEAM WON', 'GREEN WINS'); use null if not shown. "
    "Keep the clan tag shown in [brackets] separate from the gamertag (clan_tag is null if there is no bracket tag). "
    "Columns may include SCORE, KILLS, ASSISTS, DEATHS; return visible ones as integers, omit any not visible. "
    "Set map to null if no map name is visible. Call record_carnage_report with the result."
)


def _downscale_jpeg(data: bytes, max_edge: int = 2048) -> bytes:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    if max(img.width, img.height) > max_edge:
        img.thumbnail((max_edge, max_edge), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def extract_carnage_report(data: bytes, *, client=None, model=None) -> CarnageReport:
    client = client or anthropic.Anthropic()
    model = model or os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")

    jpeg = _downscale_jpeg(data)
    b64 = base64.standard_b64encode(jpeg).decode()

    image_block = {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
    }
    text_block = {"type": "text", "text": PROMPT}

    resp = client.messages.create(
        model=model,
        max_tokens=4096,
        tools=[TOOL],
        tool_choice={"type": "tool", "name": "record_carnage_report"},
        messages=[{"role": "user", "content": [image_block, text_block]}],
    )

    for block in resp.content:
        if block.type == "tool_use" and block.name == "record_carnage_report":
            return validate_report(block.input)

    raise ValueError("no tool_use block in response")


def get_extractor():
    if os.environ.get("HALOHEADS_FAKE_EXTRACT") == "1":
        from tests.fixtures.carnage_blue import fake_extract
        return fake_extract
    return extract_carnage_report
