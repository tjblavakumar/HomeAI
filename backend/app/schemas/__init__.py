from app.schemas.category import CategoryCreate, CategoryOut
from app.schemas.chat import ChatRequest, ChatResponse, Citation, DocumentSuggestion
from app.schemas.document import DocumentOut, DocumentSelectItem, DocumentSelectRequest
from app.schemas.item import ItemCreate, ItemFromUrl, ItemOut
from app.schemas.network import (
    AddManualsRequest,
    AddManualsResponse,
    DeviceOut,
    DeviceSuggestion,
    DeviceUpdate,
    DeviceWithMatch,
    DownloadDriversRequest,
    DriverDownloadOut,
    ItemMatch,
    ScanRequest,
    SuggestResponse,
)
from app.schemas.scan import ScanResult

__all__ = [
    "CategoryOut",
    "CategoryCreate",
    "ItemOut",
    "ItemCreate",
    "ItemFromUrl",
    "ChatRequest",
    "ChatResponse",
    "DocumentSuggestion",
    "Citation",
    "DocumentOut",
    "DocumentSelectItem",
    "DocumentSelectRequest",
    "ScanResult",
    # network
    "ScanRequest",
    "ItemMatch",
    "DeviceOut",
    "DeviceWithMatch",
    "DriverDownloadOut",
    "DeviceSuggestion",
    "SuggestResponse",
    "AddManualsRequest",
    "AddManualsResponse",
    "DownloadDriversRequest",
    "DeviceUpdate",
]
