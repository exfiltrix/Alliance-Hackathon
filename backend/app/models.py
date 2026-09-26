"""SQLite tables, as listed in docs/ARCHITECTURE.md §3."""
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
    cert_sig_hex: Mapped[str] = mapped_column(String(128), default="")  # root-signed device certificate
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    meta_hash_hex: Mapped[str] = mapped_column(String(64), default="")  # sha256 of imaging.meta_fields; see P0-5
    meta_json: Mapped[str] = mapped_column(Text, default="{}")  # the fields themselves, for changed_meta on verify
    meta_version: Mapped[int] = mapped_column(Integer, default=1)  # 1 = legacy META_TAGS, 2 = display-affecting v2
    sig_version: Mapped[int] = mapped_column(Integer, default=1)  # 1 = legacy signature, 2 = canonical header
    patient_ref: Mapped[str] = mapped_column(String(64), default="")  # HMAC PatientID, never the ID itself
    phi_warning: Mapped[str] = mapped_column(String(64), default="")  # non-cryptographic upload warning
    dhash_hex: Mapped[str] = mapped_column(String(16), default="")  # imaging.dhash; content-based recovery, P1-03
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
    signature_hex: Mapped[str] = mapped_column(String(128), default="")  # root signature over the frozen report
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ClientAccount(Base):
    """One organisation-level login for the client cabinet (docs/API.md "Client cabinet").

    Scoped to exactly one hospital string (the same free-text value stored on Device.hospital and
    Passport.organisation): every client-cabinet endpoint filters by it, so one organisation can
    never see another's devices, stats or passports. Created by an admin only (POST /clients),
    same pattern as a device token: the bearer token is returned once and only its sha256 is kept.
    """

    __tablename__ = "client_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    hospital: Mapped[str] = mapped_column(String(300), unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PublicCheck(Base):
    """Random, unguessable link token for the patient-facing QR check of one seal.
    Kept outside the seals table so the ledger record (and its hash chain) is untouched."""

    __tablename__ = "public_checks"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    seal_id: Mapped[int] = mapped_column(ForeignKey("seals.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InboxItem(Base):
    """An image that reached the doctor and was checked automatically (upload or watched folder)."""

    __tablename__ = "inbox_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_name: Mapped[str] = mapped_column(String(300))
    source: Mapped[str] = mapped_column(String(16))  # upload | folder
    # Lifecycle of the automatic pipeline, not of the image: new -> processing -> done | failed.
    # The doctor's triage (severity/status) is a separate axis and stays as it was. While a row is
    # still being verified, status/severity hold the PENDING placeholder — the row is committed
    # before the slow work so a crash shows up as stuck instead of vanishing (see automation.inbox).
    state: Mapped[str] = mapped_column(String(12), default="done")
    status: Mapped[str] = mapped_column(String(16), default="processing")  # authentic/tampered/unsigned/forged/error
    severity: Mapped[str] = mapped_column(String(16), default="processing", index=True)  # danger/warning/ok
    reasons_json: Mapped[str] = mapped_column(Text, default="[]")  # why it needs attention (codes)
    result_json: Mapped[str] = mapped_column(Text, default="{}")  # full /verify response, incl. preview
    # The few listing fields, so GET /inbox never has to parse result_json (which carries a
    # ~100 KB base64 preview per row) just to read four scalars.
    summary_json: Mapped[str] = mapped_column(Text, default="{}")
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Anchor(Base):
    """One batch of ledger entries whose Merkle root was written to the MedSealAnchor contract
    (docs/BLOCKCHAIN.md). Only confirmed batches are stored; a failed send leaves no row."""

    __tablename__ = "anchors"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_root_hex: Mapped[str] = mapped_column(String(64), unique=True)
    count: Mapped[int] = mapped_column(Integer)
    tx_hash: Mapped[str] = mapped_column(String(66))
    block_number: Mapped[int] = mapped_column(Integer)
    chain_id: Mapped[int] = mapped_column(Integer)
    onchain_index: Mapped[int] = mapped_column(Integer)  # id in the contract's anchors[] array
    status: Mapped[str] = mapped_column(String(16), default="confirmed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SealAnchor(Base):
    """Which batch a seal went into, plus its Merkle proof up to the batch root.
    Kept outside the seals table: the ledger stays append-only and its hash chain untouched."""

    __tablename__ = "seal_anchors"

    id: Mapped[int] = mapped_column(primary_key=True)
    seal_id: Mapped[int] = mapped_column(ForeignKey("seals.id"), unique=True)
    anchor_id: Mapped[int] = mapped_column(ForeignKey("anchors.id"), index=True)
    proof_json: Mapped[str] = mapped_column(Text)  # [[side, sibling_hex], ...], see app.seal.merkle


class AuditEvent(Base):
    """Who did what, when, with what result (docs/SECURITY.md "Audit log"). Append-only:
    the API only ever inserts and lists these rows — there is no update or delete endpoint."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    # seal | verify | device_create | device_revoke | anchor | auth_failed
    action: Mapped[str] = mapped_column(String(32), index=True)
    actor: Mapped[str] = mapped_column(String(200))  # admin | device:<name> | anonymous | inbox | scheduler
    target: Mapped[str] = mapped_column(String(200), default="")  # e.g. seal:12, device:3, anchor:5
    result: Mapped[str] = mapped_column(String(64), default="")  # e.g. sealed, authentic, forged, rejected:409
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
