from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from typing import Dict, Optional


@dataclass
class AssetEntry:
    asset_id: str
    path: str
    size: int | None = None
    checksum: str | None = None
    last_seen: float = 0.0


class StateDB:
    def __init__(self, state_path: str) -> None:
        self.state_path = state_path
        self._data: Dict[str, AssetEntry] = {}
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for k, v in raw.get("assets", {}).items():
                    self._data[k] = AssetEntry(**v)
            except Exception:
                self._data = {}
        self._loaded = True

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        payload = {"assets": {k: asdict(v) for k, v in self._data.items()} }
        tmp_path = self.state_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        os.replace(tmp_path, self.state_path)

    def get(self, asset_id: str) -> Optional[AssetEntry]:
        self.load()
        return self._data.get(asset_id)

    def upsert(self, entry: AssetEntry) -> None:
        self.load()
        entry.last_seen = time.time()
        self._data[entry.asset_id] = entry

    def exists_same(self, asset_id: str, path: str, size: int | None) -> bool:
        self.load()
        cur = self._data.get(asset_id)
        if not cur:
            return False
        if cur.path != path:
            return False
        if size is not None and cur.size is not None and size != cur.size:
            return False
        # If file exists on disk and matches recorded size, consider present
        if os.path.exists(path):
            if size is None:
                return True
            try:
                st = os.stat(path)
                return st.st_size == size
            except Exception:
                return False
        return False

