import logging
import os
from logging.handlers import RotatingFileHandler


def setup_logging(
    log_dir: str = os.path.join("artifacts", "logs"),
    filename: str = "api.log",
    level: int = logging.INFO,
) -> None:
    """
    Configure logging to both console and rotating file.
    Keeps decision points/errors for troubleshooting.
    """
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, filename)

    root = logging.getLogger()
    root.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    # Avoid duplicate handlers if reloaded (e.g. uvicorn --reload)
    for handler in list(root.handlers):
        if isinstance(handler, RotatingFileHandler) or isinstance(handler, logging.StreamHandler):
            continue

    # Clear existing handlers created by uvicorn/basicConfig to reduce duplicates
    root.handlers = []
    root.addHandler(console_handler)
    root.addHandler(file_handler)

