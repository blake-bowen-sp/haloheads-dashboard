"""Deterministic multi-tab fixture for the inline Gemini fake path.

Used when HALOHEADS_FAKE_GEMINI=1 so the video upload path can be driven
end-to-end (E2E, app tests) without an API key. One fictional game across an
OVERVIEW tab (feeds the leaderboard) and a DETAILED STATS tab (extra-tab page).
"""
from haloheads.schema import MultiTabReport, validate_multitab

MULTITAB_BLUE = {
    "is_scoreboard": True,
    "winning_team": "BLUE",
    "gametype": "LEGENDARY SLAYER BR",
    "map": None,
    "tabs": [
        {
            "name": "OVERVIEW",
            "columns": ["SCORE", "KILLS", "ASSISTS", "DEATHS"],
            "players": [
                {"gamertag": "Cyborg800", "clan_tag": "4039", "team": "BLUE", "stats": {"SCORE": 250, "KILLS": 19, "ASSISTS": 5, "DEATHS": 4}},
                {"gamertag": "X Jack X7282", "clan_tag": "UNSC", "team": "BLUE", "stats": {"SCORE": 225, "KILLS": 16, "ASSISTS": 6, "DEATHS": 5}},
                {"gamertag": "Lord Celtic XxX", "clan_tag": "BEASTMODE ON", "team": "BLUE", "stats": {"SCORE": 205, "KILLS": 11, "ASSISTS": 11, "DEATHS": 6}},
                {"gamertag": "Cursorycash5200", "clan_tag": "Seekers", "team": "BLUE", "stats": {"SCORE": 80, "KILLS": 4, "ASSISTS": 5, "DEATHS": 11}},
                {"gamertag": "ELIMINADOR", "clan_tag": "DIEGO", "team": "RED", "stats": {"SCORE": 195, "KILLS": 14, "ASSISTS": 1, "DEATHS": 10}},
                {"gamertag": "ScaredBOB", "clan_tag": "UNSC", "team": "RED", "stats": {"SCORE": 100, "KILLS": 6, "ASSISTS": 1, "DEATHS": 9}},
                {"gamertag": "Archer 6820(1)", "clan_tag": "UNSC", "team": "RED", "stats": {"SCORE": 25, "KILLS": 2, "ASSISTS": 1, "DEATHS": 16}},
                {"gamertag": "Archer 6820", "clan_tag": "UNSC", "team": "RED", "stats": {"SCORE": 15, "KILLS": 1, "ASSISTS": 1, "DEATHS": 16}},
            ],
        },
        {
            "name": "DETAILED STATS",
            "columns": ["AVERAGE LIFE", "SPREAD", "BEST SPREE"],
            "players": [
                {"gamertag": "Cyborg800", "clan_tag": "4039", "team": "BLUE", "stats": {"AVERAGE LIFE": "1:02", "SPREAD": 15, "BEST SPREE": 7}},
                {"gamertag": "X Jack X7282", "clan_tag": "UNSC", "team": "BLUE", "stats": {"AVERAGE LIFE": "0:58", "SPREAD": 11, "BEST SPREE": 5}},
                {"gamertag": "Lord Celtic XxX", "clan_tag": "BEASTMODE ON", "team": "BLUE", "stats": {"AVERAGE LIFE": "0:51", "SPREAD": 5, "BEST SPREE": 4}},
                {"gamertag": "Cursorycash5200", "clan_tag": "Seekers", "team": "BLUE", "stats": {"AVERAGE LIFE": "0:33", "SPREAD": -7, "BEST SPREE": 2}},
                {"gamertag": "ELIMINADOR", "clan_tag": "DIEGO", "team": "RED", "stats": {"AVERAGE LIFE": "0:44", "SPREAD": 4, "BEST SPREE": 5}},
                {"gamertag": "ScaredBOB", "clan_tag": "UNSC", "team": "RED", "stats": {"AVERAGE LIFE": "0:39", "SPREAD": -3, "BEST SPREE": 3}},
                {"gamertag": "Archer 6820(1)", "clan_tag": "UNSC", "team": "RED", "stats": {"AVERAGE LIFE": "0:21", "SPREAD": -14, "BEST SPREE": 1}},
                {"gamertag": "Archer 6820", "clan_tag": "UNSC", "team": "RED", "stats": {"AVERAGE LIFE": "0:18", "SPREAD": -15, "BEST SPREE": 1}},
            ],
        },
    ],
}


def fake_extract_video(data: bytes, *, mime_type: str | None = None) -> MultiTabReport:
    return validate_multitab(MULTITAB_BLUE)
