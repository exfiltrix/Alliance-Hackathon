from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

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


@router.post("", status_code=201)
def create_device(body: DeviceIn, session: Session = Depends(get_session)):
    """Creates the device and its key pair. Only the public key is returned."""
    device = Device(name=body.name, hospital=body.hospital, public_key_hex="")
    session.add(device)
    session.flush()
    device.public_key_hex = keys.create_device_key(device.id)
    session.commit()
    return device_json(device)


@router.post("/{device_id}/revoke")
def revoke_device(device_id: int, session: Session = Depends(get_session)):
    """After revocation, seals made by this device verify as `forged` (reason: device_revoked)."""
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(404, "Device not found")
    device.revoked = True
    session.commit()
    return device_json(device)
