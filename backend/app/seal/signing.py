"""Versioned signatures kept separate from the frozen v1 tile/Merkle format."""
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

V2_PREFIX = b"MEDSEAL-SEAL-v2\n"
ANCHOR_PREFIX = b"MEDSEAL-ANCHOR-v1\n"
PASSPORT_PREFIX = b"MEDSEAL-PASSPORT-v1\n"


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _shape_value(shape: str | list[int] | tuple[int, ...]) -> list[int] | str:
    if isinstance(shape, str):
        return json.loads(shape)
    return list(shape)


def seal_v2_message(
    *,
    uid: str,
    device_id: int,
    created_at: str,
    shape: str | list[int] | tuple[int, ...],
    dtype: str,
    tile: int,
    root_hex: str,
    meta_hash_hex: str,
    meta_version: int,
    patient_ref: str,
) -> bytes:
    header = {
        "uid": uid,
        "device_id": device_id,
        "created_at": created_at,
        "shape": _shape_value(shape),
        "dtype": dtype,
        "tile": tile,
        "root_hex": root_hex,
        "meta_hash_hex": meta_hash_hex,
        "meta_version": meta_version,
        "patient_ref": patient_ref,
    }
    return V2_PREFIX + canonical_json(header)


def sign_v2(key: Ed25519PrivateKey, **header) -> bytes:
    return key.sign(seal_v2_message(**header))


def check_v2(
    signature: bytes,
    pub: Ed25519PublicKey,
    *,
    uid: str,
    device_id: int,
    created_at: str,
    shape: str | list[int] | tuple[int, ...],
    dtype: str,
    tile: int,
    root_hex: str,
    meta_hash_hex: str,
    meta_version: int,
    patient_ref: str,
) -> bool:
    message = seal_v2_message(
        uid=uid,
        device_id=device_id,
        created_at=created_at,
        shape=shape,
        dtype=dtype,
        tile=tile,
        root_hex=root_hex,
        meta_hash_hex=meta_hash_hex,
        meta_version=meta_version,
        patient_ref=patient_ref,
    )
    try:
        pub.verify(signature, message)
    except InvalidSignature:
        return False
    return True


def anchor_message(*, n: int, head_hash: str, at: str) -> bytes:
    return ANCHOR_PREFIX + canonical_json({"n": n, "head_hash": head_hash, "at": at})


def passport_message(*, report: dict, passport_id: int, created_at: str, organisation: str) -> bytes:
    return PASSPORT_PREFIX + canonical_json(
        {"report": report, "id": passport_id, "created_at": created_at, "organisation": organisation}
    )
