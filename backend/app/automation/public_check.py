"""Patient-facing check behind a QR code: anyone holding the link can confirm a seal is genuine.

Shows only what is safe to show a stranger: status, hospital, device, date, image size.
Never the image, never patient data. The token is random (not the sequential seal id),
so links cannot be enumerated.
"""
import io
import json
import secrets

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.imaging import LoadedImage
from app.models import PublicCheck, Seal, iso_utc
from app.anchor import service as anchoring
from app.verify.service import _check_row, verify_upload


def token_for(session: Session, seal_id: int) -> str:
    """The seal's check token, created on first use.

    seal_id is UNIQUE here, so two concurrent seals of the same image (the idempotent path returns
    one row) would both insert and one would get a raw IntegrityError -> 500. Re-read on conflict.
    """
    row = session.scalar(select(PublicCheck).where(PublicCheck.seal_id == seal_id))
    if row is not None:
        return row.token
    row = PublicCheck(token=secrets.token_urlsafe(12), seal_id=seal_id)
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(select(PublicCheck).where(PublicCheck.seal_id == seal_id))
        if existing is None:  # lost to a concurrent delete: let the caller see the real error
            raise
        return existing.token
    return row.token


def find(session: Session, token: str) -> Seal | None:
    check = session.scalar(select(PublicCheck).where(PublicCheck.token == token))
    return session.get(Seal, check.seal_id) if check else None


def public_status(session: Session, seal: Seal) -> dict:
    """Is the seal record itself genuine? (Whether a given FILE matches it needs the file: see check_file.)"""
    device, reason, warning = _check_row(session, seal)
    if reason is None and (anchoring.check(session, seal) or {}).get("status") == "mismatch":
        reason = "blockchain_mismatch"
    return {
        "status": "invalid" if reason else ("warning" if warning else "valid"),
        "reason": reason or warning,
        "hospital": device.hospital if device else None,
        "device": device.name if device else None,
        "sealed_at": iso_utc(seal.created_at),
        "shape": json.loads(seal.shape),
    }


def check_file(session: Session, seal: Seal, image: LoadedImage) -> dict:
    """Does this file match the sealed image behind the link?"""
    if image.uid != seal.uid:
        return {"status": "mismatch"}  # a different image than the one this QR belongs to
    result = verify_upload(session, image, actor="patient-qr")
    return {
        "status": result["status"],
        "reason": result.get("reason"),
        "changed_tiles": len(result["changed_tiles"]),
        "preview_png": result["preview_png"],
    }


def qr_png(url: str) -> bytes:
    import qrcode

    img = qrcode.make(url, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

