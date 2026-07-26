"""Logging configuration module for Radar-Vagas."""

import logging
import sys

from radar_vagas.core.config import Settings


class _DynamicStdoutHandler(logging.StreamHandler):
    """Resolve stdout at emit time so test/CLI capture streams cannot go stale."""

    def emit(self, record: logging.LogRecord) -> None:
        self.stream = sys.stdout
        super().emit(record)


def setup_logging(settings: Settings) -> logging.Logger:
    """Configure consistent formatted logging for the application."""
    logger = logging.getLogger("radar_vagas")
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logger.setLevel(level)

    for existing_handler in logger.handlers:
        existing_handler.close()
    logger.handlers.clear()

    handler = _DynamicStdoutHandler()
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
