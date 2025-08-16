from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Iterable, Optional

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .state import StateDB, AssetEntry
from .utils import atomic_write, sanitize_filename, mtime_from_exif, set_mtime, apply_tree_permissions

log = logging.getLogger(__name__)


class DownloadError(Exception):
    pass


def _target_path_for(asset, out_base: str, folder_template: str) -> str:
    created: datetime = asset.created
    subfolder = folder_template.format(created, album=sanitize_filename(asset.album or ""))
    fname_base = f"{created:%Y%m%d_%H%M%S}_{asset.id}.{asset.extension}"
    return os.path.join(out_base, subfolder, sanitize_filename(fname_base))


@retry(reraise=True, stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=1, max=30), retry=retry_if_exception_type(DownloadError))
def _download_one(asset, path: str) -> tuple[str, int | None]:
    bytes_written = 0
    with atomic_write(path, mode="wb") as (_, tmp):
        for chunk in asset.downloader():
            if not chunk:
                continue
            tmp.write(chunk)
            bytes_written += len(chunk)
    return path, bytes_written


def sync_assets(
    *,
    assets: Iterable,
    out_base: str,
    folder_template: str,
    state: StateDB,
    concurrency: int = 4,
    dry_run: bool = False,
    umask: str = "002",
    chown: Optional[str] = None,
) -> dict:
    os.makedirs(out_base, exist_ok=True)
    state.load()

    scheduled = []
    skipped = 0
    downloaded = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
        futures = []
        for asset in assets:
            target = _target_path_for(asset, out_base, folder_template)
            if state.exists_same(asset.id, target, asset.size):
                skipped += 1
                continue
            if dry_run:
                log.info(f"DRY-RUN: descargaría {asset.id} → {target}")
                skipped += 1
                continue
            futures.append(ex.submit(_download_one, asset, target))
            scheduled.append((asset, target))

        for fut, (asset, target) in zip(as_completed(futures), scheduled):
            try:
                path, size = fut.result()
                # Ajuste de mtime
                ts = mtime_from_exif(path)
                if ts:
                    set_mtime(path, ts)
                state.upsert(AssetEntry(asset_id=asset.id, path=target, size=size))
                downloaded += 1
            except Exception as e:
                log.error(f"Error descargando {asset.id}: {e}")
                errors += 1

    try:
        state.save()
    except Exception as e:
        log.warning(f"No se pudo guardar el estado: {e}")

    # Permisos finales
    try:
        apply_tree_permissions(out_base, umask=umask, chown=chown)
    except Exception as e:
        log.warning(f"No se pudieron aplicar permisos: {e}")

    return {
        "skipped": skipped,
        "downloaded": downloaded,
        "errors": errors,
    }

