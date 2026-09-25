"""Passport: verdict rules, frozen snapshot, PDF. No torch needed: the crash test row is written directly."""
import json
import sqlite3

import pytest
from sqlalchemy import inspect

from app import db
from app.config import settings
from app.models import CrashTest
from app.passport import report

FLIP_RATE = {"0.5": 0.32, "1": 0.98, "2": 1.0, "4": 1.0}


def add_crash_test(model_id: int, score: float | None = 0.2) -> int:
    results = {
        "n_images": 50, "method": "pgd", "pathology": "Pneumonia", "data": ["nih/normal"],
        "eps": [0.5, 1, 2, 4], "flip_rate": FLIP_RATE, "psnr": dict.fromkeys(FLIP_RATE, 50.0),
        "robustness_score": score,
    }
    with db.SessionLocal() as session:
        row = CrashTest(model_id=model_id, n_images=50, results_json=json.dumps(results), robustness_score=score)
        session.add(row)
        session.commit()
        return row.id


@pytest.fixture
def model_id(client):
    return client.get("/api/models").json()[0]["id"]


@pytest.mark.parametrize("score,shield_ok,verdict", [
    (8.0, False, "allowed"),
    (7.0, True, "allowed"),
    (6.9, True, "allowed_with_conditions"),
    (0.2, True, "allowed_with_conditions"),
    (0.2, False, "not_allowed"),
])
def test_verdict_rules(score, shield_ok, verdict):
    got, conditions = report.decide(score, shield_ok)
    assert got == verdict
    assert (report.SHIELD_REQUIRED in conditions) == (verdict == "allowed_with_conditions")


def test_needs_a_finished_crash_test(client, model_id):
    assert client.post("/api/passport", json={"model_id": model_id}).status_code == 409
    assert client.post("/api/passport", json={"model_id": 999}).status_code == 404
    unfinished = add_crash_test(model_id, score=None)
    r = client.post("/api/passport", json={"model_id": model_id, "crash_test_id": unfinished})
    assert r.status_code == 409
    assert client.post("/api/passport", json={"model_id": model_id, "crash_test_id": 999}).status_code == 404


def test_issue_and_read(client, model_id, device):
    ct = add_crash_test(model_id)
    r = client.post("/api/passport", json={"model_id": model_id, "organisation": " Namangan viloyat shifoxonasi "})
    assert r.status_code == 201
    p = r.json()
    assert p["organisation"] == "Namangan viloyat shifoxonasi"
    assert p["robustness"]["crash_test_id"] == ct and p["robustness"]["score"] == 0.2
    assert p["robustness"]["formula"] == report.SCORE_FORMULA
    assert p["shield"]["compatible"] is True  # committed calibration: PGD caught at eps 1
    assert p["verdict"] == "allowed_with_conditions"
    assert p["conditions"] == ["shield_required", "seal_required", "doctor_decides"]
    assert p["pipeline"] == {"devices_active": 1, "seals": 0, "verifications": 0, "tampered_or_forged": 0,
                             "ledger_ok": True}
    assert p["note"]

    # frozen: later activity does not rewrite an issued passport
    from tests.conftest import admin_headers

    assert client.post("/api/devices", json={"name": "KT-02"}, headers=admin_headers()).status_code == 201
    assert client.get(f"/api/passport/{p['id']}").json() == p

    listed = client.get("/api/passports").json()
    assert listed[0]["id"] == p["id"] and listed[0]["robustness_score"] == 0.2
    assert client.get("/api/passport/999").status_code == 404


def test_not_allowed_without_shield(client, model_id, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "shield_calibration", tmp_path / "missing.json")
    add_crash_test(model_id)
    p = client.post("/api/passport", json={"model_id": model_id}).json()
    assert p["shield"] == {"available": False, "compatible": False}
    assert p["verdict"] == "not_allowed" and p["conditions"] == ["retest_required"]


@pytest.mark.parametrize("lang", ["uz", "ru"])
def test_pdf(client, model_id, lang):
    add_crash_test(model_id)
    pid = client.post("/api/passport", json={"model_id": model_id, "organisation": "Oʻzbekiston"}).json()["id"]
    r = client.get(f"/api/passport/{pid}/pdf", params={"lang": lang})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert f"medseal-passport-{pid}-{lang}.pdf" in r.headers["content-disposition"]
    assert r.content.startswith(b"%PDF")


def test_pdf_rejects_unknown_language(client, model_id):
    add_crash_test(model_id)
    pid = client.post("/api/passport", json={"model_id": model_id}).json()["id"]
    assert client.get(f"/api/passport/{pid}/pdf", params={"lang": "en"}).status_code == 422


def test_old_database_gets_new_columns(tmp_path):
    """A DB created before organisation/report_json existed is upgraded on startup."""
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE passports (id INTEGER PRIMARY KEY, model_id INTEGER, crash_test_id INTEGER, "
                     "verdict VARCHAR(32), conditions TEXT, created_at DATETIME)")
    engine = db.init_engine(f"sqlite:///{path}")
    try:
        cols = {c["name"] for c in inspect(engine).get_columns("passports")}
        assert {"organisation", "report_json"} <= cols
    finally:
        db.init_engine()  # rebind to the default URL for other code in this process
