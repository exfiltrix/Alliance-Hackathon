"""Tile-level seal: SHA-256 per tile -> Merkle root -> Ed25519 signature.

Ported from reference/medseal_poc.py. The hash input format is part of every stored
seal: changing it invalidates the ledger, so update tests and re-seal demo data
if you ever touch tile_hashes() or merkle_root().
"""
import hashlib

import numpy as np
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

Leaves = dict[tuple[int, int], bytes]


def tile_size_for(shape: tuple[int, ...]) -> int:
    """32x32 tiles for images >= 256 px, 16x16 for smaller ones."""
    return 32 if min(shape[:2]) >= 256 else 16


def tile_hashes(px: np.ndarray, uid: str, tile: int) -> Leaves:
    """SHA-256 fingerprint of every tile, bound to image ID and tile position.

    px may be 2-D grayscale (h, w) or 3-D (h, w, channels) — RGB/RGBA PNGs are hashed with
    every channel, not just luminance (P0-3), so a color-only edit is still caught.
    """
    h, w = px.shape[:2]
    out = {}
    for y in range(0, h, tile):
        for x in range(0, w, tile):
            block = np.ascontiguousarray(px[y:y + tile, x:x + tile])
            m = hashlib.sha256()
            m.update(f"{uid}|{y}|{x}|{block.shape}|{block.dtype}".encode())
            m.update(block.tobytes())
            out[(y, x)] = m.digest()
    return out


def merkle_root(leaves: Leaves) -> bytes:
    level = [leaves[k] for k in sorted(leaves)]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
    return level[0]


def seal(px: np.ndarray, uid: str, key: Ed25519PrivateKey, tile: int | None = None) -> dict:
    """Gateway side: fingerprint tiles, build Merkle root, sign it."""
    tile = tile or tile_size_for(px.shape)
    leaves = tile_hashes(px, uid, tile)
    root = merkle_root(leaves)
    return {"uid": uid, "tile": tile, "leaves": leaves, "root": root, "sig": key.sign(root + uid.encode())}


def check_record(record: dict, pub: Ed25519PublicKey) -> bool:
    """The ledger record is authentic: valid signature and the stored leaves produce the stored root."""
    try:
        pub.verify(record["sig"], record["root"] + record["uid"].encode())
    except InvalidSignature:
        return False
    return merkle_root(record["leaves"]) == record["root"]


def changed_tiles(px: np.ndarray, record: dict) -> list[tuple[int, int]]:
    """Tiles whose hash differs from the sealed one.

    Unlike the PoC this also compares tiles present only in the record, so a
    cropped image cannot hide removed tiles.
    """
    now = tile_hashes(px, record["uid"], record["tile"])
    sealed = record["leaves"]
    return sorted(k for k in now.keys() | sealed.keys() if now.get(k) != sealed.get(k))


def verify(px: np.ndarray, record: dict, pub: Ed25519PublicKey) -> tuple[bool, list[tuple[int, int]]]:
    """Viewer/AI side: check the ledger record is authentic, then compare tiles.

    Callers must check record_ok first: changed tiles are meaningless for a forged record.
    """
    return check_record(record, pub), changed_tiles(px, record)
