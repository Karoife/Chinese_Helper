"""Shared HTTP download helper with retries/backoff for all data sources."""
from __future__ import annotations

import logging
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF = 2.0


def download_bytes(
    url: str,
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
    timeout: int = DEFAULT_TIMEOUT,
) -> Optional[bytes]:
    """GET `url` and return its raw bytes, or None if every attempt failed."""
    last_error: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response.content
        except requests.RequestException as exc:
            last_error = exc
            logger.warning(
                "Download attempt %d/%d failed for %s: %s", attempt, retries, url, exc
            )
            if attempt < retries:
                time.sleep(backoff * attempt)
    logger.error("Giving up downloading %s after %d attempts: %s", url, retries, last_error)
    return None
