import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_device, require_device_or_admin
from app.config import settings
from app.db import get_session
from app.models import Device, Seal, iso_utc
from app.routers.common import read_upload
from app.seal import anchors, ledger
from app.seal.service import SealError, seal_upload

router = APIRouter(tags=["seal"])


def seal_json(row: Seal) -> dict:
    out = {
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
    if row.phi_warning:
        out["phi_warning"] = row.phi_warning
    return out


@router.post("/seal")
async def seal(
    file: UploadFile = File(...),
    device: Device = Depends(require_device),
    session: Session = Depends(get_session),
):
    image = await read_upload(file)
    try:
        row, elapsed_ms = await run_in_threadpool(seal_upload, session, image, device.id)
    except SealError as e:
        raise HTTPException(e.status, str(e)) from e
    return seal_json(row) | {"seal_ms": round(elapsed_ms, 2)}


@router.get("/seal/{seal_id}/file", dependencies=[Depends(require_device_or_admin)])
def seal_file(seal_id: int, session: Session = Depends(get_session)):
    row = session.get(Seal, seal_id)
    if row is None or not (path := settings.storage_dir / row.file_name).exists():
        raise HTTPException(404, "Sealed file not found")
    ext = path.suffix
    media = "application/dicom" if ext == ".dcm" else "image/png"
    return FileResponse(path, media_type=media, filename=f"medseal_seal_{row.id}{ext}")


@router.get("/seals", dependencies=[Depends(require_device_or_admin)])
def list_seals(limit: int = 50, session: Session = Depends(get_session)):
    rows = session.scalars(select(Seal).order_by(Seal.id.desc()).limit(min(limit, 500)))
    return [seal_json(r) for r in rows]


@router.get("/ledger/check")
def ledger_check(session: Session = Depends(get_session)):
    """Walks the whole hash chain; lists rows that were rewritten after insertion."""
    broken = ledger.broken_entries(session)
    anchors_checked, anchor_mismatch = anchors.check_anchors(session)
    return {
        "ok": not broken and not anchor_mismatch,
        "entries": session.scalar(select(func.count(Seal.id))),
        "broken": broken,
        "anchors_checked": anchors_checked,
        "anchor_mismatch": anchor_mismatch,
    }
