from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_token, new_device_token, require_admin
from app.db import get_session
from app.models import Device, iso_utc
from app.seal import keys

router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    hospital: str = Field(default="", max_length=300)


def device_json(d: Device) -> dict:
    return {
        "id": d.id,
        "name": d.name,
        "hospital": d.hospital,
        "public_key_hex": d.public_key_hex,
        "revoked": d.revoked,
        "created_at": iso_utc(d.created_at),
    }


@router.get("")
def list_devices(session: Session = Depends(get_session)):
    return [device_json(d) for d in session.scalars(select(Device).order_by(Device.id))]


@router.post("", status_code=201, dependencies=[Depends(require_admin)])
def create_device(body: DeviceIn, session: Session = Depends(get_session)):
    """Creates the device, its key pair and a bearer token.

    The token is returned ONLY in this response — only its sha256 is stored (token_hash).
    Whoever holds it can seal images as this device via POST /seal; keep it as secret as
    the private key itself (e.g. MEDSEAL_DEVICE_TOKEN in the gateway's own .env, never in
    a browser-exposed NEXT_PUBLIC_* variable).
    """
    device = Device(name=body.name, hospital=body.hospital, public_key_hex="")
    session.add(device)
    session.flush()
    device.public_key_hex = keys.create_device_key(device.id)
    token = new_device_token()
    device.token_hash = hash_token(token)
    session.commit()
    return device_json(device) | {"token": token}


@router.post("/{device_id}/revoke", dependencies=[Depends(require_admin)])
def revoke_device(device_id: int, session: Session = Depends(get_session)):
    """Seals made by this device AFTER revoked_at verify as `forged` (reason: device_revoked).
    Seals made before it (e.g. the key was stolen just now, not at creation) stay authentic/tampered
    as normal, with a warning — see verify.service."""
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(404, "Device not found")
    device.revoked = True
    # Full precision (not the whole-second utcnow() used for hashed ledger timestamps): revoked_at
    # is never part of a hash, and second-level rounding could otherwise tie with a seal's
    # created_at made moments earlier in the same test/request burst.
    device.revoked_at = datetime.now(timezone.utc)
    session.commit()
    return device_json(device)
