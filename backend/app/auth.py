"""Bearer-token auth for the write endpoints (P0-1).

Two kinds of token:
- the admin token (MEDSEAL_ADMIN_TOKEN) gates POST /devices and /devices/{id}/revoke;
- a per-device token (returned once by POST /devices, stored only as sha256) gates POST /seal
  and resolves *which* device is sealing — the client can no longer just pass a device_id.
"""
import hashlib
import hmac
import secrets

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.models import Device


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token")
    return authorization.removeprefix("Bearer ").strip()


def require_admin(authorization: str | None = Header(default=None)) -> None:
    token = _bearer(authorization)
    # Compare bytes so a non-ASCII request cannot raise a TypeError and turn auth into a 500.
    if not settings.admin_token or not hmac.compare_digest(token.encode(), settings.admin_token.encode()):
        raise HTTPException(401, "Invalid admin token")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_device_token() -> str:
    return secrets.token_urlsafe(32)


def require_device_or_admin(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> Device | None:
    """Authorize read-only device artifacts with either the admin token or a device token."""
    token = _bearer(authorization)
    if settings.admin_token and hmac.compare_digest(token.encode(), settings.admin_token.encode()):
        return None
    device = session.scalar(select(Device).where(Device.token_hash == hash_token(token)))
    if device is None:
        raise HTTPException(401, "Invalid device or admin token")
    return device


def require_device(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> Device:
    """Resolves the device from its bearer token. Never trust a client-supplied device_id."""
    token_hash = hash_token(_bearer(authorization))
    device = session.scalar(select(Device).where(Device.token_hash == token_hash))
    if device is None:
        raise HTTPException(401, "Invalid device token")
    if device.revoked:
        raise HTTPException(403, "Device is revoked")
    return device
