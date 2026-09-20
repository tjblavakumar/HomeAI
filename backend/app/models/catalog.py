from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    icon: Mapped[str] = mapped_column(String(50), default="")
    is_custom: Mapped[bool] = mapped_column(default=False)

    items: Mapped[list["Item"]] = relationship(back_populates="category")


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    purchase_store: Mapped[str | None] = mapped_column(String(100), nullable=True)
    purchase_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    category: Mapped["Category"] = relationship(back_populates="items")
    documents: Mapped[list["Document"]] = relationship(back_populates="item")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    doc_type: Mapped[str] = mapped_column(String(30))  # manual|troubleshooting|driver|accessory
    title: Mapped[str] = mapped_column(String(300))
    source_url: Mapped[str] = mapped_column(String(1000))
    local_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    indexed_status: Mapped[str] = mapped_column(String(30), default="pending")
    selected_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    item: Mapped["Item"] = relationship(back_populates="documents")


class Device(Base):
    """A device discovered on the local network by the network scan."""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    mac: Mapped[str | None] = mapped_column(String(17), nullable=True, index=True)
    ip: Mapped[str] = mapped_column(String(45))
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # A best-effort human label derived from vendor/hostname, editable by the user.
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    device_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # printer|router|nas|...
    open_ports: Mapped[str | None] = mapped_column(String(200), nullable=True)  # csv of ints
    # Whether the user has acted on this device (dismissed / linked to an item).
    status: Mapped[str] = mapped_column(String(30), default="discovered")  # discovered|linked|dismissed
    # Optional link to a catalog Item created from this device.
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)

    first_seen: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    item: Mapped["Item | None"] = relationship()


class DriverDownload(Base):
    """A driver/software file downloaded to the server for a device."""

    __tablename__ = "driver_downloads"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    source_url: Mapped[str] = mapped_column(String(1000))
    local_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")  # pending|downloaded|failed
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    device: Mapped["Device"] = relationship()
