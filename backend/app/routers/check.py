"""Public QR check for patients and anyone they show a document to. No login, no patient data."""
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.automation import public_check
from app.db import get_session
from app.routers.common import read_upload

router = APIRouter(tags=["check"])


def _seal(session: Session, token: str):
    seal = public_check.find(session, token)
    if seal is None:
        raise HTTPException(404, "Check link not found")
    return seal


@router.get("/check/{token}")
def check(token: str, session: Session = Depends(get_session)):
    return public_check.public_status(session, _seal(session, token))


@router.post("/check/{token}")
async def check_file(token: str, file: UploadFile = File(...), session: Session = Depends(get_session)):
    seal = _seal(session, token)
    # Verification decodes, hashes and may run the AI: off the event loop, like POST /verify.
    return await run_in_threadpool(public_check.check_file, session, seal, await read_upload(file))


@router.get("/check/{token}/qr.png")
def qr(token: str, url: str, session: Session = Depends(get_session)):
    """QR code for `url` (the frontend page of this check; the backend does not know the site's address)."""
    _seal(session, token)
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or len(url) > 300 or token not in parsed.path:
        raise HTTPException(422, "url must be the http(s) check page for this token")
    return Response(public_check.qr_png(url), media_type="image/png", headers={"Cache-Control": "max-age=86400"})
