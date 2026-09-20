from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ScanRequest(BaseModel):
    tcp_probe: bool | None = None  # override settings.scan_tcp_probe for this scan


class ItemMatch(BaseModel):
    """A possible or strong link between a discovered device and a saved item."""

    item_id: int
    item_name: str
    # "linked": device already linked to this item;
    # "strong": vendor + model both matched;
    # "possible": only a vendor/brand overlap.
    confidence: str


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mac: str | None
    ip: str
    hostname: str | None
    vendor: str | None
    label: str | None
    device_type: str | None
    open_ports: str | None
    status: str
    item_id: int | None
    first_seen: datetime
    last_seen: datetime


class DeviceWithMatch(DeviceOut):
    """Device plus computed matches against the catalog (not persisted)."""

    matches: list[ItemMatch] = []


class DriverDownloadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: int
    title: str
    source_url: str
    local_path: str | None
    status: str
    error: str | None
    created_at: datetime


class DeviceSuggestion(BaseModel):
    doc_type: str  # manual | troubleshooting | driver | accessory
    title: str
    source_url: str
    reason: str | None = None


class SuggestResponse(BaseModel):
    device_id: int
    query: str
    suggestions: list[DeviceSuggestion] = []
    message: str | None = None


class AddManualsRequest(BaseModel):
    manuals: list[DeviceSuggestion]
    # Optional overrides for the item created/linked for this device.
    item_name: str | None = None
    category_id: int | None = None


class AddManualsResponse(BaseModel):
    item_id: int
    document_ids: list[int] = []


class DownloadDriversRequest(BaseModel):
    drivers: list[DeviceSuggestion]


class DeviceUpdate(BaseModel):
    status: str | None = None  # discovered | dismissed
    label: str | None = None
