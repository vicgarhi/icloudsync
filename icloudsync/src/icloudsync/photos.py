from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable, Iterator, Optional

try:
    from pyicloud import PyiCloudService
except Exception:  # pragma: no cover - optional at dev time
    PyiCloudService = None  # type: ignore

log = logging.getLogger(__name__)


@dataclass
class PhotoAsset:
    id: str
    created: datetime
    filename: str
    size: int | None
    album: str | None
    extension: str
    downloader: Callable[[], Iterator[bytes]]


class ICloudPhotos:
    def __init__(self, api: "PyiCloudService") -> None:
        self.api = api

    def _iter_album_assets(self, album, album_name: Optional[str]) -> Iterator[PhotoAsset]:
        # pyicloud-ipd exposes PhotoAsset with attributes. We stream original.
        for asset in album:
            try:
                created = getattr(asset, "created", None) or getattr(asset, "added_date", None) or getattr(asset, "creation_date", None)
                if created is None:
                    created = datetime.utcnow()
                filename = getattr(asset, "filename", None) or f"{getattr(asset, 'id', 'asset')}.jpg"
                ext = filename.split(".")[-1].lower()

                def make_downloader(a=asset):
                    def _dl() -> Iterator[bytes]:
                        resp = a.download()  # type: ignore[attr-defined]
                        if hasattr(resp, "iter_content"):
                            yield from resp.iter_content(chunk_size=1024 * 1024)
                        elif hasattr(resp, "raw") and hasattr(resp.raw, "stream"):
                            yield from resp.raw.stream(1024 * 1024, decode_content=True)
                        else:
                            data = getattr(resp, "content", None) or getattr(resp, "data", None)
                            if data:
                                yield data
                    return _dl

                yield PhotoAsset(
                    id=str(getattr(asset, "id", getattr(asset, "_asset_id", "unknown"))),
                    created=created,
                    filename=filename,
                    size=getattr(asset, "size", None),
                    album=album_name,
                    extension=ext,
                    downloader=make_downloader(),
                )
            except Exception as e:
                log.warning(f"No se pudo procesar un asset del álbum {album_name}: {e}")

    def iter_library(self, recent: Optional[int] = None) -> Iterator[PhotoAsset]:
        photos = self.api.photos  # type: ignore[attr-defined]
        # Prefer 'all' if exists, else fallback to albums['All Photos']
        try:
            collection = photos.all  # type: ignore[attr-defined]
        except Exception:
            collection = photos.albums.get("All Photos")  # type: ignore[attr-defined]
        items = list(collection) if recent else collection
        if recent and hasattr(items, "__len__"):
            items = items[-recent:]
        yield from self._iter_album_assets(items, album_name=None)

    def list_shared_albums(self) -> list[tuple[str, object]]:
        photos = self.api.photos  # type: ignore[attr-defined]
        albums = []
        try:
            shared = photos.shared_albums  # type: ignore[attr-defined]
            for name, album in (shared.items() if hasattr(shared, "items") else []):
                albums.append((name, album))
        except Exception:
            # Fallback: filter albums by is_shared attribute
            for name, album in photos.albums.items():  # type: ignore[attr-defined]
                try:
                    if getattr(album, "is_shared", False):
                        albums.append((name, album))
                except Exception:
                    continue
        return albums

    def iter_shared(self, recent: Optional[int] = None, include: Optional[str] = None, exclude: Optional[str] = None) -> Iterator[PhotoAsset]:
        import re

        albums = self.list_shared_albums()
        inc = re.compile(include) if include else None
        exc = re.compile(exclude) if exclude else None

        for name, album in albums:
            if inc and not inc.search(name):
                continue
            if exc and exc.search(name):
                continue
            items = list(album) if recent else album
            if recent and hasattr(items, "__len__"):
                items = items[-recent:]
            yield from self._iter_album_assets(items, album_name=name)

