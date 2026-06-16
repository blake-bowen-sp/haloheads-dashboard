import os
import pytest
from haloheads.storage import LocalStorage, get_storage


def test_save_read_meta_list(local_storage):
    key = local_storage.save_upload(b"img", "image/jpeg", {"map": "Lockout"})
    assert key.startswith("pending/")
    assert local_storage.read(key) == b"img"
    assert local_storage.meta(key) == {"map": "Lockout"}
    assert local_storage.list_pending() == [key]


def test_move(local_storage):
    key = local_storage.save_upload(b"img", "image/jpeg", {"map": "Lockout"})
    new_key = local_storage.move(key, "analyzed/")
    assert new_key.startswith("analyzed/")
    assert key not in local_storage.list_pending()
    assert local_storage.read(new_key) == b"img"


def test_meta_missing_sidecar(local_storage):
    key = local_storage.save_upload(b"img", "image/jpeg", {})
    assert local_storage.meta(key) == {}


def test_get_storage_local(tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "bucket"))
    storage = get_storage()
    assert isinstance(storage, LocalStorage)
    key = storage.save_upload(b"roundtrip", "image/jpeg", {"x": "1"})
    assert storage.read(key) == b"roundtrip"
