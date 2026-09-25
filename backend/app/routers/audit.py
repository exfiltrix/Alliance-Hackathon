from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import audit
from app.auth import require_admin
from app.db import get_session

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", dependencies=[Depends(require_admin)])
def list_audit(limit: int = 200, action: str | None = None, session: Session = Depends(get_session)):
    """Newest first. Read-only on purpose: no endpoint changes or deletes audit rows."""
    return audit.listing(session, min(max(limit, 1), 1000), action)
