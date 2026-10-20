"""Single-process bounded disk store, with server-side session ownership."""

import json
import secrets
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path
import pandas as pd
from fastapi import HTTPException
from app.core.config import settings
from app.data.importer import parse_csv, safe_name, typed_frame
from app.data.profiling import profile_dataset
from app.schemas.models import DatasetProfile


@dataclass
class Dataset:
    id: str
    session: str
    path: Path
    kinds: dict[str, str]
    profile: DatasetProfile
    size: int

    def raw(self):
        return pd.DataFrame(json.loads(self.path.read_text()), columns=list(self.kinds), dtype=str)

    def frame(self):
        return typed_frame(self.raw(), self.kinds)


class DatasetStore:
    def __init__(self):
        self.items: dict[str, Dataset] = {}
        self.lock = threading.RLock()
        settings.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root = settings.data_dir / secrets.token_hex(16)
        self.root.mkdir(mode=0o700)

    def cleanup(self):
        with self.lock:
            for key, item in list(self.items.items()):
                if item.profile.expires_at <= time.time():
                    item.path.unlink(missing_ok=True)
                    del self.items[key]

    def add(self, content, name, session, synthetic=False):
        raw, kinds, notes = parse_csv(content, name)
        serialized = raw.to_json(orient="records", force_ascii=False)
        size = len(serialized.encode())
        with self.lock:
            self.cleanup()
            owned = sum(d.session == session for d in self.items.values())
            if (
                owned >= settings.max_session_datasets
                or len(self.items) >= settings.max_datasets
                or sum(d.size for d in self.items.values()) + size > settings.max_store_mb * 1024**2
            ):
                raise HTTPException(
                    429, "Temporary storage is full. Remove an older dataset or wait for it to expire."
                )
            key = secrets.token_urlsafe(24)
            expires = time.time() + settings.dataset_ttl_seconds
            profile = profile_dataset(
                key, safe_name(name), typed_frame(raw, kinds), kinds, notes, expires, synthetic
            )
            path = self.root / f"{key}.json"
            path.write_text(serialized)
            path.chmod(0o600)
            item = Dataset(key, session, path, kinds, profile, size)
            self.items[key] = item
            return item

    def get(self, key, session):
        with self.lock:
            self.cleanup()
            item = self.items.get(key)
            if not item or not secrets.compare_digest(item.session, session):
                raise HTTPException(
                    404, "Dataset not found in this session, or it has expired. Import it again."
                )
            return item

    def list(self, session):
        with self.lock:
            self.cleanup()
            return [d.profile for d in self.items.values() if d.session == session]

    def delete(self, key, session):
        with self.lock:
            item = self.get(key, session)
            item.path.unlink(missing_ok=True)
            del self.items[key]

    def close(self):
        shutil.rmtree(self.root, ignore_errors=True)
