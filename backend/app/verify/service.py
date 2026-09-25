"""Verify an uploaded image against the ledger.

Status order matters: unsigned (no record, no content match) -> forged (record not authentic) ->
tampered (tile or metadata mismatch) -> authentic. Changed tiles are only meaningful when the
record itself is authentic.
"""
import json
import time

from sqlalchemy.orm import Session

from app.ai import hooks
from app.imaging import LoadedImage, meta_fields, meta_hash, to_grayscale
from app.models import Device, Verification
from app.seal import core, keys, ledger, recovery
from app.verify.preview import render_preview

DOCTOR_NOTE = "Final decision is made by the doctor."


def _check_row(session: Session, row) -> tuple[Device | None, str | None, str | None]:
    """Returns (device, reason the record is forged or None, a non-fatal warning reason or None).

    Revocation is not retroactive: a seal made BEFORE revoked_at is trusted as usual (the
    device's key was presumably fine back then) but carries a warning, since we can no longer
    vouch for the device going forward. Only seals made at/after revoked_at are forged outright.
    """
    device = session.get(Device, row.device_id)
    if device is None:
        return None, "unknown_device", None
    if not ledger.row_is_intact(row):
        return device, "ledger_entry_modified", None
    if device.revoked and device.revoked_at is not None and row.created_at >= device.revoked_at:
        return device, "device_revoked", None
    if not core.check_record(ledger.to_record(row), keys.public_key_from_hex(device.public_key_hex)):
        return device, "bad_signature", None
    warning = "device_revoked_later" if device.revoked else None
    return device, None, warning


def _metadata_changed(image: LoadedImage, row) -> tuple[bool, list[str]]:
    """P0-5: RescaleIntercept, Laterality, WindowCenter etc. never touch pixel data, so they
    need their own comparison — changed_tiles alone cannot see them."""
    if not row.meta_hash_hex:
        return False, []
    current_meta = meta_fields(image)
    if meta_hash(current_meta).hex() == row.meta_hash_hex:
        return False, []
    stored_meta = json.loads(row.meta_json or "{}")
    changed = sorted(k for k in set(stored_meta) | set(current_meta) if stored_meta.get(k) != current_meta.get(k))
    return True, changed


def verify_upload(session: Session, image: LoadedImage) -> dict:
    t0 = time.perf_counter()
    row = ledger.find_by_uid(session, image.uid) if image.uid else None
    matched_by: str | None = "uid" if row is not None else None

    # P1-03: the image's ID was stripped, replaced, or its metadata chunk was dropped by a
    # re-save — fall back to content: same shape/dtype and >=50% identical tiles against a
    # previously sealed image (see app.seal.recovery for why this cannot false-match unrelated
    # X-rays).
    if row is None:
        shape_json = json.dumps(list(image.px.shape))
        match = recovery.find_content_match(session, image.px, shape_json, str(image.px.dtype))
        if match:
            row, _fraction = match
            matched_by = "content"

    result = {
        "status": "",
        "uid": image.uid,
        "device": None,
        "seal_id": None,
        "changed_tiles": [],
        "tile": None,
        "matched_by": matched_by,
    }

    if row is None:
        result["status"] = "unsigned"
    else:
        device, reason, warning = _check_row(session, row)
        result.update(device=device.name if device else None, seal_id=row.id, tile=row.tile)
        if reason:
            result.update(status="forged", reason=reason)
        elif matched_by == "content":
            changed = core.changed_tiles(image.px, ledger.to_record(row))
            meta_changed, _ = _metadata_changed(image, row)
            if changed or meta_changed:
                result.update(
                    status="tampered", reason="seal_id_removed", changed_tiles=[list(k) for k in changed]
                )
            else:
                result.update(status="authentic", warning="seal_id_missing")
        else:
            changed = core.changed_tiles(image.px, ledger.to_record(row))
            meta_changed, changed_meta = _metadata_changed(image, row)
            result.update(
                status="tampered" if (changed or meta_changed) else "authentic",
                changed_tiles=[list(k) for k in changed],
            )
            if meta_changed:
                result.update(reason="metadata_changed", changed_meta=changed_meta)
            if warning:
                result["warning"] = warning
    result["verify_ms"] = round((time.perf_counter() - t0) * 1000, 2)

    # The seal above hashes every channel (P0-3); display and the AI modules only ever need
    # grayscale, converted here — that conversion never touches what got hashed.
    gray = to_grayscale(image.px)
    result["preview_png"] = render_preview(gray, result["changed_tiles"], result["tile"] or 0)
    if result["status"] == "unsigned":
        result["detective"] = hooks.run_detective(gray)
    result["shield"] = hooks.run_shield(gray)
    result["note"] = DOCTOR_NOTE

    session.add(
        Verification(
            uid=image.uid,
            result=result["status"],
            changed_tiles_json=json.dumps(result["changed_tiles"]),
            detective_prob=(result.get("detective") or {}).get("probability"),
            shield_flag=(result["shield"] or {}).get("attack_suspected"),
        )
    )
    session.commit()
    return result
