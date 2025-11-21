import logging
import logging.handlers
import os
from pathlib import Path


def _build_logger() -> logging.Logger:
    """
    Central logger used across the project.
    - Respects AGENT_LOG_LEVEL env (defaults to INFO)
    - Avoids duplicate handlers if imported multiple times
    - Writes to stdout and a rotating file in ./agent_log.txt
    """
    log_level = os.getenv("AGENT_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)

    logger = logging.getLogger("agent")
    logger.setLevel(level)
    logger.propagate = False  # prevent duplicate logs if root handlers are configured

    if logger.handlers:
        return logger

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(level)
    logger.addHandler(stream_handler)

    log_file = Path("__file__").parent / "agent_log.txt"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    logger.addHandler(file_handler)

    return logger


logger = _build_logger()

