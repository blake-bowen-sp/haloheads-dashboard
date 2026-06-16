from tests.fixtures.carnage_blue import CARNAGE_BLUE
from haloheads.docs import build_docs
from haloheads.aggregate import leaderboard, mvps, by_gametype, by_map


def _build_m1():
    _, players = build_docs(
        CARNAGE_BLUE,
        match_id="m1",
        source_image="pending/a.jpg",
        img_hash="h1",
        uploaded_at="t0",
        analyzed_at="t1",
    )
    return players


def _build_m2():
    _, players = build_docs(
        CARNAGE_BLUE,
        match_id="m2",
        source_image="pending/b.jpg",
        img_hash="h2",
        uploaded_at="t2",
        analyzed_at="t3",
    )
    return players


def _all_players():
    return _build_m1() + _build_m2()


def _all_matches():
    m1, _ = build_docs(
        CARNAGE_BLUE,
        match_id="m1",
        source_image="pending/a.jpg",
        img_hash="h1",
        uploaded_at="t0",
        analyzed_at="t1",
    )
    m2, _ = build_docs(
        CARNAGE_BLUE,
        match_id="m2",
        source_image="pending/b.jpg",
        img_hash="h2",
        uploaded_at="t2",
        analyzed_at="t3",
    )
    return [m1, m2]


def test_leaderboard_cyborg_two_games():
    board = leaderboard(_all_players())
    cyborg = next(e for e in board if e["gamertag"] == "Cyborg800")
    assert cyborg["games"] == 2
    assert cyborg["kills"] == 38


def test_leaderboard_sorted_by_net_kd():
    board = leaderboard(_all_players())
    net_kds = [e["net_kd"] for e in board]
    assert net_kds == sorted(net_kds, reverse=True)


def test_leaderboard_top_has_highest_kd():
    board = leaderboard(_all_players())
    top_kd = board[0]["net_kd"]
    assert all(top_kd >= e["net_kd"] for e in board)


def test_leaderboard_entry_keys():
    board = leaderboard(_all_players())
    for e in board:
        for key in ("gamertag", "games", "kills", "deaths", "assists", "score",
                    "wins", "net_kd", "win_rate"):
            assert key in e, f"missing key {key!r}"


def test_mvps_blue_m1():
    matches = _all_matches()
    result = mvps(matches, _all_players())
    blue_m1 = next(
        (r for r in result if r["match_id"] == "m1" and r["team"] == "BLUE"), None
    )
    assert blue_m1 is not None
    assert blue_m1["gamertag"] == "Cyborg800"
    assert blue_m1["score"] == 250


def test_mvps_red_m1():
    matches = _all_matches()
    result = mvps(matches, _all_players())
    red_m1 = next(
        (r for r in result if r["match_id"] == "m1" and r["team"] == "RED"), None
    )
    assert red_m1 is not None
    assert red_m1["gamertag"] == "ELIMINADOR"
    assert red_m1["score"] == 195


def test_by_gametype_has_key():
    result = by_gametype(_all_players())
    expected_key = CARNAGE_BLUE.gametype.upper()
    assert expected_key in result
    assert isinstance(result[expected_key], list)


def test_by_map_empty_when_all_none():
    result = by_map(_all_players())
    assert result == {}


def test_leaderboard_wins():
    board = leaderboard(_all_players())
    cyborg = next(e for e in board if e["gamertag"] == "Cyborg800")
    assert cyborg["wins"] == 2
    eliminador = next(e for e in board if e["gamertag"] == "ELIMINADOR")
    assert eliminador["wins"] == 0


def test_leaderboard_win_rate():
    board = leaderboard(_all_players())
    cyborg = next(e for e in board if e["gamertag"] == "Cyborg800")
    assert cyborg["win_rate"] == 1.0
    eliminador = next(e for e in board if e["gamertag"] == "ELIMINADOR")
    assert eliminador["win_rate"] == 0.0
