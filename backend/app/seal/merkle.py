"""Merkle tree with domain separation and inclusion proofs (docs/BLOCKCHAIN.md §2).

leaf = sha256(0x00 || data), node = sha256(0x01 || left || right): a leaf can never be
passed off as an inner node (second-preimage trick). Odd level: the last node is duplicated.

Used for anchoring batches of ledger entries. The per-image tile tree (app.seal.core) keeps
its original v1 format, which is frozen by test_hash_format_is_frozen.
"""
import hashlib

LEAF, NODE = b"\x00", b"\x01"
# Proof step: which side the SIBLING is on, and its hash.
LEFT, RIGHT = "L", "R"


def leaf_hash(data: bytes) -> bytes:
    return hashlib.sha256(LEAF + data).digest()


def node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(NODE + left + right).digest()


def build(items: list[bytes]) -> tuple[bytes, list[list[list[str]]]]:
    """Root of the tree over items (in the given order) and a proof for every item.

    A proof is a list of [side, sibling_hex] from the leaf up to the root.
    """
    if not items:
        raise ValueError("empty tree")
    level = [leaf_hash(d) for d in items]
    positions = list(range(len(items)))  # index of each item's ancestor on the current level
    proofs: list[list[list[str]]] = [[] for _ in items]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        for i, pos in enumerate(positions):
            if pos % 2:
                proofs[i].append([LEFT, level[pos - 1].hex()])
            else:
                proofs[i].append([RIGHT, level[pos + 1].hex()])
            positions[i] = pos // 2
        level = [node_hash(level[j], level[j + 1]) for j in range(0, len(level), 2)]
    return level[0], proofs


def root_from_proof(data: bytes, proof: list[list[str]]) -> bytes:
    h = leaf_hash(data)
    for side, sibling_hex in proof:
        sibling = bytes.fromhex(sibling_hex)
        if side == LEFT:
            h = node_hash(sibling, h)
        elif side == RIGHT:
            h = node_hash(h, sibling)
        else:
            raise ValueError(f"bad proof side {side!r}")
    return h


def verify_proof(data: bytes, proof: list[list[str]], root: bytes) -> bool:
    try:
        return root_from_proof(data, proof) == root
    except ValueError:
        return False
