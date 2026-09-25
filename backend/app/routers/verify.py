from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.db import get_session
from app.routers.common import read_upload
from app.verify.service import verify_upload

router = APIRouter(tags=["verify"])


@router.post("/verify")
async def verify(file: UploadFile = File(...), session: Session = Depends(get_session)):
    return verify_upload(session, await read_upload(file))
