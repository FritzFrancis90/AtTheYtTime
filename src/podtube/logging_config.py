"""Centralized logging configuration for PodTube."""

import logging
import sys
from pathlib import Path
from typing import Optional

try:
    from rich.logging import RichHandler

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


NOISY_LOGGERS = (
    "boto3",
    "botocore",
    "s3transfer",
    "urllib3",
    "PIL",
)


def setup_logging(verbose: bool = False, log_file: Optional[Path] = None) -> None:
    """Configure application-wide logging for CLI and optional file output."""
    level = logging.DEBUG if verbose else logging.INFO
    handlers: list[logging.Handler] = []

    if HAS_RICH:
        console_handler = RichHandler(
            rich_tracebacks=True,
            show_path=verbose,
            markup=False,
            log_time_format="[%H:%M:%S]",
        )
        console_handler.setFormatter(logging.Formatter("%(message)s"))
        handlers.append(console_handler)
    else:
        stream_handler = logging.StreamHandler(sys.stdout)
        fmt = (
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
            if verbose
            else "%(asctime)s | %(levelname)-7s | %(message)s"
        )
        stream_handler.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))
        handlers.append(stream_handler)

    if log_file is not None:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True,
    )

    for logger_name in NOISY_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


class YtDlpLogger:
    """Adapter that routes yt-dlp output into standard Python logging."""

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def debug(self, msg: str) -> None:
        # yt-dlp passes both debug and info messages to debug(); ignore raw progress lines
        if msg.startswith("[download] ") and "%" in msg:
            return
        self._logger.debug(msg)

    def info(self, msg: str) -> None:
        self._logger.debug(msg)

    def warning(self, msg: str) -> None:
        self._logger.debug("yt-dlp warning: %s", msg)

    def error(self, msg: str) -> None:
        self._logger.error("yt-dlp error: %s", msg)

