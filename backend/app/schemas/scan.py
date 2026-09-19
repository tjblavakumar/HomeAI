from pydantic import BaseModel


class ScanResult(BaseModel):
    raw_text: str
    barcodes: list[str]
    guessed_name: str | None
