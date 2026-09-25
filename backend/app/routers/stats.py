from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import CrashTest, Seal, Verification

router = APIRouter(tags=["stats"])


@router.get("/stats")
def stats(session: Session = Depends(get_session)):
    by_result = dict(session.execute(select(Verification.result, func.count()).group_by(Verification.result)).all())
    avg = session.scalar(select(func.avg(CrashTest.robustness_score)))
    return {
        "sealed": session.scalar(select(func.count(Seal.id))),
        "verified": sum(by_result.values()),
        "authentic": by_result.get("authentic", 0),
        "tampered": by_result.get("tampered", 0),
        "unsigned": by_result.get("unsigned", 0),
        "forged": by_result.get("forged", 0),
        "models_tested": session.scalar(select(func.count(func.distinct(CrashTest.model_id)))),
        "avg_robustness": round(avg, 1) if avg is not None else None,
    }
