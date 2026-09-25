"""Bearer-token auth for the write endpoints (P0-1).

Two kinds of token:
- the admin token (MEDSEAL_ADMIN_TOKEN) gates POST /devices and /devices/{id}/revoke;
- a per-device token (returned once by POST /devices, stored only as sha256) gates POST /seal
  and resolves *which* device is sealing — the client can no longer just pass a device_id.
"""
import hashlib
import hmac
import secrets

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import audit
from app.config import settings
from app.db import get_session
from app.models import Device


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing bearer token")
    return authorization.removeprefix("Bearer ").strip()


def _deny(session: Session, request: Request, who: str, status: int, message: str) -> HTTPException:
    """Failed credentials are audited (T11: brute force / stolen-token attempts show up)."""
    audit.log(session, "auth_failed", who, target=request.url.path, result=str(status), ip=audit.client_ip(request))
    session.commit()
    return HTTPException(status, message)


def require_admin(
    request: Request,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> None:
    try:
        token = _bearer(authorization)
    except HTTPException as e:
        raise _deny(session, request, "admin?", e.status_code, e.detail) from None
    if not settings.admin_token or not hmac.compare_digest(token, settings.admin_token):
        raise _deny(session, request, "admin?", 401, "Invalid admin token")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_device_token() -> str:
    return secrets.token_urlsafe(32)


def require_device(
    request: Request,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> Device:
    """Resolves the device from its bearer token. Never trust a client-supplied device_id."""
    try:
        token_hash = hash_token(_bearer(authorization))
    except HTTPException as e:
        raise _deny(session, request, "device?", e.status_code, e.detail) from None
    device = session.scalar(select(Device).where(Device.token_hash == token_hash))
    if device is None:
        raise _deny(session, request, "device?", 401, "Invalid device token")
    if device.revoked:
        raise _deny(session, request, f"device:{device.name}", 403, "Device is revoked")
    return device
