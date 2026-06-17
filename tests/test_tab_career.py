from haloheads.aggregate import tab_career


def _match(tabs):
    return {"match_id": "x", "tabs": tabs}


def _detailed(gt, life, spread):
    return {
        "name": "DETAILED STATS",
        "columns": ["AVERAGE LIFE", "SPREAD"],
        "players": [{"gamertag": gt, "clan_tag": None, "team": "BLUE",
                     "stats": {"AVERAGE LIFE": life, "SPREAD": spread}}],
    }


def test_tab_career_averages_numbers_and_times():
    matches = [_match([_detailed("Cy", "1:00", 10)]), _match([_detailed("Cy", "0:30", 20)])]
    career = tab_career(matches)
    assert "DETAILED STATS" in career
    row = next(r for r in career["DETAILED STATS"]["rows"] if r["gamertag"] == "Cy")
    assert row["games"] == 2
    assert row["stats"]["SPREAD"] == 15
    assert row["stats"]["AVERAGE LIFE"] == "0:45"


def test_tab_career_excludes_overview():
    overview = {"name": "OVERVIEW", "columns": ["SCORE", "KILLS", "ASSISTS", "DEATHS"],
                "players": [{"gamertag": "Cy", "clan_tag": None, "team": "BLUE",
                             "stats": {"SCORE": 100, "KILLS": 5, "ASSISTS": 1, "DEATHS": 2}}]}
    assert tab_career([_match([overview])]) == {}


def test_tab_career_skips_non_numeric_values():
    tab = {"name": "MEDALS", "columns": ["TOP MEDAL", "COUNT"],
           "players": [{"gamertag": "Cy", "clan_tag": None, "team": None,
                        "stats": {"TOP MEDAL": "Killing Frenzy", "COUNT": 4}}]}
    row = tab_career([_match([tab])])["MEDALS"]["rows"][0]
    assert "TOP MEDAL" not in row["stats"]
    assert row["stats"]["COUNT"] == 4


def test_tab_career_handles_missing_tabs():
    assert tab_career([{"match_id": "x", "tabs": None}]) == {}
    assert tab_career([{"match_id": "x"}]) == {}


def test_tab_career_columns_union_in_order():
    t1 = {"name": "D", "columns": ["A", "B"], "players": [{"gamertag": "g", "stats": {"A": 1, "B": 2}}]}
    t2 = {"name": "D", "columns": ["A", "C"], "players": [{"gamertag": "g", "stats": {"A": 3, "C": 4}}]}
    career = tab_career([_match([t1]), _match([t2])])
    assert career["D"]["columns"] == ["A", "B", "C"]


def test_tab_career_negative_spread_average():
    matches = [_match([_detailed("Z", "0:20", -10)]), _match([_detailed("Z", "0:20", -20)])]
    row = tab_career(matches)["DETAILED STATS"]["rows"][0]
    assert row["stats"]["SPREAD"] == -15
