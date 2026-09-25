import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.db import get_session
from app.models import AIModel, CrashTest, Passport, iso_utc
from app.passport import pdf, report

router = APIRouter(tags=["passport"])


class PassportIn(BaseModel):
    model_id: int
    crash_test_id: int | None = None  # default: the model's latest finished crash test
    organisation: str = Field(default="", max_length=300)


def passport_json(p: Passport) -> dict:
    return {
        "id": p.id,
        "created_at": iso_utc(p.created_at),
        "organisation": p.organisation,
        **json.loads(p.report_json),
    }


def _get(session: Session, passport_id: int) -> Passport:
    p = session.get(Passport, passport_id)
    if p is None:
        raise HTTPException(404, "Passport not found")
    return p


@router.post("/passport", status_code=201, dependencies=[Depends(require_admin)])
def issue_passport(body: PassportIn, session: Session = Depends(get_session)):
    m = session.get(AIModel, body.model_id)
    if m is None:
        raise HTTPException(404, "Model not found")
    if body.crash_test_id is None:
        ct = session.scalar(
            select(CrashTest)
            .where(CrashTest.model_id == m.id, CrashTest.robustness_score.is_not(None))
            .order_by(CrashTest.id.desc())
        )
        if ct is None:
            raise HTTPException(409, "Run a crash test for this model first")
    else:
        ct = session.get(CrashTest, body.crash_test_id)
        if ct is None or ct.model_id != m.id:
            raise HTTPException(404, "Crash test not found for this model")
        if ct.robustness_score is None:
            raise HTTPException(409, "Crash test is not finished")

    # P1-04: only a crash test that actually ran the passport protocol may certify against it.
    ct_data = json.loads(ct.results_json)
    if not report.protocol_compliant(ct_data):
        raise HTTPException(
            409,
            "Crash test does not meet the passport protocol "
            f"(need method={report.PROTOCOL['method']!r}, n_images>={report.PROTOCOL['min_images']}, "
            f"eps includes {report.PROTOCOL['eps_required']}; got method={ct_data.get('method')!r}, "
            f"n_images={ct_data.get('n_images')}, eps={ct_data.get('eps')})",
        )

    data = report.build(session, m, ct)
    p = Passport(
        model_id=m.id,
        crash_test_id=ct.id,
        verdict=data["verdict"],
        conditions=json.dumps(data["conditions"]),
        organisation=body.organisation.strip(),
        report_json=json.dumps(data),
    )
    session.add(p)
    session.commit()
    return passport_json(p)


@router.get("/passport/{passport_id}")
def get_passport(passport_id: int, session: Session = Depends(get_session)):
    return passport_json(_get(session, passport_id))


@router.get("/passport/{passport_id}/pdf")
def passport_pdf(passport_id: int, lang: Literal["uz", "ru"] = "uz", session: Session = Depends(get_session)):
    body = pdf.render(passport_json(_get(session, passport_id)), lang)
    return Response(
        body,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="medseal-passport-{passport_id}-{lang}.pdf"'},
    )


@router.get("/passports")
def list_passports(model_id: int | None = None, session: Session = Depends(get_session)):
    """Issued passports, newest first: summary only (open one with GET /passport/{id})."""
    q = select(Passport).order_by(Passport.id.desc())
    if model_id is not None:
        q = q.where(Passport.model_id == model_id)
    out = []
    for p in session.scalars(q):
        d = passport_json(p)
        out.append({k: d[k] for k in ("id", "created_at", "organisation", "verdict", "conditions")}
                   | {"model": d["model"], "robustness_score": d["robustness"]["score"]})
    return out
