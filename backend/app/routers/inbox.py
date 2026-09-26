"""Doctor's inbox (automatic verification) and folder-automation status.

Every endpoint here requires the doctor token (or the admin token) — see app.auth.require_doctor.
The inbox carries real medical images (result_json holds the rendered preview), so it must never
be readable anonymously, and POST /automation/run triggers CPU-heavy verification with AI.
"""
import time
from datetime import date, datetime, time as dtime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app import audit
from app.auth import require_doctor
from app.automation import inbox, pdf, watcher
from app.config import settings
from app.db import get_session
from app.models import InboxItem

router = APIRouter(tags=["inbox"], dependencies=[Depends(require_doctor)])
MAX_FILES = 50
# Per-file limits alone still allow 50 x 50 MB in one request; cap the batch as a whole.
MAX_BATCH_BYTES = 200 * 1024 * 1024


def _parse_date(value: str | None, *, end: bool) -> datetime | None:
    """A plain "YYYY-MM-DD" from the doctor's date-range filter, at the start or end of that day."""
    if not value:
        return None
    try:
        d = date.fromisoformat(value)
    except ValueError:
        raise HTTPException(422, "since/until must be an ISO date, e.g. 2026-09-26") from None
    return datetime.combine(d, dtime.max if end else dtime.min, tzinfo=timezone.utc)


@router.post("/inbox")
async def add_to_inbox(request: Request, files: list[UploadFile] = File(...),
                        session: Session = Depends(get_session)):
    """Batch upload: every file is verified at once; returns the new items, most urgent first.

    Verification runs in the threadpool — decoding, tile hashing and (optionally) the AI are far
    too slow to run on the event loop, where they would stall every other request.
    """
    if len(files) > MAX_FILES:
        raise HTTPException(413, f"At most {MAX_FILES} files per upload")
    items = []
    total = 0
    for f in files:
        data = await f.read(settings.max_upload_bytes + 1)
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(413, f"{f.filename}: file is too large")
        total += len(data)
        if total > MAX_BATCH_BYTES:
            raise HTTPException(413, f"Total upload is larger than {MAX_BATCH_BYTES // (1024 * 1024)} MB")
        # run_in_threadpool, like POST /verify and POST /seal already do.
        items.append(await run_in_threadpool(inbox.process, session, data, f.filename or "image", "upload"))
    items.sort(key=lambda i: (inbox.SEVERITY_RANK[i.severity], -i.id))
    return [inbox.summary(i) for i in items]


@router.get("/inbox")
def list_inbox(limit: int = 200, offset: int = 0, severity: str | None = None, reviewed: bool | None = None,
               since: str | None = None, until: str | None = None, session: Session = Depends(get_session)):
    return inbox.listing(
        session, min(max(limit, 1), 500), severity, reviewed,
        since=_parse_date(since, end=False), until=_parse_date(until, end=True), offset=max(offset, 0),
    )


@router.get("/inbox/{item_id}")
def inbox_item(item_id: int, session: Session = Depends(get_session)):
    item = session.get(InboxItem, item_id)
    if item is None:
        raise HTTPException(404, "Inbox item not found")
    return inbox.detail(item)


@router.get("/inbox/{item_id}/pdf")
def inbox_item_pdf(item_id: int, lang: Literal["uz", "ru"] = "uz", session: Session = Depends(get_session)):
    item = session.get(InboxItem, item_id)
    if item is None:
        raise HTTPException(404, "Inbox item not found")
    body = pdf.render([inbox.detail(item)], lang)
    return Response(body, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="medseal-check-{item_id}-{lang}.pdf"'})


class BatchPdfIn(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=MAX_FILES)


@router.post("/inbox/batch-pdf")
def inbox_batch_pdf(body: BatchPdfIn, lang: Literal["uz", "ru"] = "uz", session: Session = Depends(get_session)):
    items = []
    for item_id in body.ids:
        item = session.get(InboxItem, item_id)
        if item is None:
            raise HTTPException(404, f"Inbox item {item_id} not found")
        items.append(inbox.detail(item))
    body_bytes = pdf.render(items, lang)
    return Response(body_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="medseal-inbox-batch-{lang}.pdf"'})


@router.post("/inbox/{item_id}/review")
def review(request: Request, item_id: int, session: Session = Depends(get_session)):
    """Mark as looked at. Idempotent, and audited: clearing a red flag is a clinical action."""
    item = session.get(InboxItem, item_id)
    if item is None:
        raise HTTPException(404, "Inbox item not found")
    was = item.reviewed
    item.reviewed = True
    audit.log(session, "inbox_review", "doctor", target=f"inbox:{item_id}",
              result="already_reviewed" if was else "reviewed", ip=audit.client_ip(request))
    session.commit()
    return inbox.summary(item)


@router.get("/automation")
def automation_status():
    return watcher.status() | {"warmup": settings.warmup and settings.ai_enabled}


@router.post("/automation/run")
def automation_run_now(request: Request, session: Session = Depends(get_session)):
    """Process the watched folders right now instead of waiting for the next poll."""
    t0 = time.perf_counter()
    sealed, verified = watcher.run_once()
    audit.log(session, "automation_run", "doctor", result=f"sealed:{sealed},verified:{verified}",
              ip=audit.client_ip(request))
    session.commit()
    return {"sealed": sealed, "verified": verified, "elapsed_ms": round((time.perf_counter() - t0) * 1000, 2)}
