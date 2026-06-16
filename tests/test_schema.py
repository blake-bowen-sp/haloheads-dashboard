import hashlib
import pytest
from haloheads.schema import (
    CarnageReport,
    PlayerRow,
    validate_report,
    result_for,
    kd,
    image_hash,
    row_hash,
    game_hash,
)

GOLDEN_DICT = {
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
}


def test_valid_golden():
    report = validate_report(GOLDEN_DICT)
    assert isinstance(report, CarnageReport)
    assert len(report.players) == 8
    assert report.winning_team == "BLUE"
    assert all(isinstance(p, PlayerRow) for p in report.players)


def test_empty_players():
    bad = {**GOLDEN_DICT, "players": []}
    with pytest.raises(ValueError):
        validate_report(bad)


def test_player_deaths_string():
    bad_players = [dict(p) for p in GOLDEN_DICT["players"]]
    bad_players[6] = {**bad_players[6], "deaths": "16"}
    bad = {**GOLDEN_DICT, "players": bad_players}
    with pytest.raises(ValueError):
        validate_report(bad)


def test_player_negative_kills():
    bad_players = [dict(p) for p in GOLDEN_DICT["players"]]
    bad_players[0] = {**bad_players[0], "kills": -1}
    bad = {**GOLDEN_DICT, "players": bad_players}
    with pytest.raises(ValueError):
        validate_report(bad)


def test_result_for_lost():
    assert result_for("RED", "BLUE") == "LOST"


def test_result_for_won():
    assert result_for("BLUE", "BLUE") == "WON"


def test_kd_normal():
    assert kd(19, 4) == 4.75


def test_kd_zero_deaths():
    assert kd(5, 0) == 5.0


def test_image_hash_deterministic():
    h = image_hash(b"abc")
    assert h == image_hash(b"abc")
    assert h == hashlib.sha256(b"abc").hexdigest()


def test_row_hash_changes_on_kills():
    h1 = row_hash("m1", "Cyborg800", 250, 19, 5, 4)
    h2 = row_hash("m1", "Cyborg800", 250, 20, 5, 4)
    assert h1 != h2


def test_bool_rejected_as_int():
    bad_players = [dict(p) for p in GOLDEN_DICT["players"]]
    bad_players[0] = {**bad_players[0], "score": True}
    bad = {**GOLDEN_DICT, "players": bad_players}
    with pytest.raises(ValueError):
        validate_report(bad)


_PLAYERS = validate_report(GOLDEN_DICT).players


def test_game_hash_deterministic():
    h1 = game_hash("BLUE", "SLAYER", _PLAYERS)
    h2 = game_hash("BLUE", "SLAYER", _PLAYERS)
    assert h1 == h2
    assert isinstance(h1, str) and len(h1) == 64


def test_game_hash_order_independent():
    shuffled = list(reversed(_PLAYERS))
    assert game_hash("BLUE", "SLAYER", _PLAYERS) == game_hash("BLUE", "SLAYER", shuffled)


def test_game_hash_changes_on_kills():
    from dataclasses import replace
    mutated = [replace(_PLAYERS[0], kills=_PLAYERS[0].kills + 1)] + _PLAYERS[1:]
    assert game_hash("BLUE", "SLAYER", _PLAYERS) != game_hash("BLUE", "SLAYER", mutated)


def test_game_hash_changes_on_winning_team():
    assert game_hash("BLUE", "SLAYER", _PLAYERS) != game_hash("RED", "SLAYER", _PLAYERS)


def test_green_gold_report_validates():
    report = validate_report({
        "winning_team": "GREEN",
        "gametype": "ODDBALL",
        "map": "Zanzibar",
        "players": [
            {"gamertag": "GreenPlayer1", "team": "GREEN", "score": 300, "kills": 20, "assists": 3, "deaths": 5},
            {"gamertag": "GoldPlayer1", "team": "GOLD", "score": 150, "kills": 10, "assists": 2, "deaths": 12},
        ],
    })
    assert isinstance(report, CarnageReport)
    assert report.winning_team == "GREEN"
    assert report.players[0].team == "GREEN"
    assert report.players[1].team == "GOLD"


def test_missing_stats_default_to_zero():
    report = validate_report({
        "winning_team": None,
        "gametype": "FREE FOR ALL",
        "map": None,
        "players": [
            {"gamertag": "SoloPlayer"},
        ],
    })
    p = report.players[0]
    assert p.score == 0
    assert p.kills == 0
    assert p.assists == 0
    assert p.deaths == 0


def test_result_for_none_winning_team():
    assert result_for("GREEN", None) == ""


def test_result_for_none_team():
    assert result_for(None, "GREEN") == ""


def test_result_for_green_won():
    assert result_for("GREEN", "GREEN") == "WON"


def test_result_for_gold_vs_green():
    assert result_for("GOLD", "GREEN") == "LOST"


def test_missing_gamertag_raises():
    bad = {
        "winning_team": "BLUE",
        "gametype": "SLAYER",
        "map": None,
        "players": [{"team": "BLUE", "score": 10, "kills": 1, "assists": 0, "deaths": 1}],
    }
    with pytest.raises(ValueError):
        validate_report(bad)
