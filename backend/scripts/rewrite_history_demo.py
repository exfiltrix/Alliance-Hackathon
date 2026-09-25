"""Threat T4, live: an insider with full access to our server rewrites the history of a seal.

    .venv/bin/python -m scripts.rewrite_history_demo 12 --image ~/Downloads/x_tampered.png
    .venv/bin/python -m scripts.rewrite_history_demo 12                 # only backdates the seal

The insider has what a hacker does not: the database AND the device keys in keys/. So the script
re-seals the doctored image into the existing ledger row with the real device key, then recomputes
the hash chain of every row after it. Every local check passes afterwards — signature, Merkle root,
hash chain. Only the root anchored on the blockchain still remembers the original, so /verify of
that image returns forged / blockchain_mismatch (with the chain it would be "authentic").

Demo only: it really rewrites the database it points at (MEDSEAL_DB_URL, default backend/medseal.db).
"""
import argparse
import json
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import db
from app.imaging import LoadedImage, load_image, meta_fields, meta_hash
from app.models import Seal, iso_utc
from app.seal import core, keys, ledger, signing


def _resign(row: Seal) -> None:
    """Re-sign `row` as it now stands, with the real device key — what a competent insider
    (database + device keys) would do so every *local* check, including the v2 header
    signature, passes. Only the externally anchored root still remembers the original."""
    key = keys.load_private_key(row.device_id)
    if (row.sig_version or 1) >= 2:
        row.sig_hex = signing.sign_v2(
            key,
            uid=row.uid,
            device_id=row.device_id,
            created_at=iso_utc(row.created_at),
            shape=row.shape,
            dtype=row.dtype,
            tile=row.tile,
            root_hex=row.root_hex,
            meta_hash_hex=row.meta_hash_hex,
            meta_version=row.meta_version or 1,
            patient_ref=row.patient_ref or "",
        ).hex()
    else:
        meta_hash = bytes.fromhex(row.meta_hash_hex) if row.meta_hash_hex else b""
        row.sig_hex = key.sign(bytes.fromhex(row.root_hex) + meta_hash + row.uid.encode()).hex()


def rewrite(session: Session, seal_id: int, image: LoadedImage | None = None) -> list[int]:
    """Rewrite one seal as an insider would, then repair the hash chain. -> ids of rows touched."""
    row = session.get(Seal, seal_id)
    if row is None:
        raise SystemExit(f"No seal {seal_id}")
    if image is None:
        row.created_at = row.created_at - timedelta(days=365)  # e.g. pretend the scan was done last year
        _resign(row)
    else:
        if image.uid != row.uid:
            raise SystemExit(f"Image uid {image.uid} is not seal {seal_id}'s uid {row.uid}")
        tile = core.tile_size_for(image.px.shape)
        leaves = core.tile_hashes(image.px, row.uid, tile)
        root = core.merkle_root(leaves)
        fields = meta_fields(image, version=row.meta_version or 1)
        mh = meta_hash(fields)
        row.shape, row.dtype, row.tile = json.dumps(list(image.px.shape)), str(image.px.dtype), tile
        row.leaves_json = ledger.leaves_to_json(leaves)
        row.root_hex = root.hex()
        row.meta_hash_hex, row.meta_json = mh.hex(), json.dumps(fields, sort_keys=True, separators=(",", ":"))
        _resign(row)

    touched, prev = [], ledger.GENESIS
    for r in session.scalars(select(Seal).order_by(Seal.id)):
        if r.id >= seal_id:
            r.prev_hash = prev
            r.entry_hash = ledger.entry_hash(prev, r)
            touched.append(r.id)
        prev = r.entry_hash
    session.commit()
    return touched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("seal_id", type=int)
    ap.add_argument("--image", help="doctored copy of the sealed image (keeps medseal_uid, e.g. from tamper_demo)")
    args = ap.parse_args()
    db.init_engine()
    image = load_image(Path(args.image).expanduser().read_bytes()) if args.image else None
    with db.SessionLocal() as session:
        touched = rewrite(session, args.seal_id, image)
        broken = ledger.broken_entries(session)
    print(f"rewrote seal {args.seal_id}, repaired hash chain of rows {touched[0]}..{touched[-1]}")
    print("local ledger check:", "clean — nothing looks wrong" if not broken else f"broken rows {broken}")
    print("now verify the image: only the blockchain can tell")


if __name__ == "__main__":
    main()
