"""MAC-address vendor resolution via the IEEE OUI registry.

Resolves the manufacturer that registered a MAC's OUI (first 3 bytes). The
full IEEE registry (~35k entries) is downloaded once to ``settings.oui_db_path``
and parsed into an in-memory cache. If the download fails (e.g. offline on the
first run) we fall back to a small built-in table so the scan still works.

A MAC only identifies the *manufacturer*, never the product model — the lower
three bytes are a per-unit serial. Callers layer hostname / ports / LLM on top
to guess an actual product.
"""

from __future__ import annotations

import logging
import re
import threading
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

USER_AGENT = "HomeAI/1.0 (+local network scan)"

# Minimal built-in fallback used only if the IEEE file can't be obtained.
_BUILTIN_VENDORS: dict[str, str] = {
    "001B63": "Apple",
    "3C0754": "Apple",
    "A45E60": "Apple",
    "F0189E": "Apple",
    "B827EB": "Raspberry Pi Foundation",
    "DCA632": "Raspberry Pi Foundation",
    "D8EB97": "TP-Link",
    "50C7BF": "TP-Link",
    "00151C": "Canon",
    "F8D111": "Canon",
    "0026AB": "Seiko Epson",
    "001E8F": "Brother",
    "3CD92B": "HP",
    "9C8E99": "HP",
    "0018E7": "Netgear",
    "747548": "Amazon Technologies",
    "68370E": "Amazon Technologies",
    "44650D": "Amazon Technologies",
    "50F5DA": "Sonos",
    "B8E937": "Sonos",
    "D0522A": "Synology",
    "245EBE": "QNAP",
}

# Loaded lazily; protected by a lock so concurrent scan threads load it once.
_cache: dict[str, str] | None = None
_lock = threading.Lock()

# Lines look like: "3C-D9-2B   (hex)		Hewlett Packard"
_HEX_LINE_RE = re.compile(
    r"^\s*([0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2})\s+\(hex\)\s+(.+?)\s*$"
)


def _normalize_prefix(mac: str) -> str | None:
    if not mac:
        return None
    hexonly = re.sub(r"[^0-9A-Fa-f]", "", mac).upper()
    if len(hexonly) < 6:
        return None
    return hexonly[:6]


def _parse_oui_file(text: str) -> dict[str, str]:
    table: dict[str, str] = {}
    for line in text.splitlines():
        m = _HEX_LINE_RE.match(line)
        if not m:
            continue
        prefix = m.group(1).replace("-", "").upper()
        vendor = m.group(2).strip()
        if prefix and vendor:
            table[prefix] = vendor
    return table


def _download_oui(url: str, dest: Path) -> str | None:
    try:
        logger.info("oui: downloading IEEE OUI registry from %s", url)
        with httpx.Client(follow_redirects=True, timeout=60, headers={"User-Agent": USER_AGENT}) as client:
            resp = client.get(url)
            resp.raise_for_status()
            text = resp.text
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
        logger.info("oui: cached registry to %s (%d bytes)", dest, len(text))
        return text
    except Exception:
        logger.exception("oui: failed to download IEEE registry")
        return None


def _load_cache() -> dict[str, str]:
    """Load and parse the OUI DB (from disk, else download), with fallback."""
    path = Path(settings.oui_db_path)
    text: str | None = None

    if path.exists() and path.stat().st_size > 0:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            logger.exception("oui: failed to read %s", path)

    if text is None:
        text = _download_oui(settings.oui_db_url, path)

    if text:
        table = _parse_oui_file(text)
        if table:
            # Merge built-ins as a backstop for anything missing.
            merged = dict(_BUILTIN_VENDORS)
            merged.update(table)
            logger.info("oui: loaded %d vendor prefixes", len(merged))
            return merged

    logger.warning("oui: using built-in fallback table (%d prefixes)", len(_BUILTIN_VENDORS))
    return dict(_BUILTIN_VENDORS)


def _get_cache() -> dict[str, str]:
    global _cache
    if _cache is None:
        with _lock:
            if _cache is None:
                _cache = _load_cache()
    return _cache


def lookup_vendor(mac: str | None) -> str | None:
    """Return the manufacturer for *mac*, or None if unknown."""
    prefix = _normalize_prefix(mac or "")
    if not prefix:
        return None
    return _get_cache().get(prefix)


def ensure_loaded() -> int:
    """Force-load the DB (used at startup to warm the cache). Returns entry count."""
    return len(_get_cache())
