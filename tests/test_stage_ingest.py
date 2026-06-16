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
