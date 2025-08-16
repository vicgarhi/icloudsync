from __future__ import annotations

import os
import yaml
from dataclasses import dataclass, field
from typing import Any, Dict


DEFAULTS = {
    "TIMEZONE": os.environ.get("TZ", "UTC"),
    "OUT_MAIN": "/data",
    "OUT_SHARED": "/data/Compartidos",
    "COOKIES_DIR": "/cookies",
    "LOG_FILE": "/logs/icloud_sync.log",
    "FOLDER_TEMPLATE_LIBRARY": "{:%Y/%m}",
    "FOLDER_TEMPLATE_SHARED": "{album}/{:%Y/%m}",
    "RECENT": None,
    "CONCURRENCY": 4,
    "RETRY_MAX": 5,
    "RETRY_BACKOFF": 2.0,
    "UMASK": "002",
}


@dataclass
class Config:
    apple_id: str | None = None
    timezone: str = DEFAULTS["TIMEZONE"]
    out_main: str = DEFAULTS["OUT_MAIN"]
    out_shared: str = DEFAULTS["OUT_SHARED"]
    cookies_dir: str = DEFAULTS["COOKIES_DIR"]
    log_file: str | None = DEFAULTS["LOG_FILE"]
    folder_template_library: str = DEFAULTS["FOLDER_TEMPLATE_LIBRARY"]
    folder_template_shared: str = DEFAULTS["FOLDER_TEMPLATE_SHARED"]
    recent: int | None = DEFAULTS["RECENT"]
    concurrency: int = DEFAULTS["CONCURRENCY"]
    retry_max: int = DEFAULTS["RETRY_MAX"]
    retry_backoff: float = DEFAULTS["RETRY_BACKOFF"]
    umask: str = DEFAULTS["UMASK"]
    chown: str | None = None  # "UID:GID"
    log_level: str = "INFO"
    no_log_file: bool = False
    dry_run: bool = False
    yaml_path: str | None = None

    extra: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_yaml(path: str | None) -> Dict[str, Any]:
        if not path:
            return {}
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        # Normalize keys to env-style
        return {k.upper(): v for k, v in data.items()}

    @staticmethod
    def from_env() -> Dict[str, Any]:
        keys = [
            "APPLE_ID",
            "TIMEZONE",
            "OUT_MAIN",
            "OUT_SHARED",
            "COOKIES_DIR",
            "LOG_FILE",
            "FOLDER_TEMPLATE_LIBRARY",
            "FOLDER_TEMPLATE_SHARED",
            "RECENT",
            "CONCURRENCY",
            "RETRY_MAX",
            "RETRY_BACKOFF",
            "UMASK",
            "CHOWN",
            "LOG_LEVEL",
            "NO_LOG_FILE",
            "DRY_RUN",
        ]
        env: Dict[str, Any] = {}
        for k in keys:
            if k in os.environ:
                env[k] = os.environ[k]
        return env

    @staticmethod
    def coerce_types(cfg: Dict[str, Any]) -> Dict[str, Any]:
        out = dict(cfg)
        if "RECENT" in out and out["RECENT"] is not None:
            try:
                out["RECENT"] = int(out["RECENT"]) if out["RECENT"] != "" else None
            except ValueError:
                out["RECENT"] = None
        if "CONCURRENCY" in out:
            out["CONCURRENCY"] = int(out["CONCURRENCY"])  # may raise
        if "RETRY_MAX" in out:
            out["RETRY_MAX"] = int(out["RETRY_MAX"])  # may raise
        if "RETRY_BACKOFF" in out:
            out["RETRY_BACKOFF"] = float(out["RETRY_BACKOFF"])  # may raise
        if "NO_LOG_FILE" in out:
            out["NO_LOG_FILE"] = str(out["NO_LOG_FILE"]).lower() in ("1", "true", "yes")
        if "DRY_RUN" in out:
            out["DRY_RUN"] = str(out["DRY_RUN"]).lower() in ("1", "true", "yes")
        return out

    @classmethod
    def merge(cls, *, yaml_path: str | None = None, cli: Dict[str, Any] | None = None) -> "Config":
        yaml_cfg = cls.from_yaml(yaml_path)
        env_cfg = cls.from_env()
        cli_cfg = {k.upper(): v for k, v in (cli or {}).items() if v is not None}

        merged: Dict[str, Any] = {}
        merged.update(DEFAULTS)
        merged.update(yaml_cfg)
        merged.update(env_cfg)
        merged.update(cli_cfg)
        merged = cls.coerce_types(merged)

        cfg = cls(
            apple_id=merged.get("APPLE_ID"),
            timezone=merged.get("TIMEZONE", DEFAULTS["TIMEZONE"]),
            out_main=merged.get("OUT_MAIN", DEFAULTS["OUT_MAIN"]),
            out_shared=merged.get("OUT_SHARED", DEFAULTS["OUT_SHARED"]),
            cookies_dir=merged.get("COOKIES_DIR", DEFAULTS["COOKIES_DIR"]),
            log_file=None if merged.get("NO_LOG_FILE") else merged.get("LOG_FILE", DEFAULTS["LOG_FILE"]),
            folder_template_library=merged.get("FOLDER_TEMPLATE_LIBRARY", DEFAULTS["FOLDER_TEMPLATE_LIBRARY"]),
            folder_template_shared=merged.get("FOLDER_TEMPLATE_SHARED", DEFAULTS["FOLDER_TEMPLATE_SHARED"]),
            recent=merged.get("RECENT", DEFAULTS["RECENT"]),
            concurrency=merged.get("CONCURRENCY", DEFAULTS["CONCURRENCY"]),
            retry_max=merged.get("RETRY_MAX", DEFAULTS["RETRY_MAX"]),
            retry_backoff=merged.get("RETRY_BACKOFF", DEFAULTS["RETRY_BACKOFF"]),
            umask=str(merged.get("UMASK", DEFAULTS["UMASK"])),
            chown=merged.get("CHOWN"),
            log_level=merged.get("LOG_LEVEL", "INFO"),
            no_log_file=merged.get("NO_LOG_FILE", False),
            dry_run=merged.get("DRY_RUN", False),
            yaml_path=yaml_path,
            extra={k: v for k, v in merged.items() if k not in DEFAULTS and k not in {"APPLE_ID", "CHOWN", "LOG_LEVEL", "NO_LOG_FILE", "DRY_RUN"}},
        )
        return cfg

