"""Content-based seal recovery when an image's ID was stripped or replaced (P1-03).

Different X-rays share ~0% identical tiles (each tile hash is bound to uid/y/x/shape/dtype),
so requiring >=50% identical tiles against a same-shape/dtype candidate cannot false-match on
"all chest X-rays look alike" — only a derivative of the SAME sealed image clears that bar.
dhash_hex only narrows which candidates get the expensive exact check; it is never trusted by
itself and is not part of the signed format (see imaging.dhash).
"""
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.imaging import dhash, hamming_distance, to_grayscale
from app.models import Seal
from app.seal import core, ledger

MATCH_THRESHOLD = 0.5
CANDIDATE_LIMIT = 5


def find_content_match(session: Session, px, shape_json: str, dtype: str) -> tuple[Seal, float] | None:
    """Best same-shape/dtype candidate by tile-overlap fraction among the top CANDIDATE_LIMIT
    closest by dHash, or None if nothing clears MATCH_THRESHOLD."""
    query_dhash = dhash(to_grayscale(px))
    candidates = session.scalars(
        select(Seal).where(Seal.shape == shape_json, Seal.dtype == dtype, Seal.dhash_hex != "")
    ).all()
    if not candidates:
        return None
    ranked = sorted(candidates, key=lambda row: hamming_distance(query_dhash, row.dhash_hex))[:CANDIDATE_LIMIT]

    best: tuple[Seal, float] | None = None
    for row in ranked:
        sealed = ledger.to_record(row)["leaves"]
        if not sealed:
            continue
        now = core.tile_hashes(px, row.uid, row.tile)
        fraction = sum(1 for k, v in sealed.items() if now.get(k) == v) / len(sealed)
        if best is None or fraction > best[1]:
            best = (row, fraction)

    if best and best[1] >= MATCH_THRESHOLD:
        return best
    return None


def backfill_dhash(session: Session, read_file: Callable[[Seal], bytes | None]) -> int:
    """Fills dhash_hex for rows sealed before this column existed. Only ever writes dhash_hex —
    never touches a hashed/signed field or entry_hash, so the ledger chain is unaffected.
    read_file(row) returns the stored file's bytes, or None if it's gone (skipped, not an error).
    Returns the number of rows updated."""
    from app.imaging import load_image  # local import: avoids a hard import-time cycle

    updated = 0
    for row in session.scalars(select(Seal).where(Seal.dhash_hex == "")):
        data = read_file(row)
        if data is None:
            continue
        try:
            image = load_image(data)
        except Exception:
            continue
        row.dhash_hex = dhash(to_grayscale(image.px))
        updated += 1
    if updated:
        session.commit()
    return updated
