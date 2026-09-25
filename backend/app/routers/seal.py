import json

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import audit
from app.auth import require_device
from app.automation.public_check import token_for
from app.config import settings
from app.db import get_session
from app.models import Device, Seal, iso_utc
from app.routers.common import read_upload
from app.seal import ledger
from app.seal.service import SealError, seal_upload

router = APIRouter(tags=["seal"])


def seal_json(row: Seal) -> dict:
    return {
        "seal_id": row.id,
        "uid": row.uid,
        "device_id": row.device_id,
        "tiles": len(json.loads(row.leaves_json)),
        "tile": row.tile,
        "shape": json.loads(row.shape),
        "root": row.root_hex,
        "created_at": iso_utc(row.created_at),
        "download_url": f"/api/seal/{row.id}/file",
    }


@router.post("/seal")
async def seal(
    request: Request,
    file: UploadFile = File(...),
    device: Device = Depends(require_device),
    session: Session = Depends(get_session),
):
    image = await read_upload(file)
    actor, ip = f"device:{device.name}", audit.client_ip(request)
    try:
        row, elapsed_ms = seal_upload(session, image, device.id)
    except SealError as e:
        session.rollback()
        audit.log(session, "seal", actor, target=f"uid:{image.uid or '-'}", result=f"rejected:{e.status}", ip=ip)
        session.commit()
        raise HTTPException(e.status, str(e)) from e
    audit.log(session, "seal", actor, target=f"seal:{row.id}", result="sealed" if elapsed_ms else "already_sealed", ip=ip)
    session.commit()
    return seal_json(row) | {"seal_ms": round(elapsed_ms, 2), "check_token": token_for(session, row.id)}


@router.get("/seal/{seal_id}/file")
def seal_file(seal_id: int, session: Session = Depends(get_session)):
    row = session.get(Seal, seal_id)
    if row is None or not (path := settings.storage_dir / row.file_name).exists():
        raise HTTPException(404, "Sealed file not found")
    ext = path.suffix
    media = "application/dicom" if ext == ".dcm" else "image/png"
    return FileResponse(path, media_type=media, filename=f"medseal_seal_{row.id}{ext}")


@router.get("/seals")
def list_seals(limit: int = 50, session: Session = Depends(get_session)):
    rows = session.scalars(select(Seal).order_by(Seal.id.desc()).limit(min(limit, 500)))
    return [seal_json(r) for r in rows]


@router.get("/ledger/check")
def ledger_check(session: Session = Depends(get_session)):
    """Walks the whole hash chain; lists rows that were rewritten after insertion."""
    broken = ledger.broken_entries(session)
    return {"ok": not broken, "entries": session.scalar(select(func.count(Seal.id))), "broken": broken}
