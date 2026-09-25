"""Signed external anchors for the local append-only ledger."""
import json
import os
import threading

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Seal, iso_utc
from app.seal import keys
from app.seal.signing import anchor_message

_write_lock = threading.Lock()


def _read_entries() -> list[dict]:
    if not settings.anchor_path.exists():
        return []
    entries = []
    for line in settings.anchor_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            entries.append({"_malformed": True})
            continue
        entries.append(value if isinstance(value, dict) else {"_malformed": True})
    return entries


def append_anchor(row: Seal) -> None:
    """Append one fsync'ed root-signed line. Re-appending the same row is idempotent."""
    with _write_lock:
        settings.anchor_path.parent.mkdir(parents=True, exist_ok=True)
        existing = next((e for e in _read_entries() if e.get("n") == row.id), None)
        if existing is not None:
            if existing.get("head_hash") != row.entry_hash:
                raise ValueError(f"anchor mismatch for ledger row {row.id}")
            return
        at = iso_utc(row.created_at)
        entry = {
            "n": row.id,
            "head_hash": row.entry_hash,
            "at": at,
            "sig": keys.sign_root(anchor_message(n=row.id, head_hash=row.entry_hash, at=at)).hex(),
        }
        encoded = (json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
        fd = os.open(settings.anchor_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            with os.fdopen(fd, "ab") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            # The file descriptor is owned by the context manager; fsync above is the durability point.
            pass


def check_anchors(session: Session) -> tuple[int, list[int]]:
    """Return (number checked, mismatching/missing anchor row IDs)."""
    entries = _read_entries()
    if not entries:
        return 0, []
    rows = {row.id: row for row in session.scalars(select(Seal))}
    checked = 0
    mismatch: set[int] = set()
    seen: set[int] = set()
    for entry in entries:
        n = entry.get("n")
        if not isinstance(n, int):
            continue
        checked += 1
        if n in seen:
            mismatch.add(n)
        seen.add(n)
        row = rows.get(n)
        if row is None or entry.get("head_hash") != row.entry_hash:
            mismatch.add(n)
            continue
        try:
            signature = bytes.fromhex(str(entry.get("sig", "")))
        except ValueError:
            mismatch.add(n)
            continue
        if not keys.verify_root(signature, anchor_message(n=n, head_hash=row.entry_hash, at=str(entry.get("at", "")))):
            mismatch.add(n)

    # Once anchoring has started, a missing line is evidence of truncation. Rows before the
    # first anchor may be legacy rows and are intentionally not backfilled with invented trust.
    if seen:
        first, last = min(seen), max(max(seen), max(rows, default=0))
        for n in range(first, last + 1):
            if n not in seen:
                mismatch.add(n)
    return checked, sorted(mismatch)
