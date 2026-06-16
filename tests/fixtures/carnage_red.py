from haloheads.schema import CarnageReport, validate_report

CARNAGE_RED: CarnageReport = validate_report({
    "winning_team": "RED",
    "gametype": "TEAM SLAYER",
    "map": None,
    "players": [
        {"gamertag": "Snipe King", "clan_tag": "PRO", "team": "RED", "score": 200, "kills": 18, "assists": 4, "deaths": 6},
        {"gamertag": "Ghost Recon", "clan_tag": "PRO", "team": "RED", "score": 150, "kills": 12, "assists": 5, "deaths": 8},
        {"gamertag": "Noob Tube", "clan_tag": "N00B", "team": "BLUE", "score": 90, "kills": 5, "assists": 2, "deaths": 14},
        {"gamertag": "Camper Dan", "clan_tag": "N00B", "team": "BLUE", "score": 70, "kills": 3, "assists": 3, "deaths": 15},
    ],
})
