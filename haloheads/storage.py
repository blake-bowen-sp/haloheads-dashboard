import json
import os
import uuid
from pathlib import Path
from typing import Protocol


class Storage(Protocol):
    def save_upload(self, data: bytes, content_type: str, meta: dict) -> str: ...
    def list_pending(self) -> list[str]: ...
    def read(self, key: str) -> bytes: ...
    def move(self, key: str, dest_prefix: str) -> str: ...
    def meta(self, key: str) -> dict: ...


class LocalStorage:
    def __init__(self, root: str) -> None:
        self._root = Path(root)
        for sub in ("pending", "analyzed", "failed"):
            (self._root / sub).mkdir(parents=True, exist_ok=True)

    def save_upload(self, data: bytes, content_type: str, meta: dict) -> str:
        uid = str(uuid.uuid4())
        key = f"pending/{uid}.jpg"
        (self._root / key).write_bytes(data)
        sidecar = self._root / f"pending/{uid}.json"
        sidecar.write_text(json.dumps(meta))
        return key

    def list_pending(self) -> list[str]:
        pending = self._root / "pending"
        return sorted(f"pending/{p.name}" for p in pending.glob("*.jpg"))

    def read(self, key: str) -> bytes:
        return (self._root / key).read_bytes()

    def move(self, key: str, dest_prefix: str) -> str:
        src = self._root / key
        stem = src.stem
        dest_dir = self._root / dest_prefix.rstrip("/")
        dest_dir.mkdir(parents=True, exist_ok=True)
        new_key = f"{dest_prefix.rstrip('/')}/{stem}.jpg"
        src.rename(dest_dir / f"{stem}.jpg")
        sidecar_src = src.parent / f"{stem}.json"
        if sidecar_src.exists():
            sidecar_src.rename(dest_dir / f"{stem}.json")
        return new_key

    def meta(self, key: str) -> dict:
        stem = Path(key).stem
        sidecar = self._root / Path(key).parent / f"{stem}.json"
        if not sidecar.exists():
            return {}
        return json.loads(sidecar.read_text())


class GcsStorage:
    def __init__(self, bucket_name: str) -> None:
        self._bucket_name = bucket_name
        import google.cloud.storage as gcs
        self._client = gcs.Client()
        self._bucket = self._client.bucket(bucket_name)

    def save_upload(self, data: bytes, content_type: str, meta: dict) -> str:
        uid = str(uuid.uuid4())
        key = f"pending/{uid}.jpg"
        blob = self._bucket.blob(key)
        blob.metadata = meta
        blob.upload_from_string(data, content_type=content_type)
        return key

    def list_pending(self) -> list[str]:
        blobs = self._client.list_blobs(self._bucket_name, prefix="pending/")
        return sorted(b.name for b in blobs if b.name.endswith(".jpg"))

    def read(self, key: str) -> bytes:
        return self._bucket.blob(key).download_as_bytes()

    def move(self, key: str, dest_prefix: str) -> str:
        src = self._bucket.blob(key)
        stem = Path(key).stem
        new_key = f"{dest_prefix.rstrip('/')}/{stem}.jpg"
        dest = self._bucket.copy_blob(src, self._bucket, new_key)
        dest.metadata = src.metadata or {}
        dest.patch()
        src.delete()
        return new_key

    def meta(self, key: str) -> dict:
        blob = self._bucket.blob(key)
        blob.reload()
        return blob.metadata or {}


def get_storage() -> Storage:
    backend = os.environ.get("STORAGE_BACKEND", "local")
    if backend == "local":
        root = os.environ.get("STORAGE_DIR", "./.localdata/bucket")
        return LocalStorage(root)
    if backend == "gcs":
        bucket = os.environ.get("GCS_BUCKET", "haloheads-uploads")
        return GcsStorage(bucket)
    raise ValueError(f"Unknown STORAGE_BACKEND: {backend!r}")
