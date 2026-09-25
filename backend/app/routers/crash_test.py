"""Models under test and crash-test jobs.

A single dedicated worker owns CPU-heavy attack work. Request threads only validate
and enqueue, so a queued job cannot consume the AnyIO request/database thread pool.
"""
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import db
from app.auth import require_admin
from app.db import get_session
from app.models import AIModel, CrashTest, iso_utc
from app.passport.report import protocol_compliant

router = APIRouter(tags=["crash-test"])
log = logging.getLogger(__name__)

BUILTIN_MODEL = {
    "name": "torchxrayvision DenseNet121",
    "version": "densenet121-res224-all",
    "source": "https://github.com/mlmed/torchxrayvision",
    "intended_use": "Chest X-ray screening, 18 pathologies (research model, not a medical device)",
}

_jobs: dict[int, dict] = {}
_queue_lock = threading.Lock()
_job_busy = False
_executor: ThreadPoolExecutor | None = None


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="medseal-crash-test")
    return _executor


def shutdown_worker(wait: bool = True) -> None:
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=wait, cancel_futures=True)
        _executor = None


def seed_models(session: Session) -> None:
    if session.scalar(select(AIModel).where(AIModel.version == BUILTIN_MODEL["version"])) is None:
        session.add(AIModel(**BUILTIN_MODEL))
        session.commit()


def model_json(m: AIModel) -> dict:
    return {"id": m.id, "name": m.name, "version": m.version, "source": m.source, "intended_use": m.intended_use}


@router.get("/models")
def list_models(session: Session = Depends(get_session)):
    return [model_json(m) for m in session.scalars(select(AIModel).order_by(AIModel.id))]


class CrashTestIn(BaseModel):
    model_id: int
    n_images: int = Field(default=50, ge=1, le=200)
    eps: list[float] = Field(default=[0.5, 1, 2, 4], min_length=1, max_length=8)
    method: Literal["fgsm", "pgd"] = "pgd"


def _run_job(job_id: int, body: CrashTestIn) -> None:
    from app.ai import crash_test

    job = _jobs[job_id]
    job["status"] = "running"
    try:
        result = crash_test.run(
            body.n_images, body.eps, body.method, progress=lambda p: job.update(progress=round(p, 3))
        )
        with db.SessionLocal() as session:
            row = session.get(CrashTest, job_id)
            if row is not None:
                row.n_images = result["n_images"]
                row.results_json = json.dumps(result)
                row.robustness_score = result["robustness_score"]
                session.commit()
        job.update(status="done", progress=1.0)
    except Exception as e:  # report any failure to the UI instead of a job stuck in running
        log.exception("crash test %s failed", job_id)
        job.update(status="error", error=str(e))
    finally:
        global _job_busy
        with _queue_lock:
            _job_busy = False


@router.post("/crash-test", status_code=202, dependencies=[Depends(require_admin)])
def start_crash_test(body: CrashTestIn, session: Session = Depends(get_session)):
    global _job_busy
    m = session.get(AIModel, body.model_id)
    if m is None:
        raise HTTPException(404, "Model not found")
    if m.version != BUILTIN_MODEL["version"]:
        raise HTTPException(400, "Only the built-in DenseNet can be crash-tested in this demo")
    if any(not 0 < e <= 16 for e in body.eps):
        raise HTTPException(422, "eps must be in (0, 16] pixel units")
    try:
        import app.ai.crash_test  # noqa: F401
    except ImportError as e:
        raise HTTPException(503, f"AI modules are not installed: {e}") from e

    with _queue_lock:
        if _job_busy:
            raise HTTPException(409, "A crash test is already running")
        row = CrashTest(model_id=m.id, n_images=body.n_images, results_json="{}")
        session.add(row)
        session.commit()
        _job_busy = True
        _jobs[row.id] = {"status": "queued", "progress": 0.0}
    try:
        _get_executor().submit(_run_job, row.id, body)
    except Exception as e:
        with _queue_lock:
            _job_busy = False
        _jobs[row.id].update(status="error", error=str(e))
        raise HTTPException(503, "Crash-test worker is unavailable") from e
    return {"job_id": row.id}


@router.get("/crash-test/{job_id}")
def crash_test_status(job_id: int, session: Session = Depends(get_session)):
    row = session.get(CrashTest, job_id)
    if row is None:
        raise HTTPException(404, "Crash test not found")
    base = {"job_id": row.id, "model_id": row.model_id, "created_at": iso_utc(row.created_at)}
    if row.robustness_score is not None:
        data = json.loads(row.results_json)
        data.setdefault("n_requested", data.get("n_images", 0))
        return base | {"status": "done", "progress": 1.0, "protocol_compliant": protocol_compliant(data)} | data
    job = _jobs.get(job_id) or {"status": "error", "progress": 0.0, "error": "Job was interrupted (server restarted)"}
    return base | job


@router.get("/crash-tests")
def list_crash_tests(model_id: int | None = None, session: Session = Depends(get_session)):
    """Finished crash tests, newest first (without the example images)."""
    q = select(CrashTest).where(CrashTest.robustness_score.is_not(None)).order_by(CrashTest.id.desc())
    if model_id is not None:
        q = q.where(CrashTest.model_id == model_id)
    out = []
    for row in session.scalars(q):
        r = json.loads(row.results_json)
        r.pop("example", None)
        r.setdefault("n_requested", r.get("n_images", 0))
        out.append(
            {"job_id": row.id, "model_id": row.model_id, "created_at": iso_utc(row.created_at),
             "protocol_compliant": protocol_compliant(r)} | r
        )
    return out
