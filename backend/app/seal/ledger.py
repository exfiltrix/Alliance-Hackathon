"""Append-only seal ledger with a hash chain: entry_hash = sha256(prev_hash + record)."""
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Seal, iso_utc, utcnow

GENESIS = "0" * 64


def record_bytes(row: Seal) -> bytes:
    """Canonical serialisation of the signed content of a ledger row."""
    return json.dumps(
        {
            "uid": row.uid,
            "device_id": row.device_id,
            "created_at": iso_utc(row.created_at),
            "shape": row.shape,
            "dtype": row.dtype,
            "tile": row.tile,
            "leaves": row.leaves_json,
            "root": row.root_hex,
            "sig": row.sig_hex,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def entry_hash(prev_hash: str, row: Seal) -> str:
    return hashlib.sha256(prev_hash.encode() + record_bytes(row)).hexdigest()


def append(session: Session, row: Seal) -> Seal:
    """Link the row to the current chain head and insert it. Caller commits."""
    head = session.scalar(select(Seal).order_by(Seal.id.desc()).limit(1))
    row.created_at = row.created_at or utcnow()  # part of the hashed record, so set before hashing
    row.prev_hash = head.entry_hash if head else GENESIS
    row.entry_hash = entry_hash(row.prev_hash, row)
    session.add(row)
    session.flush()
    return row


def find_by_uid(session: Session, uid: str) -> Seal | None:
    return session.scalar(select(Seal).where(Seal.uid == uid).order_by(Seal.id).limit(1))


def row_is_intact(row: Seal) -> bool:
    return entry_hash(row.prev_hash, row) == row.entry_hash


def broken_entries(session: Session) -> list[int]:
    """IDs of rows whose content or link to the previous row was rewritten."""
    broken, prev = [], GENESIS
    for row in session.scalars(select(Seal).order_by(Seal.id)):
        if row.prev_hash != prev or not row_is_intact(row):
            broken.append(row.id)
        prev = row.entry_hash
    return broken


def leaves_to_json(leaves: dict[tuple[int, int], bytes]) -> str:
    return json.dumps([[y, x, h.hex()] for (y, x), h in sorted(leaves.items())], separators=(",", ":"))


def to_record(row: Seal) -> dict:
    """Ledger row -> the record dict used by app.seal.core."""
    return {
        "uid": row.uid,
        "tile": row.tile,
        "leaves": {(y, x): bytes.fromhex(h) for y, x, h in json.loads(row.leaves_json)},
        "root": bytes.fromhex(row.root_hex),
        "sig": bytes.fromhex(row.sig_hex),
    }
