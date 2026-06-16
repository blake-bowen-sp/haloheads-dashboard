from tests.fixtures.carnage_blue import CARNAGE_BLUE
from haloheads.docs import build_docs


def _docs(match_id="m1"):
    return build_docs(
        CARNAGE_BLUE,
        match_id=match_id,
        source_image="pending/x.jpg",
        img_hash="hhh",
        uploaded_at="t0",
        analyzed_at="t1",
    )


def test_add_and_query(sqlite_store):
    match, players = _docs()
    sqlite_store.add_match(match, players)
    assert len(sqlite_store.all_player_stats()) == 8
    assert len(sqlite_store.all_matches()) == 1
    assert sqlite_store.match_exists("hhh") is True
    assert sqlite_store.match_exists("nope") is False


def test_idempotent_add(sqlite_store):
    match, players = _docs()
    sqlite_store.add_match(match, players)
    sqlite_store.add_match(match, players)
    assert len(sqlite_store.all_player_stats()) == 8
    assert len(sqlite_store.all_matches()) == 1


def test_cyborg_row_values(sqlite_store):
    match, players = _docs()
    sqlite_store.add_match(match, players)
    all_stats = sqlite_store.all_player_stats()
    cyborg = next(p for p in all_stats if p["gamertag"] == "Cyborg800")
    assert cyborg["kills"] == 19
    assert cyborg["kd"] == 4.75
    assert cyborg["result"] == "WON"


def test_player_row_keys(sqlite_store):
    match, players = _docs()
    sqlite_store.add_match(match, players)
    expected_keys = {
        "row_hash", "match_id", "gamertag", "clan_tag", "team", "result",
        "score", "kills", "assists", "deaths", "kd", "gametype", "map", "created_at",
    }
    for row in sqlite_store.all_player_stats():
        assert set(row.keys()) == expected_keys


def test_match_keys(sqlite_store):
    match, players = _docs()
    sqlite_store.add_match(match, players)
    expected_keys = {
        "match_id", "gametype", "map", "winning_team", "source_image",
        "uploaded_at", "analyzed_at", "image_hash",
    }
    for row in sqlite_store.all_matches():
        assert set(row.keys()) == expected_keys
