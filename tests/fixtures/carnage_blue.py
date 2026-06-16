from haloheads.schema import CarnageReport, PlayerRow, validate_report

CARNAGE_BLUE: CarnageReport = validate_report({
    "winning_team": "BLUE",
    "gametype": "LEGENDARY SLAYER BR",
    "map": None,
    "players": [
        {"gamertag": "Cyborg800", "clan_tag": "4039", "team": "BLUE", "score": 250, "kills": 19, "assists": 5, "deaths": 4},
        {"gamertag": "X Jack X7282", "clan_tag": "UNSC", "team": "BLUE", "score": 225, "kills": 16, "assists": 6, "deaths": 5},
        {"gamertag": "Lord Celtic XxX", "clan_tag": "BEASTMODE ON", "team": "BLUE", "score": 205, "kills": 11, "assists": 11, "deaths": 6},
        {"gamertag": "Cursorycash5200", "clan_tag": "Seekers", "team": "BLUE", "score": 80, "kills": 4, "assists": 5, "deaths": 11},
        {"gamertag": "ELIMINADOR", "clan_tag": "DIEGO", "team": "RED", "score": 195, "kills": 14, "assists": 1, "deaths": 10},
        {"gamertag": "ScaredBOB", "clan_tag": "UNSC", "team": "RED", "score": 100, "kills": 6, "assists": 1, "deaths": 9},
        {"gamertag": "Archer 6820(1)", "clan_tag": "UNSC", "team": "RED", "score": 25, "kills": 2, "assists": 1, "deaths": 16},
        {"gamertag": "Archer 6820", "clan_tag": "UNSC", "team": "RED", "score": 15, "kills": 1, "assists": 1, "deaths": 16},
    ],
})


def fake_extract(data: bytes) -> CarnageReport:
    return CARNAGE_BLUE
