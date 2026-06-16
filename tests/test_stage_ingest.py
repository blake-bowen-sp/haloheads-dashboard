import json
from dataclasses import asdict
from pathlib import Path

from haloheads.storage import get_storage
from haloheads.store import get_store
from scripts import stage, ingest
from tests.fixtures.carnage_blue import CARNAGE_BLUE


def _setup(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "bucket"))
    monkeypatch.setenv("STORE_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "stats.db"))


def test_stage_then_ingest(tmp_path, monkeypatch, sample_image_bytes):
    _setup(tmp_path, monkeypatch)
    inbox = tmp_path / "inbox"

    key = get_storage().save_upload(sample_image_bytes, "image/jpeg", {"uploaded_at": "t0"})

    manifest = stage.main(["--stage-dir", str(inbox)])
    assert len(manifest) == 1
    assert manifest[0]["key"] == key
    assert Path(manifest[0]["path"]).exists()
    assert (inbox / "manifest.json").exists()

    reports = {key: asdict(CARNAGE_BLUE)}
    reports_path = tmp_path / "reports.json"
    reports_path.write_text(json.dumps(reports))

    ingest.main(["--reports", str(reports_path), "--manifest", str(inbox / "manifest.json")])

    store = get_store()
    assert len(store.all_matches()) == 1
    assert len(store.all_player_stats()) == 8
    assert get_storage().list_pending() == []


def test_ingest_is_idempotent(tmp_path, monkeypatch, sample_image_bytes):
    _setup(tmp_path, monkeypatch)
    inbox = tmp_path / "inbox"
    key = get_storage().save_upload(sample_image_bytes, "image/jpeg", {})
    stage.main(["--stage-dir", str(inbox)])
    reports_path = tmp_path / "reports.json"
    reports_path.write_text(json.dumps({key: asdict(CARNAGE_BLUE)}))

    ingest.main(["--reports", str(reports_path), "--manifest", str(inbox / "manifest.json")])
    ingest.main(["--reports", str(reports_path), "--manifest", str(inbox / "manifest.json")])

    assert len(get_store().all_matches()) == 1
    assert len(get_store().all_player_stats()) == 8


def test_game_level_dedup_different_image_same_game(tmp_path, monkeypatch, sample_image_bytes):
    _setup(tmp_path, monkeypatch)

    inbox_a = tmp_path / "inbox_a"
    storage = get_storage()

    key_a = storage.save_upload(sample_image_bytes, "image/jpeg", {"uploaded_at": "t0"})
    manifest_a = stage.main(["--stage-dir", str(inbox_a)])
    assert len(manifest_a) == 1

    reports_a = {key_a: asdict(CARNAGE_BLUE)}
    reports_path_a = tmp_path / "reports_a.json"
    reports_path_a.write_text(json.dumps(reports_a))
    ingest.main(["--reports", str(reports_path_a), "--manifest", str(inbox_a / "manifest.json")])

    store = get_store()
    assert len(store.all_matches()) == 1
    assert len(store.all_player_stats()) == 8

    inbox_b = tmp_path / "inbox_b"
    different_bytes = sample_image_bytes + b"X"
    key_b = storage.save_upload(different_bytes, "image/jpeg", {"uploaded_at": "t1"})
    manifest_b = stage.main(["--stage-dir", str(inbox_b)])
    assert len(manifest_b) == 1

    reports_b = {key_b: asdict(CARNAGE_BLUE)}
    reports_path_b = tmp_path / "reports_b.json"
    reports_path_b.write_text(json.dumps(reports_b))
    ingest.main(["--reports", str(reports_path_b), "--manifest", str(inbox_b / "manifest.json")])

    assert len(store.all_matches()) == 1
    assert len(store.all_player_stats()) == 8
