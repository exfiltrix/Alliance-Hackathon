from fastapi import APIRouter, Depends, File, Request, UploadFile
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.audit import client_ip
from app.db import get_session
from app.routers.common import read_upload
from app.verify.service import verify_upload

router = APIRouter(tags=["verify"])


@router.post("/verify")
async def verify(request: Request, file: UploadFile = File(...), session: Session = Depends(get_session)):
    image = await read_upload(file)
    return await run_in_threadpool(verify_upload, session, image, ip=client_ip(request))
