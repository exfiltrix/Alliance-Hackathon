"""Blockchain anchoring (docs/BLOCKCHAIN.md) and threat T4: an insider rewrites history."""
import hashlib
import pytest
from sqlalchemy import delete, update

from app import db
from app.anchor import service as anchoring
from app.imaging import load_image
from app.models import Anchor, Seal, SealAnchor
from app.seal import ledger, merkle
from scripts.rewrite_history_demo import rewrite
from tests.conftest import admin_headers, png_pixels, replace_png_pixels, xray_png
from tests.test_api import seal, verify


# --- Merkle tree with domain separation ---

@pytest.mark.parametrize("n", [1, 2, 3, 5, 8, 13])
def test_proof_for_every_leaf_verifies(n):
    items = [hashlib.sha256(bytes([i])).digest() for i in range(n)]
    root, proofs = merkle.build(items)
    for item, proof in zip(items, proofs):
        assert merkle.verify_proof(item, proof, root)


def test_changed_leaf_fails():
    items = [hashlib.sha256(bytes([i])).digest() for i in range(5)]
    root, proofs = merkle.build(items)
    assert not merkle.verify_proof(b"\x01" + items[2][1:], proofs[2], root)
    assert not merkle.verify_proof(items[2], proofs[3], root)  # someone else's proof


def test_domain_separation():
    """An inner node cannot be passed off as a leaf (second-preimage trick)."""
    a, b = hashlib.sha256(b"a").digest(), hashlib.sha256(b"b").digest()
    root, _ = merkle.build([a, b])
    assert root == merkle.node_hash(merkle.leaf_hash(a), merkle.leaf_hash(b))
    inner = merkle.leaf_hash(a) + merkle.leaf_hash(b)
    assert merkle.build([inner])[0] != root


# --- anchoring service and /verify ---

def anchor_now(client):
    r = client.post("/api/anchors/run", headers=admin_headers())
    assert r.status_code == 200, r.text
    return r.json()


def test_blockchain_is_null_when_anchoring_is_off(client, device):
    _, sealed = seal(client, device, xray_png(seed=1))
    assert verify(client, sealed)["blockchain"] is None
    assert client.post("/api/anchors/run", headers=admin_headers()).status_code == 503


def test_run_requires_admin(client, chain):
    assert client.post("/api/anchors/run").status_code == 401


def test_seal_is_pending_then_anchored(client, device, chain):
    _, sealed = seal(client, device, xray_png(seed=2))
    result = verify(client, sealed)
    assert result["status"] == "authentic" and result["blockchain"] == {"status": "pending"}
    assert result["sealed_at"].endswith("Z")

    body = anchor_now(client)
    assert body["anchored"] == 1 and len(chain.anchors) == 1
    assert anchor_now(client) == {"anchored": 0, "anchor": None}  # nothing new, no transaction

    result = verify(client, sealed)
    assert result["status"] == "authentic"
    assert result["blockchain"]["status"] == "anchored"
    assert result["blockchain"]["block"] == body["anchor"]["block"]

    listed = client.get("/api/anchors").json()
    assert listed["pending"] == 0 and listed["anchors"][0]["count"] == 1


def test_one_batch_covers_many_seals(client, device, chain):
    sealed = [seal(client, device, xray_png(seed=10 + i))[1] for i in range(5)]
    assert anchor_now(client)["anchored"] == 5
    assert len(chain.anchors) == 1
    assert all(verify(client, s)["blockchain"]["status"] == "anchored" for s in sealed)


def test_chain_down_seals_keep_working(client, device, chain):
    _, sealed = seal(client, device, xray_png(seed=3))
    anchor_now(client)
    chain.online = False
    result = verify(client, sealed)
    assert result["status"] == "authentic" and result["blockchain"]["status"] == "unavailable"

    _, fresh = seal(client, device, xray_png(seed=4))  # sealing does not need the chain
    assert client.post("/api/anchors/run", headers=admin_headers()).status_code == 503
    chain.online = True
    assert anchor_now(client)["anchored"] == 1  # retried on the next run
    assert verify(client, fresh)["blockchain"]["status"] == "anchored"


def test_t4_insider_rewrites_history(client, device, chain):
    """The insider re-signs a doctored image with the real device key and repairs the hash chain.
    Every local check passes; only the anchored root catches it."""
    _, sealed = seal(client, device, xray_png(seed=5))
    _, later = seal(client, device, xray_png(seed=6))  # a row after it: the insider relinks it too
    anchor_now(client)

    px = png_pixels(sealed).copy()
    px[200:230, 150:180] = 255  # fake nodule
    doctored = replace_png_pixels(sealed, px)
    assert verify(client, doctored)["status"] == "tampered"

    with db.SessionLocal() as session:
        seal_id = ledger.find_by_uid(session, load_image(sealed).uid).id
        rewrite(session, seal_id, load_image(doctored))
        assert ledger.broken_entries(session) == []  # the local ledger looks perfectly clean

    result = verify(client, doctored)
    assert result["status"] == "forged" and result["reason"] == "blockchain_mismatch"
    assert result["blockchain"]["status"] == "mismatch"
    # The leaf is entry_hash, which covers prev_hash: every row relinked after the rewrite
    # no longer matches the chain either — the whole rewritten tail of history shows up.
    assert verify(client, later)["blockchain"]["status"] == "mismatch"


def test_t4_backdated_seal(client, device, chain):
    _, sealed = seal(client, device, xray_png(seed=7))
    anchor_now(client)
    with db.SessionLocal() as session:
        rewrite(session, ledger.find_by_uid(session, load_image(sealed).uid).id)
    result = verify(client, sealed)
    assert (result["status"], result["reason"]) == ("forged", "blockchain_mismatch")


def test_plain_row_edit_is_both_forged_and_mismatch(client, device, chain):
    """DEMO step 3b: editing a row directly in SQLite (no chain repair, no re-sign).

    `leaves_json` is part of the hash-chained record but not the v2 header signature (CRY-02
    signs uid/device_id/created_at/shape/dtype/tile/root_hex/meta_hash_hex, not the individual
    leaf hashes) — so editing it exercises the ledger/chain check specifically, distinct from
    the bad_signature path a v2-signed field like dtype would now hit first."""
    _, sealed = seal(client, device, xray_png(seed=8))
    anchor_now(client)
    with db.SessionLocal() as session:
        session.execute(update(Seal).values(leaves_json="[[0,0,\"00\"]]"))
        session.commit()
    result = verify(client, sealed)
    assert result["status"] == "forged" and result["reason"] == "ledger_entry_modified"
    assert result["blockchain"]["status"] == "mismatch"


def test_deleting_the_proof_does_not_hide_the_seal(client, device, chain):
    """The insider deletes the proof and the batch from our DB, hoping for a harmless 'pending'.
    The chain still says a batch was mined after this seal, so the missing proof is a red flag."""
    _, sealed = seal(client, device, xray_png(seed=9))
    anchor_now(client)
    chain.anchors[0].time += 3600  # the batch was mined an hour after the seal
    with db.SessionLocal() as session:
        session.execute(delete(SealAnchor))
        session.execute(delete(Anchor))
        session.commit()
    result = verify(client, sealed)
    assert result["blockchain"]["status"] == "mismatch" and result["blockchain"]["detail"] == "proof_missing"
    assert result["status"] == "forged" and result["reason"] == "blockchain_mismatch"


def test_seal_after_last_batch_is_just_pending(client, device, chain):
    seal(client, device, xray_png(seed=12))
    anchor_now(client)
    _, fresh = seal(client, device, xray_png(seed=13))
    result = verify(client, fresh)
    assert result["status"] == "authentic" and result["blockchain"] == {"status": "pending"}


def test_broken_row_is_not_anchored(client, device, chain):
    _, sealed = seal(client, device, xray_png(seed=11))
    with db.SessionLocal() as session:
        session.execute(update(Seal).values(tile=16))
        session.commit()
    assert anchor_now(client)["anchored"] == 0
    assert chain.anchors == []


def test_local_chain_restart_is_healed(client, device, chain):
    """Hardhat node restarted: its contract is empty again. Old proofs are dropped and re-anchored."""
    _, sealed = seal(client, device, xray_png(seed=14))
    anchor_now(client)
    chain.anchors.clear()  # node restart
    assert verify(client, sealed)["blockchain"]["status"] == "unavailable"
    with db.SessionLocal() as session:
        assert anchoring.resync_local_chain(session) == 1
    assert verify(client, sealed)["blockchain"] == {"status": "pending"}
    assert anchor_now(client)["anchored"] == 1
    assert verify(client, sealed)["blockchain"]["status"] == "anchored"


def test_real_chain_is_never_resynced(client, device, chain):
    chain.chain_id = 11155111  # Sepolia
    _, sealed = seal(client, device, xray_png(seed=15))
    anchor_now(client)
    chain.anchors.clear()
    with db.SessionLocal() as session:
        assert anchoring.resync_local_chain(session) == 0
    assert verify(client, sealed)["blockchain"]["status"] == "unavailable"
