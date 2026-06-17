from haloheads.docs import build_docs
from haloheads.schema import canonical_report, tabs_to_dicts, validate_multitab
from haloheads.storage import LocalStorage
from haloheads.store import SqliteStore
from tests.fixtures.carnage_blue import CARNAGE_BLUE
from tests.fixtures.multitab_fake import MULTITAB_BLUE


# --- storage: video media extensions ---

def test_storage_saves_and_moves_mp4(tmp_path):
    st = LocalStorage(str(tmp_path / "bucket"))
    key = st.save_upload(b"VIDEOBYTES", "video/mp4", {"uploaded_at": "t"})
    assert key.startswith("pending/") and key.endswith(".mp4")
    assert key in st.list_pending()
    assert st.read(key) == b"VIDEOBYTES"
    new_key = st.move(key, "analyzed/")
    assert new_key.startswith("analyzed/") and new_key.endswith(".mp4")
    assert st.read(new_key) == b"VIDEOBYTES"


def test_storage_quicktime_extension(tmp_path):
    st = LocalStorage(str(tmp_path / "bucket"))
    key = st.save_upload(b"MOV", "video/quicktime", {})
    assert key.endswith(".mov")


def test_storage_jpeg_still_jpg(tmp_path):
    st = LocalStorage(str(tmp_path / "bucket"))
    key = st.save_upload(b"img", "image/jpeg", {})
    assert key.endswith(".jpg")


# --- store: tabs column round-trip + queries ---

def test_store_roundtrips_tabs(tmp_path):
    multi = validate_multitab(MULTITAB_BLUE)
    report = canonical_report(multi)
    tabs = tabs_to_dicts(multi.tabs)
    match, players = build_docs(
        report, match_id="m1", source_image="pending/x.mp4", img_hash="h",
        uploaded_at="t", analyzed_at="t", tabs=tabs,
    )
    store = SqliteStore(str(tmp_path / "s.db"))
    store.add_match(match, players)

    got = store.get_match("m1")
    assert got is not None
    assert [t["name"] for t in got["tabs"]] == ["OVERVIEW", "DETAILED STATS"]
    assert got["tabs"][1]["players"][0]["stats"]["AVERAGE LIFE"] == "1:02"


def test_store_get_match_missing(tmp_path):
    store = SqliteStore(str(tmp_path / "s.db"))
    assert store.get_match("nope") is None


def test_store_recent_matches_newest_first(tmp_path):
    store = SqliteStore(str(tmp_path / "s.db"))
    stamps = ["2026-06-16T01:00:00Z", "2026-06-16T03:00:00Z", "2026-06-16T02:00:00Z"]
    for i, ts in enumerate(stamps):
        match, players = build_docs(
            CARNAGE_BLUE, match_id=f"m{i}", source_image="x", img_hash=f"h{i}",
            uploaded_at=ts, analyzed_at=ts,
        )
        store.add_match(match, players)
    recent = store.recent_matches(2)
    assert len(recent) == 2
    assert recent[0]["uploaded_at"] == "2026-06-16T03:00:00Z"


# --- docs: tabs attachment ---

def test_build_docs_attaches_tabs():
    tabs = [{"name": "OVERVIEW", "columns": ["SCORE"], "players": []}]
    match, _ = build_docs(
        CARNAGE_BLUE, match_id="m1", source_image="x", img_hash="h",
        uploaded_at="t", analyzed_at="t", tabs=tabs,
    )
    assert match["tabs"] == tabs


def test_build_docs_tabs_default_none():
    match, _ = build_docs(
        CARNAGE_BLUE, match_id="m1", source_image="x", img_hash="h",
        uploaded_at="t", analyzed_at="t",
    )
    assert match["tabs"] is None
