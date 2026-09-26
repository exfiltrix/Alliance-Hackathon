"""Append-only seal ledger with a hash chain: entry_hash = sha256(prev_hash + record)."""
import hashlib
import json
import threading

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Seal, iso_utc, utcnow

GENESIS = "0" * 64
_append_lock = threading.Lock()


def record_bytes(row: Seal) -> bytes:
    """Canonical record bytes. v1 rows retain their historical byte-for-byte format."""
    values = {
        "uid": row.uid,
        "device_id": row.device_id,
        "created_at": iso_utc(row.created_at),
        "shape": row.shape,
        "dtype": row.dtype,
        "tile": row.tile,
        "leaves": row.leaves_json,
        "root": row.root_hex,
        "meta_hash": row.meta_hash_hex,
        "meta": row.meta_json,
        "sig": row.sig_hex,
    }
    if (row.sig_version or 1) < 2 and (row.meta_version or 1) < 2 and not row.meta_hash_hex:
        # Rows sealed before P0-5 (3e3cbf7) were hashed without the meta fields, which the column
        # migration later filled with ""/"{}": hashing them in would flag a genuine row as
        # ledger_entry_modified. Every row sealed since has a non-empty meta_hash, and blanking it
        # changes these bytes anyway, so this cannot be used to rewrite a newer row.
        del values["meta_hash"], values["meta"]
    if (row.sig_version or 1) >= 2 or (row.meta_version or 1) >= 2:
        values.update(
            {
                "meta_version": row.meta_version or 1,
                "sig_version": row.sig_version or 1,
                "patient_ref": row.patient_ref or "",
            }
        )
    ensure_ascii = not ((row.sig_version or 1) >= 2 or (row.meta_version or 1) >= 2)
    return json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=ensure_ascii).encode()


def entry_hash(prev_hash: str, row: Seal) -> str:
    return hashlib.sha256(prev_hash.encode() + record_bytes(row)).hexdigest()


def _set_link(session: Session, row: Seal) -> None:
    head = session.scalar(select(Seal).order_by(Seal.id.desc()).limit(1))
    row.created_at = row.created_at or utcnow()
    row.prev_hash = head.entry_hash if head else GENESIS
    row.entry_hash = entry_hash(row.prev_hash, row)
    session.add(row)
    session.flush()


def append(session: Session, row: Seal) -> Seal:
    """Link and insert under a process-local lock, retrying one lost-head race."""
    with _append_lock:
        for attempt in range(2):
            try:
                _set_link(session, row)
                return row
            except IntegrityError:
                session.rollback()
                if attempt == 1:
                    raise
                # A concurrent process committed the previous head between our read and insert.
                # The same row is transient again after rollback; recompute against the new head.
                session.add(row)
    raise RuntimeError("unreachable append state")


def find_by_uid(session: Session, uid: str) -> Seal | None:
    return session.scalar(select(Seal).where(Seal.uid == uid).order_by(Seal.id).limit(1))


def row_is_intact(row: Seal) -> bool:
    return entry_hash(row.prev_hash, row) == row.entry_hash


def broken_entries(session: Session) -> list[int]:
    """IDs of rows whose content or link to the previous row were rewritten."""
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
        "meta_hash": bytes.fromhex(row.meta_hash_hex) if row.meta_hash_hex else b"",
        "sig": bytes.fromhex(row.sig_hex),
    }
