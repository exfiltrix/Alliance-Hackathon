"""Gateway: seal an uploaded image and record it in the ledger."""
import json
import time
import uuid

from sqlalchemy.orm import Session

from app.config import settings
from app.imaging import (
    LoadedImage,
    assign_uid,
    dhash,
    meta_fields,
    meta_hash,
    patient_reference,
    sealed_file_bytes,
    to_grayscale,
)
from app.models import Device, Seal, utcnow
from app.seal import anchors, core, keys, ledger, recovery, signing


class SealError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def seal_upload(session: Session, image: LoadedImage, device_id: int) -> tuple[Seal, float]:
    """Returns (ledger row, sealing time in ms). Re-sealing identical pixels returns the existing row."""
    device = session.get(Device, device_id)
    if device is None:
        raise SealError(404, "Device not found")
    if device.revoked:
        raise SealError(409, "Device is revoked")

    existing = ledger.find_by_uid(session, image.uid) if image.uid else None
    if existing is not None:
        if core.changed_tiles(image.px, ledger.to_record(existing)):
            raise SealError(409, f"Image {image.uid} is already sealed with different pixels (seal {existing.id})")
        return existing, 0.0

    # Search whenever the supplied ID is absent or unknown. An attacker must not bypass the
    # content guard by attaching a fresh random UID to an edited derivative.
    if image.uid is None or existing is None:
        shape_json = json.dumps(list(image.px.shape))
        match = recovery.find_content_match(session, image.px, shape_json, str(image.px.dtype))
        if match:
            candidate, fraction = match
            if fraction >= 1.0:
                return candidate, 0.0
            raise SealError(409, f"Image is derived from sealed image #{candidate.id}")

    uid = assign_uid(image)
    fields = meta_fields(image, version=2)
    mh = meta_hash(fields)
    created_at = utcnow()
    patient_ref = patient_reference(image.patient_id)
    key = keys.load_private_key(device.id)

    t0 = time.perf_counter()
    tile = core.tile_size_for(image.px.shape)
    leaves = core.tile_hashes(image.px, uid, tile)
    root = core.merkle_root(leaves)
    signature = signing.sign_v2(
        key,
        uid=uid,
        device_id=device.id,
        created_at=created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        shape=json.dumps(list(image.px.shape)),
        dtype=str(image.px.dtype),
        tile=tile,
        root_hex=root.hex(),
        meta_hash_hex=mh.hex(),
        meta_version=2,
        patient_ref=patient_ref,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    record = {"uid": uid, "tile": tile, "leaves": leaves, "root": root, "sig": signature}

    content, ext = sealed_file_bytes(image)
    file_name = f"{uuid.uuid4().hex}.{ext}"
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    (settings.storage_dir / file_name).write_bytes(content)

    row = Seal(
        uid=uid,
        device_id=device.id,
        created_at=created_at,
        shape=json.dumps(list(image.px.shape)),
        dtype=str(image.px.dtype),
        tile=record["tile"],
        leaves_json=ledger.leaves_to_json(record["leaves"]),
        root_hex=record["root"].hex(),
        meta_hash_hex=mh.hex(),
        meta_json=json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        meta_version=2,
        sig_version=2,
        patient_ref=patient_ref,
        phi_warning="burned_in_annotation" if image.burned_in_annotation else "",
        dhash_hex=dhash(to_grayscale(image.px)),
        sig_hex=record["sig"].hex(),
        file_name=file_name,
    )
    ledger.append(session, row)
    session.commit()
    anchors.append_anchor(row)
    return row, elapsed_ms
