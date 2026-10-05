"""Fallback illustrative card (large hanzi + pinyin) generated with Pillow
when no photo is found for a sentence's keyword.

Uses Google's open-license "Noto Sans SC" font, downloaded once into
storage/fonts/ on first use (no manual font installation required).
"""
from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from data.sources.http_utils import download_bytes

logger = logging.getLogger(__name__)

FONT_PATH = Path("storage/fonts/NotoSansSC.ttf")
FONT_URL = (
    "https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf"
)

CARD_SIZE = (800, 600)
BACKGROUND = (255, 250, 240)
HANZI_COLOR = (30, 30, 30)
PINYIN_COLOR = (170, 40, 40)
MAX_TEXT_WIDTH = CARD_SIZE[0] - 100


def _ensure_font() -> bool:
    if FONT_PATH.exists():
        return True
    FONT_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = download_bytes(FONT_URL)
    if data is None:
        return False
    FONT_PATH.write_bytes(data)
    return True


def _load_font(size: int, weight: bytes) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(FONT_PATH), size)
    try:
        font.set_variation_by_name(weight)
    except Exception:  # noqa: BLE001 - non-variable font fallback, keep default weight
        pass
    return font


def _fit_font(draw: ImageDraw.ImageDraw, text: str, weight: bytes, start_size: int) -> ImageFont.FreeTypeFont:
    """Shrink the font size until `text` fits within MAX_TEXT_WIDTH."""
    size = start_size
    while size > 20:
        font = _load_font(size, weight)
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= MAX_TEXT_WIDTH:
            return font
        size -= 10
    return _load_font(20, weight)


def generate_fallback_card(hanzi: str, pinyin: str, output_path: Path) -> bool:
    if not _ensure_font():
        logger.error("Could not download the CJK font; skipping fallback card for %r", hanzi)
        return False

    image = Image.new("RGB", CARD_SIZE, BACKGROUND)
    draw = ImageDraw.Draw(image)

    hanzi_font = _fit_font(draw, hanzi, b"Bold", 140)
    pinyin_font = _fit_font(draw, pinyin, b"Regular", 50)

    hanzi_bbox = draw.textbbox((0, 0), hanzi, font=hanzi_font)
    hanzi_w, hanzi_h = hanzi_bbox[2] - hanzi_bbox[0], hanzi_bbox[3] - hanzi_bbox[1]
    pinyin_bbox = draw.textbbox((0, 0), pinyin, font=pinyin_font)
    pinyin_w, pinyin_h = pinyin_bbox[2] - pinyin_bbox[0], pinyin_bbox[3] - pinyin_bbox[1]

    gap = 40
    total_h = hanzi_h + gap + pinyin_h
    start_y = (CARD_SIZE[1] - total_h) // 2

    draw.text(
        ((CARD_SIZE[0] - hanzi_w) // 2 - hanzi_bbox[0], start_y - hanzi_bbox[1]),
        hanzi,
        font=hanzi_font,
        fill=HANZI_COLOR,
    )
    draw.text(
        ((CARD_SIZE[0] - pinyin_w) // 2 - pinyin_bbox[0], start_y + hanzi_h + gap - pinyin_bbox[1]),
        pinyin,
        font=pinyin_font,
        fill=PINYIN_COLOR,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, "PNG")
    return True
