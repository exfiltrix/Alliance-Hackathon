"""The doctor's cabinet must never be readable or writable anonymously (docs/SECURITY.md T11).

The inbox holds real medical images: GET /inbox/{id} returns the rendered preview of the study.
Before MEDSEAL_DOCTOR_TOKEN existed the whole cabinet answered 200 to anyone, and the frontend
put a link to it in the site header for every visitor.
"""
import pytest

from app.config import settings
from tests.conftest import ADMIN_TOKEN, DOCTOR_TOKEN, doctor_headers, xray_png

CABINET = [
    ("get", "/api/inbox", None),
    ("get", "/api/inbox/1", None),
    ("post", "/api/inbox/1/review", {}),
    ("get", "/api/automation", None),
    ("post", "/api/automation/run", {}),
]


@pytest.fixture
def filled_inbox(client):
    client.post("/api/inbox", files={"files": ("patient_ivanov.png", xray_png(seed=3))},
                headers=doctor_headers())
    return client.get("/api/inbox", headers=doctor_headers()).json()["items"][0]


@pytest.mark.parametrize("method,path,body", CABINET)
def test_cabinet_refuses_a_missing_token(client, method, path, body):
    assert client.request(method, path, json=body).status_code == 401


@pytest.mark.parametrize("method,path,body", CABINET)
def test_cabinet_refuses_a_wrong_token(client, method, path, body):
    headers = {"Authorization": "Bearer not-the-doctor-token"}
    assert client.request(method, path, json=body, headers=headers).status_code == 401


@pytest.mark.parametrize("method,path,body", CABINET)
def test_cabinet_accepts_the_doctor_token(client, method, path, body):
    assert client.request(method, path, json=body, headers=doctor_headers()).status_code != 401


def test_admin_token_also_opens_the_cabinet(client):
    assert client.get("/api/inbox", headers={"Authorization": f"Bearer {ADMIN_TOKEN}"}).status_code == 200


def test_cabinet_fails_closed_when_no_token_is_configured(client, monkeypatch):
    """An unconfigured deployment must not fall back to an open inbox."""
    monkeypatch.setattr(settings, "doctor_token", "")
    monkeypatch.setattr(settings, "admin_token", "")
    r = client.get("/api/inbox")
    assert r.status_code == 503
    assert "not configured" in r.json()["detail"]


def test_inbox_leaks_no_medical_image_to_an_anonymous_caller(filled_inbox, client):
    r = client.get(f"/api/inbox/{filled_inbox['id']}")
    assert r.status_code == 401
    assert b"preview_png" not in r.content


def test_anonymous_caller_cannot_clear_the_doctors_red_flags(filled_inbox, client):
    assert client.post(f"/api/inbox/{filled_inbox['id']}/review").status_code == 401
    assert client.get("/api/inbox", headers=doctor_headers()).json()["items"][0]["reviewed"] is False


def test_anonymous_caller_cannot_trigger_the_expensive_automation_pass(client):
    assert client.post("/api/automation/run").status_code == 401


def test_review_is_audited(filled_inbox, client):
    client.post(f"/api/inbox/{filled_inbox['id']}/review", headers=doctor_headers())
    rows = client.get("/api/audit?action=inbox_review", headers={"Authorization": f"Bearer {ADMIN_TOKEN}"}).json()
    assert [r["result"] for r in rows] == ["reviewed"]
    assert rows[0]["actor"] == "doctor"


def test_public_patient_check_stays_open(filled_inbox, client, device):
    """The patient's QR link is the one thing that must keep working with no credentials —
    it carries no image and no patient data (docs/API.md "Public QR check")."""
    meta = client.post("/api/seal", files={"file": ("x.png", xray_png(seed=4))},
                       headers=device["auth"]).json()
    r = client.get(f"/api/check/{meta['check_token']}")
    assert r.status_code == 200 and r.json()["hospital"] == device["hospital"]


def test_verify_stays_open_because_the_doctor_uploads_from_their_own_browser(client):
    assert client.post("/api/verify", files={"file": ("x.png", xray_png(seed=5))}).status_code == 200


def test_sealed_file_is_not_readable_by_another_device(client, device):
    """Horizontal IDOR: hospital B's gateway must not be able to walk hospital A's seal ids."""
    other = client.post("/api/devices", json={"name": "KT-02", "hospital": "Hospital B"},
                        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"}).json()
    meta = client.post("/api/seal", files={"file": ("x.png", xray_png(seed=6))},
                       headers=device["auth"]).json()
    assert client.get(meta["download_url"], headers=device["auth"]).status_code == 200  # its own
    assert client.get(meta["download_url"], headers={"Authorization": f"Bearer {other['token']}"}).status_code == 403
    # The doctor role reads the inbox, not sealed originals: a doctor token is not a device token.
    assert client.get(meta["download_url"], headers=doctor_headers()).status_code == 401
    assert client.get(meta["download_url"]).status_code == 401
    assert client.get(meta["download_url"],
                      headers={"Authorization": f"Bearer {ADMIN_TOKEN}"}).status_code == 200


def test_doctor_token_is_never_echoed_by_a_rejection(client):
    r = client.get("/api/inbox", headers={"Authorization": f"Bearer {DOCTOR_TOKEN}zzz"})
    assert DOCTOR_TOKEN not in r.text
    assert r.status_code == 401
