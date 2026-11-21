"""Object Storage: surowe HTML/JSON i zrzuty ekranu. Lokalny system plików albo S3 on-premise
(w Docker Compose: SeaweedFS; klient `minio` działa z dowolnym API zgodnym z S3)."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path

from . import config


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, data: bytes, content_type: str) -> str:
        p = (self.root / key).resolve()
        if self.root.resolve() not in p.parents:
            raise ValueError("nieprawidłowy klucz obiektu")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return key

    def get(self, key: str) -> bytes | None:
        p = (self.root / key).resolve()
        if self.root.resolve() not in p.parents or not p.exists():
            return None
        return p.read_bytes()


class S3Storage:
    def __init__(self):
        from minio import Minio

        self.bucket = config.S3_BUCKET
        self.client = Minio(config.S3_ENDPOINT, access_key=config.S3_ACCESS_KEY,
                            secret_key=config.S3_SECRET_KEY, secure=config.S3_SECURE)
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def put(self, key: str, data: bytes, content_type: str) -> str:
        self.client.put_object(self.bucket, key, io.BytesIO(data), len(data), content_type=content_type)
        return key

    def get(self, key: str) -> bytes | None:
        try:
            r = self.client.get_object(self.bucket, key)
            try:
                return r.read()
            finally:
                r.close()
                r.release_conn()
        except Exception:
            return None


_storage = None


def get_storage():
    global _storage
    if _storage is None:
        _storage = S3Storage() if config.STORAGE_BACKEND == "s3" else LocalStorage(config.STORAGE_DIR)
    return _storage


def put_content_addressed(data: bytes, prefix: str, ext: str, content_type: str) -> str:
    """Klucz = sha256 treści → identyczne obiekty zapisywane raz (deduplikacja dokładna)."""
    digest = hashlib.sha256(data).hexdigest()
    return get_storage().put(f"{prefix}/{digest[:2]}/{digest}.{ext}", data, content_type)
