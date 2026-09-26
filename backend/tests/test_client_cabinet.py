"""The client (hospital) cabinet must be strictly scoped: one organisation must never be able to
read another's devices, stats, alerts or passports (docs/API.md "Client cabinet").
"""
import pytest

from tests.conftest import admin_headers, doctor_headers, xray_png


def make_client_account(client, hospital: str) -> dict:
    r = client.post("/api/clients", json={"hospital": hospital}, headers=admin_headers())
    assert r.status_code == 201, r.text
    body = r.json()
    body["auth"] = {"Authorization": f"Bearer {body['token']}"}
    return body


def make_device(client, name: str, hospital: str) -> dict:
    r = client.post("/api/devices", json={"name": name, "hospital": hospital}, headers=admin_headers())
    assert r.status_code == 201, r.text
    body = r.json()
    body["auth"] = {"Authorization": f"Bearer {body['token']}"}
    return body


def seal(client, device: dict, seed: int) -> dict:
    r = client.post("/api/seal", files={"file": ("x.png", xray_png(seed=seed))}, headers=device["auth"])
    assert r.status_code == 200, r.text
    return r.json()


CABINET = ["/api/client/devices", "/api/client/stats", "/api/client/alerts", "/api/client/passports"]


@pytest.mark.parametrize("path", CABINET)
def test_cabinet_refuses_a_missing_token(client, path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("path", CABINET)
def test_cabinet_refuses_a_wrong_token(client, path):
    r = client.get(path, headers={"Authorization": "Bearer not-a-client-token"})
    assert r.status_code == 401


@pytest.mark.parametrize("path", CABINET)
def test_admin_token_without_org_is_rejected(client, path):
    """The admin token can inspect any hospital, but must say which one — it must never default
    to 'everything', which would defeat the whole point of per-org scoping."""
    assert client.get(path, headers=admin_headers()).status_code == 400


@pytest.mark.parametrize("path", CABINET)
def test_admin_token_with_org_is_accepted(client, path):
    r = client.get(path, params={"org": "Any Hospital"}, headers=admin_headers())
    assert r.status_code == 200


@pytest.mark.parametrize("path", CABINET)
def test_doctor_token_cannot_open_the_client_cabinet(client, path):
    """A doctor token is a different role and must not double as a client login."""
    assert client.get(path, headers=doctor_headers()).status_code == 401


def test_one_hospital_never_sees_another_devices(client):
    a = make_client_account(client, "Hospital A")
    make_device(client, "KT-A1", "Hospital A")
    make_device(client, "KT-B1", "Hospital B")

    devices = client.get("/api/client/devices", headers=a["auth"]).json()
    assert [d["name"] for d in devices] == ["KT-A1"]


def test_device_fields_report_certification_and_activity(client):
    a = make_client_account(client, "Hospital A")
    dev = make_device(client, "KT-A1", "Hospital A")
    seal(client, dev, seed=1)
    seal(client, dev, seed=2)

    [d] = client.get("/api/client/devices", headers=a["auth"]).json()
    assert d["name"] == "KT-A1" and d["revoked"] is False and d["certified"] is True
    assert d["seal_count"] == 2 and d["last_seal_at"] is not None

    client.post(f"/api/devices/{dev['id']}/revoke", headers=admin_headers())
    [d] = client.get("/api/client/devices", headers=a["auth"]).json()
    assert d["revoked"] is True


def test_stats_are_scoped_to_the_organisations_own_devices(client):
    a = make_client_account(client, "Hospital A")
    dev_a = make_device(client, "KT-A1", "Hospital A")
    dev_b = make_device(client, "KT-B1", "Hospital B")
    meta_a = seal(client, dev_a, seed=10)
    seal(client, dev_b, seed=11)

    assert client.post(
        "/api/verify", files={"file": ("x.png", client.get(meta_a["download_url"], headers=dev_a["auth"]).content)}
    ).json()["status"] == "authentic"

    stats = client.get("/api/client/stats", headers=a["auth"]).json()
    assert stats["hospital"] == "Hospital A"
    assert stats["devices"] == {"total": 1, "active": 1, "revoked": 0, "certified": 1}
    assert stats["seals"]["total"] == 1  # only Hospital A's own seal, not Hospital B's
    assert stats["verifications"]["total"] == 1
    assert stats["verifications"]["by_result"] == {"authentic": 1}


def test_alerts_show_only_this_orgs_own_flagged_images(client):
    a = make_client_account(client, "Hospital A")
    dev_a = make_device(client, "KT-A1", "Hospital A")
    meta = seal(client, dev_a, seed=20)
    sealed = client.get(meta["download_url"], headers=dev_a["auth"]).content

    from tests.conftest import png_pixels, replace_png_pixels
    px = png_pixels(sealed).copy()
    px[50, 50] ^= 0xFF
    tampered = replace_png_pixels(sealed, px)
    client.post("/api/verify", files={"file": ("x.png", tampered)})
    client.post("/api/verify", files={"file": ("x.png", sealed)})  # authentic, must not show up as an alert

    alerts = client.get("/api/client/alerts", headers=a["auth"]).json()
    assert len(alerts) == 1
    assert alerts[0]["result"] == "tampered" and alerts[0]["device"] == "KT-A1"


def test_passports_are_scoped_by_organisation_name(client):
    from tests.test_passport import add_crash_test

    a = make_client_account(client, "Hospital A")
    model_id = client.get("/api/models").json()[0]["id"]
    ct = add_crash_test(model_id)
    for org in ("Hospital A", "Hospital B"):
        r = client.post("/api/passport", json={"model_id": model_id, "crash_test_id": ct, "organisation": org},
                        headers=admin_headers())
        assert r.status_code == 201, r.text

    passports = client.get("/api/client/passports", headers=a["auth"]).json()
    assert [p["organisation"] for p in passports] == ["Hospital A"]
