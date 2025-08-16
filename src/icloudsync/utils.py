from __future__ import annotations

import contextlib
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Iterator

import piexif


_ILLEGAL_FS_CHARS = re.compile(r"[\\/:*?\"<>|]+")


def sanitize_filename(name: str) -> str:
    name = name.strip().replace("\n", " ").replace("\r", " ")
    name = _ILLEGAL_FS_CHARS.sub("_", name)
    return name[:200] if len(name) > 200 else name


@contextlib.contextmanager
def atomic_write(target_path: str, mode: str = "wb") -> Iterator[tuple[str, tempfile.NamedTemporaryFile]]:
    directory = os.path.dirname(target_path)
    os.makedirs(directory, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, dir=directory) as tmp:
        try:
            yield tmp.name, tmp
            tmp.flush()
            os.fsync(tmp.fileno())
        finally:
            try:
                tmp.close()
            except Exception:
                pass
    os.replace(tmp.name, target_path)


def set_mtime(path: str, timestamp: float) -> None:
    os.utime(path, (timestamp, timestamp))


def mtime_from_exif(path: str) -> float | None:
    try:
        exif_dict = piexif.load(path)
        dt = exif_dict.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal)
        if dt:
            # format: "YYYY:MM:DD HH:MM:SS"
            s = dt.decode("utf-8") if isinstance(dt, bytes) else str(dt)
            parts_date, parts_time = s.split(" ")
            y, m, d = [int(x) for x in parts_date.split(":")]
            hh, mm, ss = [int(x) for x in parts_time.split(":")]
            return time.mktime((y, m, d, hh, mm, ss, 0, 0, -1))
    except Exception:
        return None
    return None


def apply_tree_permissions(root: str, umask: str = "002", chown: str | None = None) -> None:
    try:
        mask = int(umask, 8)
    except Exception:
        mask = 0o002
    # Desired modes: files 0o664, dirs 0o775
    file_mode = 0o666 & ~mask
    dir_mode = 0o777 & ~mask

    uid = -1
    gid = -1
    if chown:
        try:
            uid_s, gid_s = chown.split(":", 1)
            uid = int(uid_s)
            gid = int(gid_s)
        except Exception:
            uid, gid = -1, -1

    for base, dirs, files in os.walk(root):
        for d in dirs:
            p = os.path.join(base, d)
            try:
                os.chmod(p, dir_mode)
                if uid >= 0 or gid >= 0:
                    os.chown(p, uid if uid >= 0 else -1, gid if gid >= 0 else -1)
            except Exception:
                pass
        for f in files:
            p = os.path.join(base, f)
            try:
                os.chmod(p, file_mode)
                if uid >= 0 or gid >= 0:
                    os.chown(p, uid if uid >= 0 else -1, gid if gid >= 0 else -1)
            except Exception:
                pass

