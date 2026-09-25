"""Doctor's inbox (automatic verification) and folder-automation status."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.automation import inbox, watcher
from app.config import settings
from app.db import get_session
from app.models import InboxItem

router = APIRouter(tags=["inbox"])
MAX_FILES = 50


@router.post("/inbox")
async def add_to_inbox(files: list[UploadFile] = File(...), session: Session = Depends(get_session)):
    """Batch upload: every file is verified at once; returns the new items, most urgent first."""
    if len(files) > MAX_FILES:
        raise HTTPException(413, f"At most {MAX_FILES} files per upload")
    items = []
    for f in files:
        data = await f.read(settings.max_upload_bytes + 1)
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(413, f"{f.filename}: file is too large")
        items.append(inbox.process(session, data, f.filename or "image", source="upload"))
    items.sort(key=lambda i: (inbox.SEVERITY_RANK[i.severity], -i.id))
    return [inbox.summary(i) for i in items]


@router.get("/inbox")
def list_inbox(limit: int = 200, session: Session = Depends(get_session)):
    return inbox.listing(session, min(limit, 500))


@router.get("/inbox/{item_id}")
def inbox_item(item_id: int, session: Session = Depends(get_session)):
    item = session.get(InboxItem, item_id)
    if item is None:
        raise HTTPException(404, "Inbox item not found")
    return inbox.detail(item)


@router.post("/inbox/{item_id}/review")
def review(item_id: int, session: Session = Depends(get_session)):
    item = session.get(InboxItem, item_id)
    if item is None:
        raise HTTPException(404, "Inbox item not found")
    item.reviewed = True
    session.commit()
    return inbox.summary(item)


@router.get("/automation")
def automation_status():
    return watcher.status() | {"warmup": settings.warmup and settings.ai_enabled}


@router.post("/automation/run")
def automation_run_now():
    """Process the watched folders right now instead of waiting for the next poll."""
    sealed, verified = watcher.run_once()
    return {"sealed": sealed, "verified": verified}
