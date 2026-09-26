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
from app.models import ClientAccount, Device, Seal


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
    # Compare bytes so a non-ASCII request cannot raise a TypeError and turn auth into a 500.
    if not _token_matches(token, settings.admin_token):
        raise _deny(session, request, "admin?", 401, "Invalid admin token")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_device_token() -> str:
    return secrets.token_urlsafe(32)


def _token_matches(token: str, expected: str) -> bool:
    """Constant-time byte comparison. `expected` empty means 'not configured' and never matches."""
    return bool(expected) and hmac.compare_digest(token.encode(), expected.encode())


def require_doctor(
    request: Request,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> str:
    """Authorize the doctor's cabinet: /inbox*, review and /automation*.

    The inbox holds real medical images (`result_json` carries the rendered preview), so it must
    never be readable anonymously. Accepts MEDSEAL_DOCTOR_TOKEN and the admin token; when neither is
    configured the request is refused (fail closed) exactly like require_admin.
    """
    # Configuration is checked before the header, so an operator who forgot the env var gets a
    # diagnosable 503 instead of a bare 401 that looks like a wrong password.
    if not (settings.doctor_token or settings.admin_token):
        raise _deny(session, request, "doctor?", 503, "Doctor access is not configured")
    try:
        token = _bearer(authorization)
    except HTTPException as e:
        raise _deny(session, request, "doctor?", e.status_code, e.detail) from None
    if _token_matches(token, settings.doctor_token) or _token_matches(token, settings.admin_token):
        return "admin" if _token_matches(token, settings.admin_token) else "doctor"
    raise _deny(session, request, "doctor?", 401, "Invalid doctor token")


def require_client(
    request: Request,
    org: str | None = None,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> str:
    """Authorize the client cabinet (/client/*) and return the hospital to scope every query by.

    A client token is minted for exactly one hospital (POST /clients, admin-only) and always
    resolves to that hospital, ignoring any ?org= a caller supplies — trusting client-controlled
    input for the scope would be the same horizontal-IDOR mistake require_seal_owner exists to
    prevent for sealed files. The admin token may inspect any organisation, but must name it.
    """
    try:
        token = _bearer(authorization)
    except HTTPException as e:
        raise _deny(session, request, "client?", e.status_code, e.detail) from None
    if _token_matches(token, settings.admin_token):
        if not org:
            raise HTTPException(400, "org is required when using the admin token")
        return org
    account = session.scalar(select(ClientAccount).where(ClientAccount.token_hash == hash_token(token)))
    if account is None:
        raise _deny(session, request, "client?", 401, "Invalid client token")
    return account.hospital


def require_seal_owner(
    request: Request,
    seal_id: int,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> None:
    """Authorize reading one sealed file: the admin, or the device that actually produced it.

    Any-device-is-allowed would be a horizontal IDOR: a gateway from hospital B could walk
    /api/seal/{id}/file and download every image ever sealed by hospital A's scanners.
    """
    try:
        token = _bearer(authorization)
    except HTTPException as e:
        raise _deny(session, request, "device?", e.status_code, e.detail) from None
    if _token_matches(token, settings.admin_token):
        return
    device = session.scalar(select(Device).where(Device.token_hash == hash_token(token)))
    if device is None:
        raise _deny(session, request, "device?", 401, "Invalid device or admin token")
    row = session.get(Seal, seal_id)
    if row is None or row.device_id != device.id:
        raise _deny(session, request, f"device:{device.name}", 403, "This seal belongs to another device")


def require_device_or_admin(
    request: Request,
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> Device | None:
    """Authorize read-only device artifacts with either the admin token or a device token."""
    try:
        token = _bearer(authorization)
    except HTTPException as e:
        raise _deny(session, request, "device?", e.status_code, e.detail) from None
    if _token_matches(token, settings.admin_token):
        return None
    device = session.scalar(select(Device).where(Device.token_hash == hash_token(token)))
    if device is None:
        raise _deny(session, request, "device?", 401, "Invalid device or admin token")
    return device


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
