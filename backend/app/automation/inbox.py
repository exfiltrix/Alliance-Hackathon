"""Doctor's inbox: every incoming image is verified automatically and ranked by urgency.

The doctor never checks images by hand: green items need nothing, only red ones need a look.
  danger   tampered / forged / hidden attack found by the shield
  warning  no seal (the detective gives a probability), or sealed by a device revoked later
  ok       authentic and the shield is quiet
"""
import json

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.imaging import ImageError, load_image
from app.models import InboxItem, iso_utc
from app.verify.service import verify_upload

SEVERITY_RANK = {"danger": 0, "warning": 1, "ok": 2}


def triage(result: dict) -> tuple[str, list[str]]:
    """-> (severity, reason codes) for a /verify result."""
    reasons = []
    if result["status"] in ("tampered", "forged"):
        reasons.append(result["status"])
    if (result.get("shield") or {}).get("attack_suspected"):
        reasons.append("attack_suspected")
    if reasons:
        return "danger", reasons
    if result["status"] == "unsigned":
        return "warning", ["unsigned"]
    if result.get("warning"):
        return "warning", [result["warning"]]
    return "ok", []


def process(session: Session, data: bytes, file_name: str, source: str) -> InboxItem:
    """Verify one file and store it in the inbox. Unreadable files become red 'error' items."""
    try:
        result = verify_upload(session, load_image(data))
        severity, reasons = triage(result)
        status = result["status"]
    except ImageError as e:
        result, severity, reasons, status = {"error": str(e)}, "danger", ["unreadable"], "error"
    item = InboxItem(
        file_name=file_name[:300],
        source=source,
        status=status,
        severity=severity,
        reasons_json=json.dumps(reasons),
        result_json=json.dumps(result),
    )
    session.add(item)
    session.commit()
    return item


def summary(item: InboxItem) -> dict:
    result = json.loads(item.result_json)
    detective = result.get("detective") or {}
    return {
        "id": item.id,
        "file_name": item.file_name,
        "source": item.source,
        "received_at": iso_utc(item.received_at),
        "status": item.status,
        "severity": item.severity,
        "reasons": json.loads(item.reasons_json),
        "reviewed": item.reviewed,
        "device": result.get("device"),
        "changed_tiles": len(result.get("changed_tiles") or []),
        "detective_probability": detective.get("probability"),
        "error": result.get("error"),
    }


def detail(item: InboxItem) -> dict:
    return summary(item) | {"result": json.loads(item.result_json)}


def listing(session: Session, limit: int = 200) -> dict:
    """Unreviewed first, then most urgent, then newest."""
    rank = case(SEVERITY_RANK, value=InboxItem.severity, else_=3)
    rows = session.scalars(
        select(InboxItem).order_by(InboxItem.reviewed, rank, InboxItem.id.desc()).limit(limit)
    )
    counts = dict(session.execute(
        select(InboxItem.severity, func.count()).where(InboxItem.reviewed.is_(False)).group_by(InboxItem.severity)
    ).all())
    return {
        "counts": {s: counts.get(s, 0) for s in SEVERITY_RANK} | {"total": session.scalar(select(func.count(InboxItem.id)))},
        "items": [summary(r) for r in rows],
    }
