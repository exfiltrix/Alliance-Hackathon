"""Verify an uploaded image against the ledger.

Status order matters: unsigned (no record) -> forged (record not authentic) ->
tampered (tile mismatch) -> authentic. Changed tiles are only meaningful when
the record itself is authentic.
"""
import json
import time

from sqlalchemy.orm import Session

from app.ai import hooks
from app.imaging import LoadedImage
from app.models import Device, Verification
from app.seal import core, keys, ledger
from app.verify.preview import render_preview

DOCTOR_NOTE = "Final decision is made by the doctor."


def _check_row(session: Session, row) -> tuple[Device | None, str | None]:
    """Returns (device, reason the record is forged or None)."""
    device = session.get(Device, row.device_id)
    if device is None:
        return None, "unknown_device"
    if not ledger.row_is_intact(row):
        return device, "ledger_entry_modified"
    if device.revoked:
        return device, "device_revoked"
    if not core.check_record(ledger.to_record(row), keys.public_key_from_hex(device.public_key_hex)):
        return device, "bad_signature"
    return device, None


def verify_upload(session: Session, image: LoadedImage) -> dict:
    t0 = time.perf_counter()
    row = ledger.find_by_uid(session, image.uid) if image.uid else None
    result = {"status": "", "uid": image.uid, "device": None, "seal_id": None, "changed_tiles": [], "tile": None}

    if row is None:
        result["status"] = "unsigned"
    else:
        device, reason = _check_row(session, row)
        result.update(device=device.name if device else None, seal_id=row.id, tile=row.tile)
        if reason:
            result.update(status="forged", reason=reason)
        else:
            changed = core.changed_tiles(image.px, ledger.to_record(row))
            result.update(status="tampered" if changed else "authentic", changed_tiles=[list(k) for k in changed])
    result["verify_ms"] = round((time.perf_counter() - t0) * 1000, 2)

    result["preview_png"] = render_preview(image.px, result["changed_tiles"], result["tile"] or 0)
    if result["status"] == "unsigned":
        result["detective"] = hooks.run_detective(image.px)
    result["shield"] = hooks.run_shield(image.px)
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
