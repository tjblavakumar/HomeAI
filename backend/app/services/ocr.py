from __future__ import annotations

import io

import pytesseract
from PIL import Image


class OCRUnavailableError(RuntimeError):
    """Raised when the system tesseract/zbar binaries are not installed."""


def extract_text(image_bytes: bytes) -> str:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(image).strip()
    except pytesseract.TesseractNotFoundError as exc:
        raise OCRUnavailableError(
            "tesseract-ocr is not installed. Run: sudo apt-get install tesseract-ocr"
        ) from exc


def decode_barcodes(image_bytes: bytes) -> list[str]:
    try:
        from pyzbar.pyzbar import decode as zbar_decode  # loads libzbar at import time
    except ImportError as exc:
        raise OCRUnavailableError(
            "libzbar is not installed. Run: sudo apt-get install libzbar0"
        ) from exc
    image = Image.open(io.BytesIO(image_bytes))
    return [result.data.decode("utf-8", errors="ignore") for result in zbar_decode(image)]


def guess_product_name(raw_text: str) -> str | None:
    """Best-effort heuristic: the first short, non-empty line is often the product/brand name."""
    for line in raw_text.splitlines():
        line = line.strip()
        if 3 <= len(line) <= 60:
            return line
    return None


def scan_image(image_bytes: bytes) -> dict:
    raw_text = extract_text(image_bytes)
    try:
        barcodes = decode_barcodes(image_bytes)
    except OCRUnavailableError:
        # Barcode decoding is a bonus, not essential — degrade gracefully if libzbar is missing.
        barcodes = []
    return {
        "raw_text": raw_text,
        "barcodes": barcodes,
        "guessed_name": guess_product_name(raw_text),
    }
