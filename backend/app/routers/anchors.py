from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import audit
from app.anchor import service
from app.anchor.chain import ChainError, configured
from app.auth import require_admin
from app.db import get_session

router = APIRouter(prefix="/anchors", tags=["blockchain"])


@router.get("")
def list_anchors(session: Session = Depends(get_session)):
    return {"enabled": configured(), "pending": len(service.unanchored(session)),
            "anchors": service.list_anchors(session)}


@router.post("/run", dependencies=[Depends(require_admin)])
def run(request: Request, session: Session = Depends(get_session)):
    """Anchor every pending seal now (demo). Blocks until the transaction is confirmed."""
    try:
        anchor = service.run_batch(session, actor="admin", ip=audit.client_ip(request))
    except ChainError as e:
        raise HTTPException(503, str(e)) from e
    if anchor is None:
        return {"anchored": 0, "anchor": None}
    return {"anchored": anchor.count, "anchor": service.list_anchors(session)[0]}
