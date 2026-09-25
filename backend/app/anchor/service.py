"""Anchoring the ledger to the blockchain (docs/BLOCKCHAIN.md §3–4).

run_batch(): every not-yet-anchored ledger entry -> Merkle tree over their entry_hash (id order)
-> anchor(root, count) on the contract -> anchors + seal_anchors rows with each seal's proof.

check(): recompute the entry hash from the row's CURRENT content, climb the stored proof and
compare with the root read from the chain — not from our database. An insider who rewrites a
row (even re-signing it and recomputing the whole hash chain) cannot change the on-chain root.
"""
import json
import logging
import threading
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app import audit, db
from app.anchor.chain import ChainError, get_chain, tx_url
from app.config import settings
from app.models import Anchor, Seal, SealAnchor, iso_utc
from app.seal import ledger, merkle

log = logging.getLogger(__name__)
_run_lock = threading.Lock()  # the background loop and POST /anchors/run must not batch the same rows twice
# A seal older than the newest on-chain batch by more than this should have been in some batch.
# If it has no proof, someone deleted it (or its batch) from our database.
MISSING_PROOF_GRACE_S = 300


def unanchored(session: Session) -> list[Seal]:
    anchored_ids = select(SealAnchor.seal_id)
    return list(session.scalars(select(Seal).where(Seal.id.not_in(anchored_ids)).order_by(Seal.id)))


def run_batch(session: Session, actor: str = "scheduler", ip: str | None = None) -> Anchor | None:
    """Anchor every pending seal in one transaction. None if there was nothing to anchor.
    Raises ChainError when anchoring is off or the chain is unreachable (seals keep working)."""
    chain = get_chain()
    if chain is None:
        raise ChainError("anchoring is not configured (RPC_URL, CONTRACT_ADDRESS, ANCHOR_PRIVATE_KEY)")
    with _run_lock:
        # A row that is already broken is `forged` anyway; anchoring it would only bless the edit.
        rows = [r for r in unanchored(session) if ledger.row_is_intact(r)]
        if not rows:
            return None
        root, proofs = merkle.build([bytes.fromhex(r.entry_hash) for r in rows])
        tx = chain.anchor(root, len(rows))
        anchor = Anchor(batch_root_hex=root.hex(), count=len(rows), tx_hash=tx.tx_hash,
                        block_number=tx.block_number, chain_id=chain.chain_id,
                        onchain_index=tx.onchain_index, status="confirmed")
        session.add(anchor)
        session.flush()
        for row, proof in zip(rows, proofs):
            session.add(SealAnchor(seal_id=row.id, anchor_id=anchor.id, proof_json=json.dumps(proof)))
        audit.log(session, "anchor", actor, target=f"anchor:{anchor.id}", result=f"{len(rows)} seals, block {tx.block_number}", ip=ip)
        session.commit()
        log.info("anchored %d seals in block %d (tx %s)", len(rows), tx.block_number, tx.tx_hash)
        return anchor


LOCAL_DEV_CHAIN_IDS = {31337}  # Hardhat node: lives in memory, forgets everything when restarted


def resync_local_chain(session: Session) -> int:
    """After a restart of the local Hardhat node its contract is empty, but our tables still point
    at the old batches — every older seal would read "unavailable" forever. Forget those batches so
    the next run re-anchors the seals. Never on a real network: a real chain cannot be reset, and
    there the same symptom means something is badly wrong. -> number of batches forgotten."""
    chain = get_chain()
    if chain is None:
        return 0
    try:
        chain_id, total = chain.chain_id, chain.total()
    except ChainError:
        return 0
    if chain_id not in LOCAL_DEV_CHAIN_IDS:
        return 0
    stale = list(session.scalars(select(Anchor).where(Anchor.chain_id == chain_id, Anchor.onchain_index >= total)))
    if not stale:
        return 0
    ids = [a.id for a in stale]
    session.execute(delete(SealAnchor).where(SealAnchor.anchor_id.in_(ids)))
    session.execute(delete(Anchor).where(Anchor.id.in_(ids)))
    session.commit()
    log.warning("local chain was reset: forgot %d old batches, their seals will be re-anchored", len(ids))
    return len(ids)


def _iso(ts: int) -> str:
    return iso_utc(datetime.fromtimestamp(ts, timezone.utc))


def check(session: Session, row: Seal) -> dict | None:
    """The `blockchain` field of /verify. None when anchoring is off.
    status: anchored | pending | mismatch | unavailable."""
    chain = get_chain()
    if chain is None:
        return None
    link = session.scalar(select(SealAnchor).where(SealAnchor.seal_id == row.id))
    anchor = session.get(Anchor, link.anchor_id) if link else None
    if link is None:
        return _pending_or_missing(session, row)
    if anchor is None:  # the proof points at a batch that is no longer in our database
        return {"status": "mismatch", "detail": "anchor_record_missing"}

    info = {"block": anchor.block_number, "tx_hash": anchor.tx_hash, "tx_url": tx_url(anchor.tx_hash),
            "chain_id": anchor.chain_id}
    try:
        onchain = chain.get_anchor(anchor.onchain_index)
    except ChainError:
        return {"status": "unavailable", **info}
    leaf = bytes.fromhex(ledger.entry_hash(row.prev_hash, row))  # from the row as it is NOW
    ok = merkle.verify_proof(leaf, json.loads(link.proof_json), onchain.root)
    return {"status": "anchored" if ok else "mismatch", **info, "time": _iso(onchain.time)}


def _pending_or_missing(session: Session, row: Seal) -> dict:
    """Not in any batch yet. Normal for a fresh seal; a red flag for an old one."""
    chain = get_chain()
    try:
        # Ask the chain, not our table: deleting rows from `anchors` must not hide a batch.
        total = chain.total()
        if total == 0:
            return {"status": "pending"}
        newest = chain.get_anchor(total - 1)
    except ChainError:
        return {"status": "unavailable"}
    created = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=timezone.utc)
    if newest.time - created.timestamp() > MISSING_PROOF_GRACE_S:
        return {"status": "mismatch", "detail": "proof_missing", "time": _iso(newest.time)}
    return {"status": "pending"}


def list_anchors(session: Session) -> list[dict]:
    return [
        {"id": a.id, "root": a.batch_root_hex, "count": a.count, "tx_hash": a.tx_hash, "tx_url": tx_url(a.tx_hash),
         "block": a.block_number, "chain_id": a.chain_id, "onchain_index": a.onchain_index, "status": a.status,
         "created_at": iso_utc(a.created_at)}
        for a in session.scalars(select(Anchor).order_by(Anchor.id.desc()))
    ]


# --- background batching: every MEDSEAL_ANCHOR_INTERVAL seconds (default 10 min) ---

_stop = threading.Event()


def _loop() -> None:
    while not _stop.wait(settings.anchor_interval_s):
        try:
            with db.SessionLocal() as session:
                run_batch(session)
        except ChainError as e:
            log.warning("anchoring skipped, will retry next cycle: %s", e)
        except Exception:
            log.exception("anchoring pass failed")


def start() -> None:
    _stop.clear()
    threading.Thread(target=_loop, name="medseal-anchor", daemon=True).start()


def stop() -> None:
    _stop.set()
