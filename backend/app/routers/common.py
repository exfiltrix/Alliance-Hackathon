from fastapi import HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.imaging import ImageError, LoadedImage, load_image


async def read_upload(file: UploadFile) -> LoadedImage:
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(413, "File is too large")
    try:
        return await run_in_threadpool(load_image, data)
    except ImageError as e:
        raise HTTPException(415, str(e)) from e
