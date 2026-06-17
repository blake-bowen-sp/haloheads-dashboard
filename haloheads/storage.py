import json
import os
import uuid
from pathlib import Path
from typing import Protocol

_EXT_BY_TYPE = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "video/x-matroska": ".mkv",
}
_MEDIA_EXTS = set(_EXT_BY_TYPE.values())


def _ext_for(content_type: str) -> str:
    return _EXT_BY_TYPE.get((content_type or "").split(";")[0].strip().lower(), ".jpg")


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
        ext = _ext_for(content_type)
        key = f"pending/{uid}{ext}"
        (self._root / key).write_bytes(data)
        sidecar = self._root / f"pending/{uid}.json"
        sidecar.write_text(json.dumps(meta))
        return key

    def list_pending(self) -> list[str]:
        pending = self._root / "pending"
        return sorted(
            f"pending/{p.name}" for p in pending.iterdir()
            if p.is_file() and p.suffix.lower() in _MEDIA_EXTS
        )

    def read(self, key: str) -> bytes:
        return (self._root / key).read_bytes()

    def move(self, key: str, dest_prefix: str) -> str:
        src = self._root / key
        stem, suffix = src.stem, src.suffix
        dest_dir = self._root / dest_prefix.rstrip("/")
        dest_dir.mkdir(parents=True, exist_ok=True)
        new_key = f"{dest_prefix.rstrip('/')}/{stem}{suffix}"
        src.rename(dest_dir / f"{stem}{suffix}")
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
        ext = _ext_for(content_type)
        key = f"pending/{uid}{ext}"
        blob = self._bucket.blob(key)
        blob.metadata = meta
        blob.upload_from_string(data, content_type=content_type)
        return key

    def list_pending(self) -> list[str]:
        blobs = self._client.list_blobs(self._bucket_name, prefix="pending/")
        return sorted(b.name for b in blobs if Path(b.name).suffix.lower() in _MEDIA_EXTS)

    def read(self, key: str) -> bytes:
        return self._bucket.blob(key).download_as_bytes()

    def move(self, key: str, dest_prefix: str) -> str:
        src = self._bucket.blob(key)
        stem, suffix = Path(key).stem, Path(key).suffix
        new_key = f"{dest_prefix.rstrip('/')}/{stem}{suffix}"
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
