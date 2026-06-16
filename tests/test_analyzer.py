import pytest
from scripts import analyze
from haloheads.storage import get_storage
from haloheads.store import get_store


def _setup(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "bucket"))
    monkeypatch.setenv("STORE_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "stats.db"))
    monkeypatch.setenv("HALOHEADS_FAKE_EXTRACT", "1")


def test_bucket_flow(tmp_path, monkeypatch, sample_image_bytes):
    _setup(tmp_path, monkeypatch)

    storage = get_storage()
    storage.save_upload(sample_image_bytes, "image/jpeg", {})

    analyze.main([])

    store = get_store()
    assert len(store.all_matches()) == 1
    assert len(store.all_player_stats()) == 8
    assert storage.list_pending() == []


def test_idempotency(tmp_path, monkeypatch, sample_image_bytes):
    _setup(tmp_path, monkeypatch)

    storage = get_storage()
    storage.save_upload(sample_image_bytes, "image/jpeg", {})
    analyze.main([])

    storage2 = get_storage()
    storage2.save_upload(sample_image_bytes, "image/jpeg", {})

    analyze.main([])

    store = get_store()
    assert len(store.all_matches()) == 1
    assert len(store.all_player_stats()) == 8
    assert get_storage().list_pending() == []


def test_dry_run(tmp_path, monkeypatch, sample_image_bytes):
    _setup(tmp_path, monkeypatch)

    storage = get_storage()
    pending_key = storage.save_upload(sample_image_bytes, "image/jpeg", {})

    analyze.main(["--dry-run"])

    store = get_store()
    assert len(store.all_matches()) == 0
    assert storage.list_pending() == [pending_key]
