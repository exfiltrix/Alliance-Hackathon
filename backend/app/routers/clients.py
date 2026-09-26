"""Client (hospital/clinic) cabinet: an org-level view, strictly scoped to one hospital.

Every /client/* endpoint requires a client token or the admin token with ?org= — see
app.auth.require_client. "hospital" is the same free-text string already stored on
Device.hospital and Passport.organisation; there is no separate organisation table.
"""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import audit
from app.auth import hash_token, new_device_token, require_admin, require_client
from app.db import get_session
from app.models import ClientAccount, Device, Passport, Seal, Verification, iso_utc, utcnow
from app.routers.passport import passport_json
from app.seal import keys

router = APIRouter(tags=["clients"])


class ClientIn(BaseModel):
    hospital: str = Field(min_length=1, max_length=300)


@router.post("/clients", status_code=201, dependencies=[Depends(require_admin)])
def create_client(body: ClientIn, request: Request, session: Session = Depends(get_session)):
    """Create the org-level login for a hospital. The token is returned ONLY in this response —
    only its sha256 is stored (token_hash) — same handling as a device token (POST /devices)."""
    hospital = body.hospital.strip()
    if session.scalar(select(ClientAccount).where(ClientAccount.hospital == hospital)) is not None:
        raise HTTPException(409, "A client account for this hospital already exists")
    token = new_device_token()
    account = ClientAccount(hospital=hospital, token_hash=hash_token(token), created_at=utcnow())
    session.add(account)
    session.flush()
    audit.log(session, "client_create", "admin", target=f"client:{account.id}", result=hospital,
              ip=audit.client_ip(request))
    session.commit()
    return {"id": account.id, "hospital": account.hospital, "created_at": iso_utc(account.created_at), "token": token}


@router.get("/client/devices")
def client_devices(hospital: str = Depends(require_client), session: Session = Depends(get_session)):
    devices = session.scalars(select(Device).where(Device.hospital == hospital).order_by(Device.id)).all()
    out = []
    for d in devices:
        last_seal_at = session.scalar(select(func.max(Seal.created_at)).where(Seal.device_id == d.id))
        out.append({
            "id": d.id,
            "name": d.name,
            "revoked": d.revoked,
            "certified": keys.device_certificate_valid(d),
            "created_at": iso_utc(d.created_at),
            "last_seal_at": iso_utc(last_seal_at) if last_seal_at else None,
            "seal_count": session.scalar(select(func.count(Seal.id)).where(Seal.device_id == d.id)) or 0,
        })
    return out


@router.get("/client/stats")
def client_stats(hospital: str = Depends(require_client), session: Session = Depends(get_session)):
    device_ids = select(Device.id).where(Device.hospital == hospital)
    now = utcnow()
    today, week = now - timedelta(hours=24), now - timedelta(days=7)

    def seal_count(since=None) -> int:
        q = select(func.count(Seal.id)).where(Seal.device_id.in_(device_ids))
        if since is not None:
            q = q.where(Seal.created_at >= since)
        return session.scalar(q) or 0

    by_result = dict(session.execute(
        select(Verification.result, func.count())
        .join(Seal, Verification.uid == Seal.uid)
        .where(Seal.device_id.in_(device_ids))
        .group_by(Verification.result)
    ).all())
    device_counts = dict(session.execute(
        select(Device.revoked, func.count()).where(Device.hospital == hospital).group_by(Device.revoked)
    ).all())
    certified = sum(
        1 for d in session.scalars(select(Device).where(Device.hospital == hospital))
        if keys.device_certificate_valid(d)
    )

    return {
        "hospital": hospital,
        "devices": {
            "total": device_counts.get(True, 0) + device_counts.get(False, 0),
            "active": device_counts.get(False, 0),
            "revoked": device_counts.get(True, 0),
            "certified": certified,
        },
        "seals": {"today": seal_count(today), "7d": seal_count(week), "total": seal_count()},
        # Only verifications of this org's own sealed images (joined on Seal.uid): a check made
        # elsewhere of someone else's image never counts toward this hospital's numbers.
        "verifications": {"total": sum(by_result.values()), "by_result": by_result},
    }


@router.get("/client/alerts")
def client_alerts(limit: int = 50, hospital: str = Depends(require_client), session: Session = Depends(get_session)):
    """Recent non-authentic outcomes for this org's own sealed images, newest first."""
    device_ids = select(Device.id).where(Device.hospital == hospital)
    rows = session.execute(
        select(Verification, Seal.id, Device.name)
        .join(Seal, Verification.uid == Seal.uid)
        .join(Device, Seal.device_id == Device.id)
        .where(Seal.device_id.in_(device_ids), Verification.result != "authentic")
        .order_by(Verification.id.desc())
        .limit(min(max(limit, 1), 200))
    ).all()
    return [
        {
            "at": iso_utc(v.created_at),
            "seal_id": seal_id,
            "uid": v.uid,
            "device": device_name,
            "result": v.result,
            "shield_flag": v.shield_flag,
        }
        for v, seal_id, device_name in rows
    ]


@router.get("/client/passports")
def client_passports(hospital: str = Depends(require_client), session: Session = Depends(get_session)):
    rows = session.scalars(select(Passport).where(Passport.organisation == hospital).order_by(Passport.id.desc()))
    return [passport_json(p) for p in rows]
