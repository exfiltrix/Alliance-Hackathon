from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session

from app.audit import client_ip
from app.db import get_session
from app.routers.common import read_upload
from app.verify.service import verify_upload

router = APIRouter(tags=["verify"])


@router.post("/verify")
async def verify(request: Request, file: UploadFile = File(...), session: Session = Depends(get_session)):
    return verify_upload(session, await read_upload(file), ip=client_ip(request))
