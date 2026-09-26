"""Doctor cabinet extras: date-range filter, pagination, volume tiles, PDF export
(docs/API.md "Inbox (doctor)")."""
from app.automation import inbox as inbox_mod
from app.db import SessionLocal
from tests.conftest import doctor_headers, xray_png


def upload(client, seed: int, name: str = "x.png"):
    r = client.post("/api/inbox", files={"files": (name, xray_png(seed=seed))}, headers=doctor_headers())
    assert r.status_code == 200, r.text
    return r.json()[0]


def test_since_and_until_filter_the_listing(client):
    upload(client, 1)
    with SessionLocal() as s:
        item = s.scalars(inbox_mod.select(inbox_mod.InboxItem)).first()
        item.received_at = item.received_at.replace(year=2000)  # force it well outside any recent window
        s.commit()

    r = client.get("/api/inbox", params={"since": "2026-01-01"}, headers=doctor_headers())
    assert r.status_code == 200 and r.json()["items"] == []

    r = client.get("/api/inbox", params={"until": "2001-01-01"}, headers=doctor_headers())
    assert len(r.json()["items"]) == 1


def test_since_rejects_a_non_date_string(client):
    assert client.get("/api/inbox", params={"since": "not-a-date"}, headers=doctor_headers()).status_code == 422


def test_offset_paginates_past_the_first_page(client):
    for i in range(3):
        upload(client, i)
    first = client.get("/api/inbox", params={"limit": 2, "offset": 0}, headers=doctor_headers()).json()["items"]
    second = client.get("/api/inbox", params={"limit": 2, "offset": 2}, headers=doctor_headers()).json()["items"]
    assert len(first) == 2 and len(second) == 1
    assert {i["id"] for i in first}.isdisjoint({i["id"] for i in second})


def test_volume_tiles_count_finished_checks_regardless_of_severity(client):
    upload(client, 1)
    upload(client, 2)
    listing = client.get("/api/inbox", headers=doctor_headers()).json()
    assert listing["volume"] == {"today": 2, "week": 2, "all": 2}


def test_single_check_pdf_is_a_pdf(client):
    item = upload(client, 5)
    r = client.get(f"/api/inbox/{item['id']}/pdf", headers=doctor_headers())
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_single_check_pdf_requires_doctor_auth(client):
    item = upload(client, 6)
    assert client.get(f"/api/inbox/{item['id']}/pdf").status_code == 401


def test_single_check_pdf_404s_for_missing_item(client):
    assert client.get("/api/inbox/999999/pdf", headers=doctor_headers()).status_code == 404


def test_batch_pdf_covers_every_requested_item(client):
    a = upload(client, 7)
    b = upload(client, 8)
    r = client.post("/api/inbox/batch-pdf", json={"ids": [a["id"], b["id"]]}, headers=doctor_headers())
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_batch_pdf_requires_doctor_auth(client):
    a = upload(client, 9)
    assert client.post("/api/inbox/batch-pdf", json={"ids": [a["id"]]}).status_code == 401


def test_batch_pdf_404s_if_any_id_is_missing(client):
    a = upload(client, 10)
    r = client.post("/api/inbox/batch-pdf", json={"ids": [a["id"], 999999]}, headers=doctor_headers())
    assert r.status_code == 404
