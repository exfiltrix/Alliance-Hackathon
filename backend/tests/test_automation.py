"""Automation: doctor's inbox, watched folders, patient QR check."""
import pytest

from app.automation import inbox, watcher
from tests.conftest import doctor_headers, png_pixels, replace_png_pixels, xray_png


def seal(client, device, data):
    r = client.post("/api/seal", files={"file": ("x.png", data)}, headers=device["auth"])
    assert r.status_code == 200, r.text
    return r.json()


def tampered_copy(client, device, sealed_meta) -> bytes:
    sealed = client.get(sealed_meta["download_url"], headers=device["auth"]).content
    px = png_pixels(sealed).copy()
    px[100, 100] ^= 0xFF
    return replace_png_pixels(sealed, px)


@pytest.mark.parametrize("result,severity,reasons", [
    ({"status": "authentic", "shield": {"attack_suspected": False}}, "ok", []),
    ({"status": "authentic", "shield": None}, "ok", []),
    ({"status": "authentic", "shield": {"attack_suspected": True}}, "danger", ["attack_suspected"]),
    ({"status": "tampered", "shield": None}, "danger", ["tampered"]),
    ({"status": "forged", "shield": None}, "danger", ["forged"]),
    ({"status": "unsigned", "shield": None}, "warning", ["unsigned"]),
    ({"status": "authentic", "shield": None, "warning": "device_revoked_later"}, "warning", ["device_revoked_later"]),
])
def test_triage(result, severity, reasons):
    assert inbox.triage(result) == (severity, reasons)


def test_batch_upload_ranks_by_urgency(client, device):
    meta = seal(client, device, xray_png(seed=1))
    good = client.get(meta["download_url"], headers=device["auth"]).content
    files = [
        ("files", ("good.png", good)),
        ("files", ("unsigned.png", xray_png(seed=2))),
        ("files", ("tampered.png", tampered_copy(client, device, meta))),
        ("files", ("junk.png", b"not an image")),
    ]
    r = client.post("/api/inbox", files=files, headers=doctor_headers())
    assert r.status_code == 200, r.text
    got = [(i["file_name"], i["severity"], i["status"]) for i in r.json()]
    assert [s for _, s, _ in got] == ["danger", "danger", "warning", "ok"]
    assert dict((n, st) for n, _, st in got) == {
        "good.png": "authentic", "unsigned.png": "unsigned", "tampered.png": "tampered", "junk.png": "error",
    }

    listing = client.get("/api/inbox", headers=doctor_headers()).json()
    assert listing["counts"] == {"danger": 2, "warning": 1, "ok": 1, "total": 4}
    first = listing["items"][0]
    assert first["severity"] == "danger"

    detail = client.get(f"/api/inbox/{first['id']}", headers=doctor_headers()).json()
    assert "result" in detail
    assert client.post(f"/api/inbox/{first['id']}/review", headers=doctor_headers()).json()["reviewed"] is True
    listing = client.get("/api/inbox", headers=doctor_headers()).json()
    assert listing["counts"]["danger"] == 1  # reviewed items no longer count
    assert listing["items"][-1]["id"] == first["id"]  # and sink to the bottom
    assert client.get("/api/inbox/999", headers=doctor_headers()).status_code == 404


def test_folders_seal_then_verify_without_any_click(client, monkeypatch):
    monkeypatch.setattr(watcher, "SETTLE_S", 0)
    watcher.scanner_dir().mkdir(parents=True)
    (watcher.scanner_dir() / "patient1.png").write_bytes(xray_png(seed=5))
    (watcher.scanner_dir() / "broken.png").write_bytes(b"\x89PNG\r\n\x1a\nnot really")

    assert watcher.run_once() == (1, 1)  # sealed by the gateway, then verified in the inbox

    assert (watcher.scanner_dir() / "processed" / "patient1.png").exists()
    assert (watcher.scanner_dir() / "failed" / "broken.png").exists()
    assert (watcher.incoming_dir() / "processed" / "patient1.png").exists()
    items = client.get("/api/inbox", headers=doctor_headers()).json()["items"]
    assert [(i["file_name"], i["status"], i["severity"], i["source"]) for i in items] == [
        ("patient1.png", "authentic", "ok", "folder")
    ]
    assert items[0]["device"] == "Shlyuz-Auto"
    assert watcher.run_once() == (0, 0)  # nothing new

    status = client.get("/api/automation", headers=doctor_headers()).json()
    assert status["sealed"] >= 1 and status["gateway"] == "Shlyuz-Auto"


def test_patient_qr_check(client, device):
    meta = seal(client, device, xray_png(seed=7))
    token = meta["check_token"]
    assert token and str(meta["seal_id"]) != token

    info = client.get(f"/api/check/{token}").json()
    assert info["status"] == "valid" and info["hospital"] == device["hospital"] and info["device"] == "KT-01"
    assert "uid" not in info and "preview_png" not in info  # nothing about the patient or the image

    sealed = client.get(meta["download_url"], headers=device["auth"]).content
    ok = client.post(f"/api/check/{token}", files={"file": ("x.png", sealed)}).json()
    assert ok["status"] == "authentic"
    bad = client.post(f"/api/check/{token}", files={"file": ("x.png", tampered_copy(client, device, meta))}).json()
    assert bad["status"] == "tampered" and bad["changed_tiles"] == 1
    other = seal(client, device, xray_png(seed=8))
    other_file = client.get(other["download_url"], headers=device["auth"]).content
    assert client.post(f"/api/check/{token}", files={"file": ("x.png", other_file)}).json()["status"] == "mismatch"

    assert client.get("/api/check/nope").status_code == 404
    page = f"http://localhost:3000/check/{token}"
    qr = client.get(f"/api/check/{token}/qr.png", params={"url": page})
    assert qr.status_code == 200 and qr.content.startswith(b"\x89PNG")
    assert client.get(f"/api/check/{token}/qr.png", params={"url": "javascript:alert(1)"}).status_code == 422
    assert client.get(f"/api/check/{token}/qr.png", params={"url": "http://evil.com/x"}).status_code == 422
