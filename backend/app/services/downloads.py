"""Download driver/software files to a server folder for discovered devices.

Reuses the canonical remote-fetch helper from ``ingestion`` and stores files
under ``data/downloads/{device_id}/``. Runs inside a FastAPI BackgroundTask,
so it opens its own DB session and tracks progress on the ``DriverDownload``
row (status: pending → downloaded | failed).

Policy (per product decisions):
  * A real, downloadable file is saved and **zipped** on the server.
  * An HTML landing page (not a direct file) is **not** zipped — we keep the
    source URL as a link-only fallback and flag it so the user can open it.
  * Drivers are never indexed into RAG (matches the app's existing policy).
"""

from __future__ import annotations

import io
import logging
import os
import re
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlparse

from app.config import settings
from app.db import SessionLocal
from app.models import DriverDownload
from app.services.ingestion import _guess_file_type, download_document

logger = logging.getLogger(__name__)

# Content that is clearly a human-facing web page rather than a downloadable
# driver/installer artifact. For these we store the URL instead of a file.
_LANDING_PAGE_TYPES = {"html"}


def _filename_from_url(url: str, fallback: str) -> str:
    path = urlparse(url).path
    name = unquote(path.rstrip("/").split("/")[-1]) if "/" in path else ""
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("._")
    return name or fallback


def _safe_stem(title: str, device_id: int, download_id: int) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", title).strip("._")
    stem = stem[:80] or f"device{device_id}"
    return f"{stem}_{download_id}"


def download_driver(download_id: int) -> None:
    """Fetch the driver at ``DriverDownload.source_url`` and store it zipped.

    If the URL resolves to an HTML landing page (no direct file), the download
    is marked ``downloaded`` but ``local_path`` stays empty — the row keeps its
    ``source_url`` as a link-only fallback and records an explanatory error hint.
    """
    db = SessionLocal()
    try:
        record = db.get(DriverDownload, download_id)
        if record is None:
            logger.warning("download_driver(%s): record not found", download_id)
            return

        try:
            logger.info("download_driver(%s): fetching %s", download_id, record.source_url)
            content, content_type = download_document(record.source_url)
            file_type = _guess_file_type(content, content_type)

            if file_type in _LANDING_PAGE_TYPES:
                # Not a real file — keep as a link-only download.
                record.status = "downloaded"
                record.local_path = None
                record.error = (
                    "This URL is a web page, not a direct download. Stored the link "
                    "only — open it to download the driver manually."
                )
                db.commit()
                logger.info("download_driver(%s): landing page, stored URL only", download_id)
                return

            dest_dir = Path(settings.downloads_dir) / str(record.device_id)
            dest_dir.mkdir(parents=True, exist_ok=True)

            inner_name = _filename_from_url(
                record.source_url,
                fallback=f"{_safe_stem(record.title, record.device_id, download_id)}.bin",
            )
            zip_stem = _safe_stem(record.title, record.device_id, download_id)
            zip_path = dest_dir / f"{zip_stem}.zip"

            buffer = io.BytesIO(content)
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(inner_name, buffer.getvalue())

            record.local_path = str(zip_path)
            record.status = "downloaded"
            record.error = None
            db.commit()
            logger.info(
                "download_driver(%s): saved %d bytes → %s",
                download_id, len(content), zip_path,
            )
        except Exception as exc:  # noqa: BLE001 - record the failure reason for the UI
            logger.exception("download_driver(%s): failed", download_id)
            record.status = "failed"
            record.error = str(exc)[:500]
            db.commit()
    finally:
        db.close()
