"""Audit log helper. The caller commits (so the event lands together with what it describes)."""
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditEvent, iso_utc


def client_ip(request: Request | None) -> str | None:
    return request.client.host if request is not None and request.client else None


def log(session: Session, action: str, actor: str, target: str = "", result: str = "",
        ip: str | None = None) -> None:
    session.add(AuditEvent(action=action, actor=actor[:200], target=target[:200], result=result[:64], ip=ip))


def listing(session: Session, limit: int = 200, action: str | None = None) -> list[dict]:
    q = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
    if action:
        q = q.where(AuditEvent.action == action)
    return [
        {"id": e.id, "at": iso_utc(e.at), "action": e.action, "actor": e.actor, "target": e.target,
         "result": e.result, "ip": e.ip}
        for e in session.scalars(q)
    ]
