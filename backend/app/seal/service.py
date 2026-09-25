"""Gateway: seal an uploaded image and record it in the ledger."""
import json
import time
import uuid

from sqlalchemy.orm import Session

from app.config import settings
from app.imaging import LoadedImage, assign_uid, dhash, meta_fields, meta_hash, sealed_file_bytes, to_grayscale
from app.models import Device, Seal
from app.seal import core, keys, ledger, recovery


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

    if image.uid and (existing := ledger.find_by_uid(session, image.uid)):
        if core.changed_tiles(image.px, ledger.to_record(existing)):
            raise SealError(409, f"Image {image.uid} is already sealed with different pixels (seal {existing.id})")
        return existing, 0.0

    # P1-03 seal-side guard: without this, "strip the ID, edit, seal as new" would mint a fresh,
    # perfectly valid seal for a forged derivative of an already-sealed image.
    if image.uid is None:
        shape_json = json.dumps(list(image.px.shape))
        match = recovery.find_content_match(session, image.px, shape_json, str(image.px.dtype))
        if match:
            candidate, fraction = match
            if fraction >= 1.0:
                return candidate, 0.0  # untouched, just missing its chunk — same as re-sealing today
            raise SealError(409, f"Image is derived from sealed image #{candidate.id}")

    uid = assign_uid(image)
    fields = meta_fields(image)
    mh = meta_hash(fields)
    t0 = time.perf_counter()
    record = core.seal(image.px, uid, keys.load_private_key(device.id), meta_hash=mh)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    content, ext = sealed_file_bytes(image)
    file_name = f"{uuid.uuid4().hex}.{ext}"
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    (settings.storage_dir / file_name).write_bytes(content)

    row = Seal(
        uid=uid,
        device_id=device.id,
        shape=json.dumps(list(image.px.shape)),
        dtype=str(image.px.dtype),
        tile=record["tile"],
        leaves_json=ledger.leaves_to_json(record["leaves"]),
        root_hex=record["root"].hex(),
        meta_hash_hex=mh.hex(),
        meta_json=json.dumps(fields, sort_keys=True, separators=(",", ":")),
        dhash_hex=dhash(to_grayscale(image.px)),
        sig_hex=record["sig"].hex(),
        file_name=file_name,
    )
    ledger.append(session, row)
    session.commit()
    return row, elapsed_ms
