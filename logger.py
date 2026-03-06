from __future__ import annotations

import logging
import os
from pathlib import Path

from config import LOG_DIR

LOGGER_NAME = "auto_woo_catalog"


class _ContextDefaultsFilter(logging.Filter):
    """Ensure contextual log fields always exist for the formatter."""

    def filter(self, record: logging.LogRecord) -> bool:
        defaults = {
            "product_title": "-",
            "image_url": "-",
            "category_id": "-",
            "outcome": "-",
        }
        for field_name, default_value in defaults.items():
            if not hasattr(record, field_name):
                setattr(record, field_name, default_value)
        return True


def safe_extra(extra: dict | None = None) -> dict[str, str]:
    """Return a dictionary suitable for passing as the ``extra`` argument to
    ``logging`` calls.

    The pipeline formatter expects the following keys in ``extra``; when any
    of them are missing we supply a safe ``"-"`` placeholder so that the
    formatter never raises ``KeyError``.
    """
    defaults = {
        "product_title": "-",
        "image_url": "-",
        "category_id": "-",
        "outcome": "-",
    }
    if extra:
        defaults.update(extra)
    return defaults


def build_log_extra(
    product_title: str | None = None,
    image_url: str | None = None,
    category_id: int | str | None = None,
    outcome: str | None = None,
) -> dict[str, str]:
    """Create a consistent `extra` payload for structured pipeline logging.

    This helper is used by the various pipeline modules when they already have
    specific pieces of context. It simply wraps the values in
    :func:`safe_extra` so that callers don't need to worry about missing
    fields.
    """
    return safe_extra(
        {
            "product_title": product_title or "-",
            "image_url": image_url or "-",
            "category_id": str(category_id) if category_id is not None else "-",
            "outcome": outcome or "-",
        }
    )


def get_logger() -> logging.Logger:
    """Create a shared console and file logger for the whole pipeline."""
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    log_dir = Path(os.getenv("LOG_DIR", str(LOG_DIR)))
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.INFO)
    logger.addFilter(_ContextDefaultsFilter())

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | product=%(product_title)s | "
        "image=%(image_url)s | category=%(category_id)s | outcome=%(outcome)s | %(message)s"
    )

    file_handler = logging.FileHandler(log_dir / "pipeline.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.propagate = False
    return logger
