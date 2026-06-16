from tests.fixtures.carnage_blue import CARNAGE_BLUE
from haloheads.docs import build_docs


def _build():
    return build_docs(
        CARNAGE_BLUE,
        match_id="m1",
        source_image="pending/x.jpg",
        img_hash="h",
        uploaded_at="t0",
        analyzed_at="t1",
    )


def test_match_winning_team():
    match, _ = _build()
    assert match["winning_team"] == "BLUE"


def test_match_gametype_uppercase():
    match, _ = _build()
    assert match["gametype"] == CARNAGE_BLUE.gametype.upper()


def test_player_count():
    _, players = _build()
    assert len(players) == 8


def test_eliminador_result_lost():
    _, players = _build()
    eliminador = next(p for p in players if p["gamertag"] == "ELIMINADOR")
    assert eliminador["result"] == "LOST"


def test_cyborg_kd():
    _, players = _build()
    cyborg = next(p for p in players if p["gamertag"] == "Cyborg800")
    assert cyborg["kd"] == 4.75


def test_row_hashes_unique():
    _, players = _build()
    hashes = [p["row_hash"] for p in players]
    assert len(set(hashes)) == 8


def test_match_keys():
    match, _ = _build()
    for key in ("match_id", "gametype", "map", "winning_team", "source_image",
                "uploaded_at", "analyzed_at", "image_hash", "game_hash"):
        assert key in match, f"missing key {key!r}"


def test_match_game_hash_nonempty():
    match, _ = _build()
    assert isinstance(match["game_hash"], str) and len(match["game_hash"]) > 0


def test_player_keys():
    _, players = _build()
    for p in players:
        for key in ("match_id", "gamertag", "clan_tag", "team", "result", "score",
                    "kills", "assists", "deaths", "kd", "gametype", "map",
                    "created_at", "row_hash"):
            assert key in p, f"player missing key {key!r}"
