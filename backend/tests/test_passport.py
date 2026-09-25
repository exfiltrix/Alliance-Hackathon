"""Passport: verdict rules, frozen snapshot, PDF. No torch needed: the crash test row is written directly."""
import json
import sqlite3

import pytest
from sqlalchemy import inspect

from app import db
from app.config import settings
from app.models import CrashTest, Passport
from app.passport import report
from tests.conftest import admin_headers

FLIP_RATE = {"0.5": 0.32, "1": 0.98, "2": 1.0, "4": 1.0}


def add_crash_test(model_id: int, score: float | None = 0.2, **overrides) -> int:
    results = {
        "n_images": 50, "method": "pgd", "pathology": "Pneumonia", "data": ["nih/normal"],
        "eps": [0.5, 1, 2, 4], "flip_rate": FLIP_RATE, "psnr": dict.fromkeys(FLIP_RATE, 50.0),
        "robustness_score": score,
    }
    results.update(overrides)
    with db.SessionLocal() as session:
        row = CrashTest(
            model_id=model_id, n_images=results["n_images"], results_json=json.dumps(results),
            robustness_score=score,
        )
        session.add(row)
        session.commit()
        return row.id


@pytest.fixture
def model_id(client):
    return client.get("/api/models").json()[0]["id"]


@pytest.mark.parametrize("score,shield_ok,validated,verdict", [
    (8.0, False, True, "allowed"),
    (7.0, True, True, "allowed"),
    (8.0, True, False, "allowed_with_conditions"),
    (6.9, True, False, "allowed_with_conditions"),
    (0.2, True, False, "allowed_with_conditions"),
    (0.2, False, False, "not_allowed"),
])
def test_verdict_rules(score, shield_ok, validated, verdict):
    validation = {"dataset": "synthetic validation", "n": 10, "auc": 0.91, "sensitivity": 0.9, "specificity": 0.9} if validated else None
    got, conditions = report.decide(score, shield_ok, validation)
    assert got == verdict
    assert (report.SHIELD_REQUIRED in conditions) == (verdict == "allowed_with_conditions")
    assert (report.CLINICAL_VALIDATION_REQUIRED in conditions) == (not validated)


def test_passport_requires_admin_token(client, model_id):
    """P1-04: issuing a passport is an admin-only, credentialed action."""
    ct = add_crash_test(model_id)
    assert client.post("/api/passport", json={"model_id": model_id, "crash_test_id": ct}).status_code == 401
    assert client.post(
        "/api/passport", json={"model_id": model_id, "crash_test_id": ct}, headers={"Authorization": "Bearer wrong"}
    ).status_code == 401


@pytest.mark.parametrize("overrides,why", [
    ({"method": "fgsm"}, "wrong method"),
    ({"n_images": 49}, "too few images"),
    ({"eps": [0.5, 2, 4]}, "eps 1 missing"),
])
def test_passport_refuses_non_compliant_crash_test(client, model_id, overrides, why):
    """P1-04: a passport may only certify against the protocol the crash test actually ran."""
    ct = add_crash_test(model_id, **overrides)
    r = client.post(
        "/api/passport", json={"model_id": model_id, "crash_test_id": ct}, headers=admin_headers()
    )
    assert r.status_code == 409, why
    assert "protocol" in r.json()["detail"].lower()


def test_needs_a_finished_crash_test(client, model_id):
    assert client.post("/api/passport", json={"model_id": model_id}, headers=admin_headers()).status_code == 409
    assert client.post("/api/passport", json={"model_id": 999}, headers=admin_headers()).status_code == 404
    unfinished = add_crash_test(model_id, score=None)
    r = client.post("/api/passport", json={"model_id": model_id, "crash_test_id": unfinished}, headers=admin_headers())
    assert r.status_code == 409
    assert client.post("/api/passport", json={"model_id": model_id, "crash_test_id": 999}, headers=admin_headers()).status_code == 404


def test_issue_and_read(client, model_id, device):
    ct = add_crash_test(model_id)
    r = client.post("/api/passport", json={"model_id": model_id, "organisation": " Namangan viloyat shifoxonasi "}, headers=admin_headers())
    assert r.status_code == 201
    p = r.json()
    assert p["organisation"] == "Namangan viloyat shifoxonasi"
    assert p["robustness"]["crash_test_id"] == ct and p["robustness"]["score"] == 0.2
    assert p["robustness"]["formula"] == report.SCORE_FORMULA
    assert p["shield"]["compatible"] is True  # AI-01: point estimate (see test below for the interval-vs-point proof)
    assert p["shield"]["confidence_intervals"]["detection_pgd_eps1"]["lower"] == 0.880555
    assert p["shield"]["confidence_intervals"]["false_positive_rate"]["upper"] == 0.022602
    assert p["shield"]["adaptive_attack_tested"] is False
    assert p["verdict"] == "allowed_with_conditions"
    assert p["conditions"] == ["clinical_validation_required", "shield_required", "seal_required", "doctor_decides"]
    assert p["clinical_validation"] is None
    assert p["pipeline"] == {"devices_active": 1, "seals": 0, "verifications": 0, "tampered_or_forged": 0,
                             "ledger_ok": True}
    assert p["note"]

    # frozen: later activity does not rewrite an issued passport
    assert client.post("/api/devices", json={"name": "KT-02"}, headers=admin_headers()).status_code == 201
    assert client.get(f"/api/passport/{p['id']}").json() == p

    listed = client.get("/api/passports").json()
    assert listed[0]["id"] == p["id"] and listed[0]["robustness_score"] == 0.2
    assert client.get("/api/passport/999").status_code == 404

    assert client.get(f"/api/passport/{p['id']}/verify").json()["valid"] is True
    with db.SessionLocal() as session:
        row = session.get(Passport, p["id"])
        row.report_json = json.dumps({**json.loads(row.report_json), "verdict": "forged"})
        session.commit()
    assert client.get(f"/api/passport/{p['id']}/verify").json()["valid"] is False


def test_shield_compatible_uses_point_estimates_not_interval_bounds(tmp_path, monkeypatch):
    """AI-01 (decided): `compatible` reads the point estimates, never the Clopper-Pearson bounds.

    Small trial counts here make the 95% interval miss the 0.9/0.02 thresholds even though the
    point estimates clear them (9/10 detected = 0.9; 2/100 false alarms = 0.02). If the rule were
    ever switched to interval bounds, `compatible` below would flip to False.
    """
    calibration = {
        "method": "median 3x3, L1 distance of DenseNet logits",
        "threshold": 10.0,
        "dataset": "synthetic test fixture",
        "n_held_out": 100,
        "false_positive_count": 2,
        "false_positive_rate": 0.02,
        "detection_rate": {
            "fgsm": {"1": {"attacks_that_fooled_model": 10, "detected_count": 9, "detected": 0.9}},
            "pgd": {"1": {"attacks_that_fooled_model": 10, "detected_count": 9, "detected": 0.9}},
        },
    }
    path = tmp_path / "shield_calibration.json"
    path.write_text(json.dumps(calibration))
    monkeypatch.setattr(settings, "shield_calibration", path)

    block = report.shield_block()

    detection_ci = block["confidence_intervals"]["detection_pgd_eps1"]
    fpr_ci = block["confidence_intervals"]["false_positive_rate"]
    assert detection_ci["lower"] < report.SHIELD_MIN_DETECTION, "fixture must make the interval miss the threshold"
    assert fpr_ci["upper"] > report.SHIELD_MAX_FALSE_ALARMS, "fixture must make the interval miss the threshold"
    assert block["compatible"] is True, "compatible must follow the 0.9/0.02 point estimates, not the CI bounds"
    assert block["adaptive_attack_tested"] is False


def test_not_allowed_without_shield(client, model_id, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "shield_calibration", tmp_path / "missing.json")
    add_crash_test(model_id)
    p = client.post("/api/passport", json={"model_id": model_id}, headers=admin_headers()).json()
    assert p["shield"] == {"available": False, "compatible": False}
    assert p["verdict"] == "not_allowed" and p["conditions"] == ["clinical_validation_required", "retest_required"]


@pytest.mark.parametrize("lang", ["uz", "ru"])
def test_pdf(client, model_id, lang):
    add_crash_test(model_id)
    pid = client.post("/api/passport", json={"model_id": model_id, "organisation": "Oʻzbekiston"}, headers=admin_headers()).json()["id"]
    r = client.get(f"/api/passport/{pid}/pdf", params={"lang": lang})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert f"medseal-passport-{pid}-{lang}.pdf" in r.headers["content-disposition"]
    assert r.content.startswith(b"%PDF")


def test_pdf_rejects_unknown_language(client, model_id):
    add_crash_test(model_id)
    pid = client.post("/api/passport", json={"model_id": model_id}, headers=admin_headers()).json()["id"]
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
