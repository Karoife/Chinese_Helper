"""Search a freely-licensed illustrative image via the Openverse API
(https://openverse.org), which aggregates Creative Commons content and
requires no API key for this kind of light, personal use.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

import requests

from data.sources.http_utils import download_bytes

logger = logging.getLogger(__name__)

OPENVERSE_URL = "https://api.openverse.org/v1/images/"
SEARCH_TIMEOUT = 15
RESULTS_TO_TRY = 5


def search_image(keyword: str) -> Optional[Tuple[bytes, str]]:
    """Return (image_bytes, attribution_text) for the first usable result."""
    try:
        response = requests.get(
            OPENVERSE_URL,
            params={"q": keyword, "page_size": RESULTS_TO_TRY, "mature": "false"},
            timeout=SEARCH_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        logger.warning("Openverse search failed for %r: %s", keyword, exc)
        return None
    except ValueError as exc:  # invalid JSON
        logger.warning("Openverse returned invalid JSON for %r: %s", keyword, exc)
        return None

    for result in data.get("results", []):
        if result.get("mature") or not result.get("url"):
            continue
        image_bytes = download_bytes(result["url"], retries=2)
        if not image_bytes:
            continue
        attribution = result.get("attribution") or (
            f"\"{result.get('title') or keyword}\" by {result.get('creator') or 'unknown'} "
            f"({(result.get('license') or '').upper()}) via Openverse"
        )
        return image_bytes, attribution

    logger.info("No usable Openverse image found for %r", keyword)
    return None
