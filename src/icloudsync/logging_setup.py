import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging(log_level: str = "INFO", log_file: str | None = None) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    # Clear existing handlers to avoid duplicate logs when reconfiguring
    if root.handlers:
        for h in list(root.handlers):
            root.removeHandler(h)

    fmt = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.setLevel(level)
    root.addHandler(sh)

    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        fh = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5)
        fh.setFormatter(fmt)
        fh.setLevel(level)
        root.addHandler(fh)

