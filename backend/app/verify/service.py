"""Verify an uploaded image against the ledger.

The native array is used for the frozen tile/Merkle checks. Only the display view is
passed to previews and AI, so DICOM LUT/windowing changes are metadata changes rather
than accidental pixel-hash changes.

Status order matters: unsigned (no record) -> forged (record not authentic) ->
tampered (tile mismatch) -> authentic. Changed tiles are only meaningful when
the record itself is authentic.

The blockchain check (app.anchor) runs for every sealed image. A mismatch means our own
database was rewritten, so it overrides a locally clean result: forged / blockchain_mismatch.
"""
import json
import time

from sqlalchemy.orm import Session

from app import audit
from app.ai import hooks
from app.anchor import service as anchoring
from app.config import settings
from app.imaging import (
    LoadedImage,
    ai_applicable,
    display_pixels,
    meta_fields,
    meta_hash,
    patient_reference,
)
from app.models import Device, Verification, iso_utc
from app.seal import core, keys, ledger, recovery, signing
from app.verify.preview import render_preview

DOCTOR_NOTE = "Final decision is made by the doctor."


def _analysis(result: dict, display) -> dict | None:
    """AI reading only for a trusted image: authentic seal and a shield that saw no attack."""
    if not settings.ai_enabled:
        return None
    from app.ai import analysis  # torch-free

    if result["status"] != "authentic":
        return analysis.blocked(result["status"])
    if result["shield"] is None:
        return analysis.blocked("shield_unavailable")
    if result["shield"]["attack_suspected"]:
        return analysis.blocked("attack_suspected")
    return hooks.run_analysis(display)


def _check_row(session: Session, row) -> tuple[Device | None, str | None, str | None]:
    """Return (device, fatal reason, non-fatal warning).

    Revocation is not retroactive: a seal made BEFORE revoked_at is trusted as usual (the
    device's key was presumably fine back then) but carries a warning, since we can no longer
    vouch for the device going forward. Only seals made at/after revoked_at are forged outright.
    """
    device = session.get(Device, row.device_id)
    if device is None:
        return None, "unknown_device", None

    if settings.require_device_cert and not keys.device_certificate_valid(device):
        return device, "untrusted_device", None

    # v2 signs created_at/device_id itself. Check that signature before the hash-chain
    # diagnostic so editing either field is reported as bad_signature as specified.
    if (row.sig_version or 1) >= 2:
        try:
            valid_signature = signing.check_v2(
                bytes.fromhex(row.sig_hex),
                keys.public_key_from_hex(device.public_key_hex),
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
            )
        except (ValueError, TypeError):
            valid_signature = False
        if not valid_signature:
            return device, "bad_signature", None

    if not ledger.row_is_intact(row):
        return device, "ledger_entry_modified", None
    if device.revoked and device.revoked_at is not None and row.created_at >= device.revoked_at:
        return device, "device_revoked", None
    if (row.sig_version or 1) < 2 and not core.check_record(
        ledger.to_record(row), keys.public_key_from_hex(device.public_key_hex)
    ):
        return device, "bad_signature", None

    warning = "device_not_certified" if not keys.device_certificate_valid(device) else None
    if device.revoked:
        warning = "device_revoked_later"
    return device, None, warning


def _metadata_changed(image: LoadedImage, row) -> tuple[bool, list[str]]:
    if not row.meta_hash_hex:
        return False, []
    current_meta = meta_fields(image, version=row.meta_version or 1)
    if meta_hash(current_meta).hex() == row.meta_hash_hex:
        return False, []
    stored_meta = json.loads(row.meta_json or "{}")
    changed = sorted(k for k in set(stored_meta) | set(current_meta) if stored_meta.get(k) != current_meta.get(k))
    return True, changed


def _patient_check(image: LoadedImage, row) -> tuple[str, str | None]:
    if (row.sig_version or 1) < 2 or not row.patient_ref or not image.patient_id or not settings.patient_salt:
        return "not_available", None
    current = patient_reference(image.patient_id)
    if current == row.patient_ref:
        return "matched", None
    return "mismatch", "patient_mismatch"


def verify_upload(session: Session, image: LoadedImage, actor: str = "anonymous", ip: str | None = None) -> dict:
    t0 = time.perf_counter()
    row = ledger.find_by_uid(session, image.uid) if image.uid else None
    matched_by: str | None = "uid" if row is not None else None

    if row is None:
        shape_json = json.dumps(list(image.px.shape))
        match = recovery.find_content_match(session, image.px, shape_json, str(image.px.dtype))
        if match:
            row, _fraction = match
            matched_by = "content"

    result = {
        "status": "",
        "uid": row.uid if matched_by == "content" else image.uid,
        "device": None,
        "seal_id": None,
        "changed_tiles": [],
        "tile": None,
        "matched_by": matched_by,
        "patient_check": "not_available",
        "blockchain": None,
    }

    if row is None:
        result["status"] = "unsigned"
    else:
        device, reason, warning = _check_row(session, row)
        blockchain = anchoring.check(session, row)
        if reason is None and (blockchain or {}).get("status") == "mismatch":
            reason = "blockchain_mismatch"
        result.update(device=device.name if device else None, seal_id=row.id, tile=row.tile, blockchain=blockchain)
        patient_check, patient_reason = _patient_check(image, row)
        result["patient_check"] = patient_check
        if reason:
            result.update(status="forged", reason=reason)
        elif patient_reason:
            result.update(status="tampered", reason=patient_reason)
        elif matched_by == "content":
            changed = core.changed_tiles(image.px, ledger.to_record(row))
            meta_changed, changed_meta = _metadata_changed(image, row)
            result["changed_tiles"] = [list(k) for k in changed]
            if changed or meta_changed:
                result.update(status="tampered", reason="seal_id_removed")
                if meta_changed:
                    result["changed_meta"] = changed_meta
            else:
                result.update(status="authentic", warning="seal_id_missing")
        else:
            changed = core.changed_tiles(image.px, ledger.to_record(row))
            meta_changed, changed_meta = _metadata_changed(image, row)
            result.update(
                status="tampered" if (changed or meta_changed) else "authentic",
                changed_tiles=[list(k) for k in changed],
                sealed_at=iso_utc(row.created_at),  # T6: a replayed old image shows its original date
            )
            if meta_changed:
                result.update(reason="metadata_changed", changed_meta=changed_meta)
            if warning:
                result["warning"] = warning

    result["verify_ms"] = round((time.perf_counter() - t0) * 1000, 2)
    display = display_pixels(image)
    result["preview_png"] = render_preview(display, result["changed_tiles"], result["tile"] or 0)

    applicable = ai_applicable(image)
    if applicable:
        if result["status"] == "unsigned":
            result["detective"] = hooks.run_detective(display)
        result["shield"] = hooks.run_shield(display)
        result["analysis"] = _analysis(result, display)
    else:
        result["detective"] = None
        result["shield"] = None
        result["analysis"] = None
        result["ai_note"] = "not_applicable"
    if image.burned_in_annotation:
        result["phi_warning"] = "burned_in_annotation"
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
    outcome = result["status"] + (f":{result['reason']}" if result.get("reason") else "")
    audit.log(session, "verify", actor, target=f"seal:{row.id}" if row else f"uid:{image.uid or '-'}",
              result=outcome, ip=ip)
    session.commit()
    return result
