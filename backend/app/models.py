"""SQLite tables, as listed in ARCHITECTURE.md §3."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso_utc(dt: datetime) -> str:
    """SQLite drops tzinfo on read; all stored times are UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    hospital: Mapped[str] = mapped_column(String(300), default="")
    public_key_hex: Mapped[str] = mapped_column(String(64))
    token_hash: Mapped[str] = mapped_column(String(64), default="")  # sha256 of the bearer token; see app.auth
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Seal(Base):
    """Append-only ledger entry. entry_hash chains every row to the previous one."""

    __tablename__ = "seals"

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(String(128), index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    shape: Mapped[str] = mapped_column(String(64))  # JSON list, e.g. "[512, 512]"
    dtype: Mapped[str] = mapped_column(String(16))
    tile: Mapped[int] = mapped_column(Integer)
    leaves_json: Mapped[str] = mapped_column(Text)  # JSON [[y, x, sha256_hex], ...] sorted by (y, x)
    root_hex: Mapped[str] = mapped_column(String(64))
    sig_hex: Mapped[str] = mapped_column(String(128))
    prev_hash: Mapped[str] = mapped_column(String(64), unique=True)  # unique => the chain cannot fork
    entry_hash: Mapped[str] = mapped_column(String(64), unique=True)
    file_name: Mapped[str] = mapped_column(String(200))  # sealed file inside storage_dir


class Verification(Base):
    __tablename__ = "verifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    result: Mapped[str] = mapped_column(String(16))  # authentic / tampered / unsigned / forged
    changed_tiles_json: Mapped[str] = mapped_column(Text, default="[]")
    detective_prob: Mapped[float | None] = mapped_column(Float, nullable=True)
    shield_flag: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AIModel(Base):
    __tablename__ = "models"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[str] = mapped_column(String(100), default="")
    source: Mapped[str] = mapped_column(String(300), default="")
    intended_use: Mapped[str] = mapped_column(Text, default="")


class CrashTest(Base):
    __tablename__ = "crash_tests"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("models.id"))
    n_images: Mapped[int] = mapped_column(Integer)
    results_json: Mapped[str] = mapped_column(Text, default="{}")
    robustness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Passport(Base):
    """Issued once and frozen: report_json is a snapshot of every number at issue time."""

    __tablename__ = "passports"

    id: Mapped[int] = mapped_column(primary_key=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("models.id"))
    crash_test_id: Mapped[int] = mapped_column(ForeignKey("crash_tests.id"))
    verdict: Mapped[str] = mapped_column(String(32))
    conditions: Mapped[str] = mapped_column(Text, default="")  # JSON list of condition codes
    organisation: Mapped[str] = mapped_column(String(300), default="")
    report_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
