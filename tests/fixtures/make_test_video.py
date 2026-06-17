"""Generate deterministic multi-tab carnage-report videos for the golden tests.

Renders clean OVERVIEW + DETAILED STATS frames for a fictional game and encodes
them to mp4, so the real-Gemini golden test has known ground truth without
needing a phone video. Run:  python3 tests/fixtures/make_test_video.py
"""
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
HEADER = "BLUE TEAM WON    LEGENDARY SLAYER BR"
TEAM_BG = {"BLUE": (24, 58, 130), "RED": (150, 28, 28)}

# --- ground truth (imported by the golden test) ---
GAME_ONE = {
    "winning_team": "BLUE",
    "gametype": "LEGENDARY SLAYER BR",
    "overview": {
        "name": "OVERVIEW",
        "columns": ["SCORE", "KILLS", "ASSISTS", "DEATHS"],
        "players": [
            {"gamertag": "Spartan117", "clan_tag": "UNSC", "team": "BLUE", "stats": {"SCORE": 300, "KILLS": 25, "ASSISTS": 4, "DEATHS": 6}},
            {"gamertag": "NobleSix", "clan_tag": "HALO", "team": "BLUE", "stats": {"SCORE": 280, "KILLS": 22, "ASSISTS": 7, "DEATHS": 8}},
            {"gamertag": "RedReaper", "clan_tag": "BR", "team": "RED", "stats": {"SCORE": 240, "KILLS": 18, "ASSISTS": 2, "DEATHS": 12}},
            {"gamertag": "GruntKing", "clan_tag": "BR", "team": "RED", "stats": {"SCORE": 90, "KILLS": 6, "ASSISTS": 1, "DEATHS": 16}},
        ],
    },
    "detailed": {
        "name": "DETAILED STATS",
        "columns": ["AVERAGE LIFE", "SPREAD", "BEST SPREE"],
        "players": [
            {"gamertag": "Spartan117", "clan_tag": "UNSC", "team": "BLUE", "stats": {"AVERAGE LIFE": "1:12", "SPREAD": 19, "BEST SPREE": 9}},
            {"gamertag": "NobleSix", "clan_tag": "HALO", "team": "BLUE", "stats": {"AVERAGE LIFE": "0:58", "SPREAD": 14, "BEST SPREE": 7}},
            {"gamertag": "RedReaper", "clan_tag": "BR", "team": "RED", "stats": {"AVERAGE LIFE": "0:41", "SPREAD": 6, "BEST SPREE": 5}},
            {"gamertag": "GruntKing", "clan_tag": "BR", "team": "RED", "stats": {"AVERAGE LIFE": "0:24", "SPREAD": -10, "BEST SPREE": 2}},
        ],
    },
}

# A second, clearly different game for the semantic-delta test.
GAME_TWO = {
    "winning_team": "RED",
    "gametype": "TEAM SLAYER",
    "overview": {
        "name": "OVERVIEW",
        "columns": ["SCORE", "KILLS", "ASSISTS", "DEATHS"],
        "players": [
            {"gamertag": "Spartan117", "clan_tag": "UNSC", "team": "RED", "stats": {"SCORE": 120, "KILLS": 9, "ASSISTS": 3, "DEATHS": 14}},
            {"gamertag": "NobleSix", "clan_tag": "HALO", "team": "BLUE", "stats": {"SCORE": 175, "KILLS": 13, "ASSISTS": 5, "DEATHS": 11}},
        ],
    },
    "detailed": {
        "name": "DETAILED STATS",
        "columns": ["AVERAGE LIFE", "SPREAD"],
        "players": [
            {"gamertag": "Spartan117", "clan_tag": "UNSC", "team": "RED", "stats": {"AVERAGE LIFE": "0:33", "SPREAD": -5}},
            {"gamertag": "NobleSix", "clan_tag": "HALO", "team": "BLUE", "stats": {"AVERAGE LIFE": "0:47", "SPREAD": 2}},
        ],
    },
}


def _font(size, bold=False):
    for path in (
        f"/System/Library/Fonts/Supplemental/Arial{' Bold' if bold else ''}.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _col_x(n):
    return [1180 - (n - 1 - i) * 168 for i in range(n)]


def render_tab(header, tab_name, columns, players):
    img = Image.new("RGB", (W, H), (10, 12, 16))
    d = ImageDraw.Draw(img)
    d.text((50, 34), header, font=_font(38, bold=True), fill=(236, 241, 246))
    d.text((W - 280, 44), tab_name, font=_font(30, bold=True), fill=(150, 190, 225))
    d.text((60, 118), "PLAYERS", font=_font(20, bold=True), fill=(120, 132, 144))
    xs = _col_x(len(columns))
    for cx, name in zip(xs, columns):
        d.text((cx, 118), name, font=_font(20, bold=True), fill=(120, 132, 144), anchor="ra")
    y = 158
    for p in players:
        d.rectangle([40, y, W - 40, y + 58], fill=TEAM_BG.get(p["team"], (44, 44, 44)))
        label = (f"[{p['clan_tag']}] " if p.get("clan_tag") else "") + p["gamertag"]
        d.text((60, y + 14), label, font=_font(30, bold=True), fill=(246, 249, 251))
        for cx, name in zip(xs, columns):
            d.text((cx, y + 14), str(p["stats"][name]), font=_font(30), fill=(246, 249, 251), anchor="ra")
        y += 66
    return img


def write_video(path, game, fps=10, hold=14):
    overview = render_tab(HEADER if game is GAME_ONE else f"{game['winning_team']} TEAM WON    {game['gametype']}",
                          game["overview"]["name"], game["overview"]["columns"], game["overview"]["players"])
    detailed = render_tab(HEADER if game is GAME_ONE else f"{game['winning_team']} TEAM WON    {game['gametype']}",
                          game["detailed"]["name"], game["detailed"]["columns"], game["detailed"]["players"])
    vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    for frame, n in ((overview, hold), (detailed, hold)):
        bgr = cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR)
        for _ in range(n):
            vw.write(bgr)
    vw.release()


def write_notscoreboard(path, fps=10):
    img = Image.new("RGB", (W, H), (245, 245, 240))
    d = ImageDraw.Draw(img)
    d.text((80, 280), "A treatise on music, mind, and Bach.", font=_font(40), fill=(20, 20, 20))
    d.text((80, 340), "There is no scoreboard on this page.", font=_font(40), fill=(20, 20, 20))
    vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    for _ in range(20):
        vw.write(bgr)
    vw.release()


def main():
    here = os.path.dirname(__file__)
    write_video(os.path.join(here, "multitab_sample.mp4"), GAME_ONE)
    write_video(os.path.join(here, "multitab_sample_2.mp4"), GAME_TWO)
    write_notscoreboard(os.path.join(here, "notscoreboard_sample.mp4"))
    print("wrote multitab_sample.mp4, multitab_sample_2.mp4, notscoreboard_sample.mp4")


if __name__ == "__main__":
    main()
