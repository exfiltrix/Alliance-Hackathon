"""Folder automation: nobody presses a button.

    data/watch/scanner/    the X-ray machine drops images here -> sealed by the gateway device
                           and handed on to incoming/ (as a hospital PACS would receive them)
    data/watch/incoming/   images arriving at the doctor (own scanner or another clinic)
                           -> verified automatically -> doctor's inbox, most urgent first

Processed files move to <folder>/processed/, unreadable ones to <folder>/failed/.
A background thread polls both folders every couple of seconds (no extra dependency).
"""
import logging
import shutil
import threading
import time
from pathlib import Path

from sqlalchemy import select

from app import audit, db
from app.automation import inbox
from app.automation.public_check import token_for
from app.config import settings
from app.imaging import ImageError, load_image
from app.models import Device
from app.seal import keys
from app.seal.service import SealError, seal_upload

log = logging.getLogger(__name__)
IMAGE_SUFFIXES = {".png", ".dcm"}
SETTLE_S = 1.0  # a file younger than this may still be being written

_state = {"running": False, "sealed": 0, "verified": 0, "failed": 0, "last_event": None}
_stop = threading.Event()


def scanner_dir() -> Path:
    return settings.watch_dir / "scanner"


def incoming_dir() -> Path:
    return settings.watch_dir / "incoming"


def gateway_device(session) -> Device:
    """The device that seals on behalf of the automated scanner, created on first use."""
    device = session.scalar(select(Device).where(Device.name == settings.gateway_name, Device.revoked.is_(False)))
    if device is None:
        keys.ensure_root_key()  # CRY-02: seal_upload's anchors.append_anchor also needs it, root-signed
        device = Device(name=settings.gateway_name, hospital=settings.gateway_hospital, public_key_hex="")
        session.add(device)
        session.flush()
        device.public_key_hex = keys.create_device_key(device.id)
        keys.certify_device(device)
        session.commit()
    return device


def _ready_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    now = time.time()
    return sorted(
        p for p in folder.iterdir()
        if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in IMAGE_SUFFIXES
        and now - p.stat().st_mtime >= SETTLE_S
    )


def _move(path: Path, sub: str) -> None:
    dest = path.parent / sub
    dest.mkdir(exist_ok=True)
    target = dest / path.name
    if target.exists():
        target = dest / f"{path.stem}_{int(time.time() * 1000)}{path.suffix}"
    shutil.move(str(path), target)


def _event(text: str) -> None:
    _state["last_event"] = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "text": text}
    log.info(text)


def seal_new_scans() -> int:
    """Seal every settled file in scanner/ and pass the sealed copy to incoming/."""
    done = 0
    for path in _ready_files(scanner_dir()):
        try:
            with db.SessionLocal() as session:
                image = load_image(path.read_bytes())
                row, _ = seal_upload(session, image, gateway_device(session).id)
                audit.log(session, "seal", f"device:{settings.gateway_name}", target=f"seal:{row.id}",
                          result="sealed", ip="folder")
                token_for(session, row.id)
                sealed_file = settings.storage_dir / row.file_name  # with medseal_uid / stripped DICOM tags
            incoming_dir().mkdir(parents=True, exist_ok=True)
            shutil.copyfile(sealed_file, incoming_dir() / f"{path.stem}{sealed_file.suffix}")
            _move(path, "processed")
            _state["sealed"] += 1
            done += 1
            _event(f"sealed {path.name} (seal {row.id})")
        except (ImageError, SealError) as e:
            _move(path, "failed")
            _state["failed"] += 1
            _event(f"could not seal {path.name}: {e}")
    return done


def verify_incoming() -> int:
    """Verify every settled file in incoming/ into the doctor's inbox."""
    done = 0
    for path in _ready_files(incoming_dir()):
        with db.SessionLocal() as session:
            item = inbox.process(session, path.read_bytes(), path.name, source="folder")
        _move(path, "processed")
        _state["verified"] += 1
        done += 1
        _event(f"checked {path.name}: {item.status} ({item.severity})")
    return done


def run_once() -> tuple[int, int]:
    """One pass over both folders (the loop, and tests, call this). -> (sealed, verified)"""
    return seal_new_scans(), verify_incoming()


def _loop() -> None:
    while not _stop.is_set():
        try:
            run_once()
        except Exception:  # keep watching even if one pass fails
            log.exception("watch pass failed")
        _stop.wait(settings.watch_interval_s)


def start() -> None:
    for folder in (scanner_dir(), incoming_dir()):
        folder.mkdir(parents=True, exist_ok=True)
    _stop.clear()
    threading.Thread(target=_loop, name="medseal-watcher", daemon=True).start()
    _state["running"] = True


def stop() -> None:
    _stop.set()
    _state["running"] = False


def status() -> dict:
    return {
        "watching": _state["running"],
        "scanner_dir": str(scanner_dir()),
        "incoming_dir": str(incoming_dir()),
        "interval_s": settings.watch_interval_s,
        "gateway": settings.gateway_name,
        **{k: _state[k] for k in ("sealed", "verified", "failed", "last_event")},
    }
