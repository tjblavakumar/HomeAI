"""Local-network device scanning + manual/driver actions.

Endpoints:
  POST   /network/scan                          run a scan, upsert devices
  GET    /network/devices                        list known devices (+ matches)
  POST   /network/devices/{id}/suggest           web-search manuals/drivers
  POST   /network/devices/{id}/add-manuals       create/link item + index manuals (RAG)
  POST   /network/devices/{id}/download-drivers   download drivers to server
  GET    /network/devices/{id}/downloads          list driver downloads
  PATCH  /network/devices/{id}                    dismiss / relabel
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Category, Device, Document, DriverDownload, Item
from app.schemas import (
    AddManualsRequest,
    AddManualsResponse,
    DeviceSuggestion,
    DeviceUpdate,
    DeviceWithMatch,
    DownloadDriversRequest,
    DriverDownloadOut,
    ItemMatch,
    ScanRequest,
    SuggestResponse,
)
from app.services import llm, network_scan, search_provider
from app.services.downloads import download_driver
from app.services.ingestion import process_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/network", tags=["network"])


# Map a guessed device_type to one of the seeded categories.
_DEVICE_TYPE_TO_CATEGORY = {
    "printer": "Electronics",
    "router": "Electronics",
    "nas": "Electronics",
    "computer": "Electronics",
    "generic": "Electronics",
}
_DEFAULT_CATEGORY = "Other"


# ── helpers ──────────────────────────────────────────────────────────


def _device_label(device: Device) -> str:
    if device.label:
        return device.label
    parts = [device.vendor, device.device_type]
    label = " ".join(p for p in parts if p).strip()
    return label or device.hostname or device.ip


def _compute_matches(device: Device, items: list[Item]) -> list[ItemMatch]:
    """Find catalog items that may correspond to *device*.

    - "linked": device.item_id points at the item.
    - "strong": vendor AND (hostname/model token) both appear in the item.
    - "possible": vendor/brand overlap only.
    """
    matches: list[ItemMatch] = []
    vendor = (device.vendor or "").lower().strip()
    host = (device.hostname or "").lower()

    for item in items:
        if device.item_id and item.id == device.item_id:
            matches.append(ItemMatch(item_id=item.id, item_name=item.name, confidence="linked"))
            continue

        brand = (item.brand or "").lower()
        name = (item.name or "").lower()
        model = (item.model_number or "").lower()
        haystack = f"{brand} {name} {model}"

        vendor_hit = bool(vendor) and (vendor in haystack or vendor in host)
        model_hit = bool(model) and (model in host or model in name)

        if vendor_hit and model_hit:
            matches.append(ItemMatch(item_id=item.id, item_name=item.name, confidence="strong"))
        elif vendor_hit:
            matches.append(ItemMatch(item_id=item.id, item_name=item.name, confidence="possible"))

    # Prefer strongest matches first.
    order = {"linked": 0, "strong": 1, "possible": 2}
    matches.sort(key=lambda m: order.get(m.confidence, 3))
    return matches


def _to_device_with_match(device: Device, items: list[Item]) -> DeviceWithMatch:
    dto = DeviceWithMatch.model_validate(device)
    dto.matches = _compute_matches(device, items)
    return dto


def _pick_category(db: Session, device_type: str | None) -> Category:
    name = _DEVICE_TYPE_TO_CATEGORY.get(device_type or "", _DEFAULT_CATEGORY)
    category = db.execute(select(Category).where(Category.name == name)).scalar_one_or_none()
    if category is None:
        # Fall back to any category so item creation never hard-fails.
        category = db.execute(select(Category)).scalars().first()
        if category is None:
            raise HTTPException(status_code=500, detail="No categories are configured")
    return category


def _search_query_for(device: Device) -> str:
    parts = [device.vendor or "", device.hostname or "", device.device_type or ""]
    label = " ".join(p for p in parts if p).strip()
    if not label:
        label = device.ip
    return f"{label} manual and driver download official"


# ── endpoints ────────────────────────────────────────────────────────


@router.post("/scan", response_model=list[DeviceWithMatch])
def scan(payload: ScanRequest | None = None, db: Session = Depends(get_db)) -> list[DeviceWithMatch]:
    req = payload or ScanRequest()
    try:
        discovered = network_scan.scan_network(tcp_probe=req.tcp_probe)
    except network_scan.NetworkScanUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    now = datetime.utcnow()
    for d in discovered:
        # Merge by MAC when available, else by IP.
        existing: Device | None = None
        if d.mac:
            existing = db.execute(
                select(Device).where(Device.mac == d.mac)
            ).scalar_one_or_none()
        if existing is None:
            existing = db.execute(
                select(Device).where(Device.ip == d.ip)
            ).scalar_one_or_none()

        ports_csv = ",".join(str(p) for p in d.open_ports) if d.open_ports else None
        if existing is None:
            device = Device(
                mac=d.mac,
                ip=d.ip,
                hostname=d.hostname,
                vendor=d.vendor,
                device_type=d.device_type,
                label=d.label,
                open_ports=ports_csv,
                first_seen=now,
                last_seen=now,
            )
            db.add(device)
        else:
            existing.ip = d.ip
            existing.last_seen = now
            # Refresh enrichment if we learned more this round.
            existing.hostname = d.hostname or existing.hostname
            existing.vendor = d.vendor or existing.vendor
            existing.device_type = d.device_type or existing.device_type
            # Refresh the auto label only while the device is unlinked; once the
            # user has linked/renamed it we leave their label alone.
            if d.label and existing.item_id is None:
                existing.label = d.label
            if ports_csv:
                existing.open_ports = ports_csv
            # A device that reappears after being dismissed becomes visible again.
            if existing.status == "dismissed":
                existing.status = "discovered"
    db.commit()

    items = list(db.execute(select(Item)).scalars())
    devices = list(db.execute(select(Device)).scalars())
    return [_to_device_with_match(dev, items) for dev in devices]


@router.get("/devices", response_model=list[DeviceWithMatch])
def list_devices(
    include_dismissed: bool = False, db: Session = Depends(get_db)
) -> list[DeviceWithMatch]:
    query = select(Device)
    if not include_dismissed:
        query = query.where(Device.status != "dismissed")
    devices = list(db.execute(query).scalars())
    items = list(db.execute(select(Item)).scalars())
    return [_to_device_with_match(dev, items) for dev in devices]


@router.post("/devices/{device_id}/suggest", response_model=SuggestResponse)
def suggest_docs(device_id: int, db: Session = Depends(get_db)) -> SuggestResponse:
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    query = _search_query_for(device)
    raw = search_provider.search_with_fallback(query, max_results=12)
    if not raw:
        return SuggestResponse(
            device_id=device_id,
            query=query,
            message="Couldn't find anything online for this device. Try relabeling it "
            "with a more specific brand/model, then search again.",
        )

    product = _device_label(device)
    try:
        categorized = llm.categorize_search_results(
            product,
            [{"title": r.title, "url": r.url, "snippet": r.snippet} for r in raw],
        )
    except llm.LLMNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    suggestions = [DeviceSuggestion(**doc) for doc in categorized]
    return SuggestResponse(device_id=device_id, query=query, suggestions=suggestions)


@router.post("/devices/{device_id}/add-manuals", response_model=AddManualsResponse, status_code=201)
def add_manuals(
    device_id: int,
    payload: AddManualsRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> AddManualsResponse:
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Only manuals/troubleshooting go into RAG. Silently ignore other types here.
    manuals = [m for m in payload.manuals if m.doc_type in ("manual", "troubleshooting")]
    if not manuals:
        raise HTTPException(status_code=400, detail="No manual/troubleshooting documents provided")

    # Resolve or create the linked item.
    item: Item | None = db.get(Item, device.item_id) if device.item_id else None
    if item is None:
        category = (
            db.get(Category, payload.category_id)
            if payload.category_id
            else _pick_category(db, device.device_type)
        )
        if category is None:
            raise HTTPException(status_code=404, detail="Category not found")
        item = Item(
            name=payload.item_name or _device_label(device),
            brand=device.vendor,
            category_id=category.id,
        )
        db.add(item)
        db.flush()
        device.item_id = item.id
        device.status = "linked"

    document_ids: list[int] = []
    for m in manuals:
        document = Document(
            item_id=item.id,
            doc_type=m.doc_type,
            title=m.title,
            source_url=m.source_url,
            indexed_status="pending",
        )
        db.add(document)
        db.flush()
        document_ids.append(document.id)

    db.commit()

    for doc_id in document_ids:
        background_tasks.add_task(process_document, doc_id)

    return AddManualsResponse(item_id=item.id, document_ids=document_ids)


@router.post(
    "/devices/{device_id}/download-drivers",
    response_model=list[DriverDownloadOut],
    status_code=201,
)
def download_drivers(
    device_id: int,
    payload: DownloadDriversRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> list[DriverDownload]:
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    if not payload.drivers:
        raise HTTPException(status_code=400, detail="No drivers provided")

    saved: list[DriverDownload] = []
    for d in payload.drivers:
        record = DriverDownload(
            device_id=device_id,
            title=d.title,
            source_url=d.source_url,
            status="pending",
        )
        db.add(record)
        db.flush()
        saved.append(record)
    db.commit()
    for record in saved:
        db.refresh(record)
        background_tasks.add_task(download_driver, record.id)
    return saved


@router.get("/devices/{device_id}/downloads", response_model=list[DriverDownloadOut])
def list_downloads(device_id: int, db: Session = Depends(get_db)) -> list[DriverDownload]:
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return list(
        db.execute(
            select(DriverDownload).where(DriverDownload.device_id == device_id)
        ).scalars()
    )


@router.patch("/devices/{device_id}", response_model=DeviceWithMatch)
def update_device(
    device_id: int, payload: DeviceUpdate, db: Session = Depends(get_db)
) -> DeviceWithMatch:
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if payload.status is not None:
        if payload.status not in ("discovered", "dismissed", "linked"):
            raise HTTPException(status_code=400, detail="Invalid status")
        device.status = payload.status
    if payload.label is not None:
        device.label = payload.label or None
    db.commit()
    db.refresh(device)
    items = list(db.execute(select(Item)).scalars())
    return _to_device_with_match(device, items)
