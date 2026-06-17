import json

import pytest

from haloheads.schema import (
    CarnageReport,
    MultiTabReport,
    Tab,
    validate_multitab,
    validate_report,
    canonical_report,
    overview_tab,
    tabs_to_dicts,
)

MULTITAB_DICT = {
    "is_scoreboard": True,
    "winning_team": "BLUE",
    "gametype": "LEGENDARY SLAYER BR",
    "map": None,
    "tabs": [
        {
            "name": "OVERVIEW",
            "columns": ["SCORE", "KILLS", "ASSISTS", "DEATHS"],
            "players": [
                {"gamertag": "Cyborg800", "clan_tag": "4039", "team": "BLUE",
                 "stats": {"SCORE": 250, "KILLS": 19, "ASSISTS": 5, "DEATHS": 4}},
                {"gamertag": "ELIMINADOR", "clan_tag": "DIEGO", "team": "RED",
                 "stats": {"SCORE": 195, "KILLS": 14, "ASSISTS": 1, "DEATHS": 10}},
            ],
        },
        {
            "name": "DETAILED STATS",
            "columns": ["AVERAGE LIFE", "SPREAD"],
            "players": [
                {"gamertag": "Cyborg800", "clan_tag": "4039", "team": "BLUE",
                 "stats": {"AVERAGE LIFE": "0:58", "SPREAD": 15}},
                {"gamertag": "ELIMINADOR", "clan_tag": "DIEGO", "team": "RED",
                 "stats": {"AVERAGE LIFE": "0:21", "SPREAD": 4}},
            ],
        },
    ],
}


def test_validate_multitab_happy():
    multi = validate_multitab(MULTITAB_DICT)
    assert isinstance(multi, MultiTabReport)
    assert len(multi.tabs) == 2
    assert multi.tabs[0].name == "OVERVIEW"
    assert multi.tabs[0].players[0].gamertag == "Cyborg800"
    assert multi.tabs[0].players[0].stats["KILLS"] == 19
    assert multi.tabs[1].name == "DETAILED STATS"
    assert multi.tabs[1].players[0].stats["AVERAGE LIFE"] == "0:58"


def test_validate_multitab_empty_tabs_raises():
    with pytest.raises(ValueError):
        validate_multitab({**MULTITAB_DICT, "tabs": []})


def test_validate_multitab_tab_without_players_raises():
    bad = {**MULTITAB_DICT, "tabs": [{"name": "EMPTY", "columns": [], "players": []}]}
    with pytest.raises(ValueError):
        validate_multitab(bad)


def test_validate_multitab_player_missing_gamertag_raises():
    bad = {
        **MULTITAB_DICT,
        "tabs": [{"name": "OVERVIEW", "columns": ["SCORE"], "players": [{"stats": {"SCORE": 1}}]}],
    }
    with pytest.raises(ValueError):
        validate_multitab(bad)


def test_validate_multitab_fills_columns_from_stats_when_absent():
    data = {
        "is_scoreboard": True, "winning_team": "BLUE", "gametype": "SLAYER", "map": None,
        "tabs": [{"name": "OVERVIEW", "players": [
            {"gamertag": "A", "stats": {"SCORE": 10, "KILLS": 1, "ASSISTS": 0, "DEATHS": 2}}]}],
    }
    multi = validate_multitab(data)
    assert multi.tabs[0].columns == ["SCORE", "KILLS", "ASSISTS", "DEATHS"]


def test_canonical_report_picks_overview_tab():
    report = canonical_report(validate_multitab(MULTITAB_DICT))
    assert isinstance(report, CarnageReport)
    assert report.winning_team == "BLUE"
    assert report.gametype == "LEGENDARY SLAYER BR"
    cy = next(p for p in report.players if p.gamertag == "Cyborg800")
    assert (cy.score, cy.kills, cy.assists, cy.deaths) == (250, 19, 5, 4)
    assert cy.team == "BLUE" and cy.clan_tag == "4039"


def test_canonical_report_detects_skad_tab_not_named_overview():
    data = {
        "is_scoreboard": True, "winning_team": "GREEN", "gametype": "TEAM SLAYER", "map": None,
        "tabs": [
            {"name": "MEDALS", "columns": ["MEDALS"], "players": [
                {"gamertag": "A", "clan_tag": None, "team": "GREEN", "stats": {"MEDALS": 3}}]},
            {"name": "SCORES", "columns": ["SCORE", "KILLS", "ASSISTS", "DEATHS"], "players": [
                {"gamertag": "A", "clan_tag": None, "team": "GREEN",
                 "stats": {"SCORE": 50, "KILLS": 5, "ASSISTS": 2, "DEATHS": 1}}]},
        ],
    }
    report = canonical_report(validate_multitab(data))
    assert report.players[0].gamertag == "A"
    assert report.players[0].kills == 5


def test_canonical_report_coerces_string_numbers():
    data = {
        "is_scoreboard": True, "winning_team": "BLUE", "gametype": "SLAYER", "map": None,
        "tabs": [{"name": "OVERVIEW", "columns": ["SCORE", "KILLS", "ASSISTS", "DEATHS"], "players": [
            {"gamertag": "S", "clan_tag": None, "team": "BLUE",
             "stats": {"SCORE": "120", "KILLS": "8", "ASSISTS": "0", "DEATHS": "3"}}]}],
    }
    report = canonical_report(validate_multitab(data))
    assert (report.players[0].score, report.players[0].kills, report.players[0].deaths) == (120, 8, 3)


def test_canonical_report_no_skad_tab_yields_empty_players():
    data = {
        "is_scoreboard": True, "winning_team": None, "gametype": "MEDALS", "map": None,
        "tabs": [{"name": "MEDALS", "columns": ["MEDALS"], "players": [
            {"gamertag": "A", "clan_tag": None, "team": None, "stats": {"MEDALS": 3}}]}],
    }
    report = canonical_report(validate_multitab(data))
    assert report.players == []


def test_overview_tab_from_carnage_report():
    report = validate_report({
        "winning_team": "BLUE", "gametype": "SLAYER", "map": None,
        "players": [{"gamertag": "Cyborg800", "clan_tag": "4039", "team": "BLUE",
                     "score": 250, "kills": 19, "assists": 5, "deaths": 4}],
    })
    tab = overview_tab(report)
    assert isinstance(tab, Tab)
    assert tab.name == "OVERVIEW"
    assert tab.columns == ["SCORE", "KILLS", "ASSISTS", "DEATHS"]
    assert tab.players[0].gamertag == "Cyborg800"
    assert tab.players[0].stats == {"SCORE": 250, "KILLS": 19, "ASSISTS": 5, "DEATHS": 4}


def test_tabs_to_dicts_is_json_serializable():
    multi = validate_multitab(MULTITAB_DICT)
    dicts = tabs_to_dicts(multi.tabs)
    back = json.loads(json.dumps(dicts))
    assert back[0]["name"] == "OVERVIEW"
    assert back[0]["players"][0]["stats"]["KILLS"] == 19
    assert back[1]["players"][0]["stats"]["AVERAGE LIFE"] == "0:58"
