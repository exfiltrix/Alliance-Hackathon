import base64
import io

import numpy as np
import pydicom
from PIL import Image
from sqlalchemy import update

from app import db
from app.models import Seal
from tests.conftest import png_pixels, replace_png_pixels, xray_png


def seal(client, device, data: bytes, name="img.png"):
    r = client.post("/api/seal", files={"file": (name, data)}, data={"device_id": device["id"]})
    assert r.status_code == 200, r.text
    body = r.json()
    return body, client.get(body["download_url"]).content


def verify(client, data: bytes, name="img.png"):
    r = client.post("/api/verify", files={"file": (name, data)})
    assert r.status_code == 200, r.text
    return r.json()


def test_device_never_exposes_private_key(client, device, tmp_path):
    assert set(device) == {"id", "name", "hospital", "public_key_hex", "revoked", "created_at"}
    assert len(device["public_key_hex"]) == 64
    pem = (tmp_path / "keys" / f"device_{device['id']}.pem").read_bytes()
    listed = client.get("/api/devices").text
    assert b"PRIVATE KEY" in pem and "PRIVATE" not in listed


def test_png_round_trip(client, device):
    original = xray_png()
    body, sealed = seal(client, device, original)
    assert body["tiles"] == 256 and body["tile"] == 32
    assert np.array_equal(png_pixels(sealed), png_pixels(original))  # pixels unchanged

    result = verify(client, sealed)
    assert result["status"] == "authentic"
    assert result["device"] == "KT-01" and result["changed_tiles"] == []
    assert result["note"] == "Final decision is made by the doctor."
    assert "detective" not in result
    Image.open(io.BytesIO(base64.b64decode(result["preview_png"])))  # valid PNG


def test_png_one_pixel_change(client, device):
    _, sealed = seal(client, device, xray_png())
    px = png_pixels(sealed)
    px[300, 70] ^= 1
    result = verify(client, replace_png_pixels(sealed, px))
    assert result["status"] == "tampered"
    assert result["changed_tiles"] == [[288, 64]]


def test_unsigned_png(client, device):
    result = verify(client, xray_png(seed=1))
    assert result["status"] == "unsigned"
    assert result["uid"] is None
    assert "detective" in result  # null until the AI detective is plugged in


def test_forged_ledger_row_is_rejected(client, device):
    """Attacker edits the image and rewrites the ledger row's hashes, but has no private key."""
    _, sealed = seal(client, device, xray_png())
    px = png_pixels(sealed)
    px[100:140, 100:140] = 255
    fake = replace_png_pixels(sealed, px)

    from app.seal import core, ledger

    uid = Image.open(io.BytesIO(fake)).text["medseal_uid"]
    leaves = core.tile_hashes(px, uid, 32)
    with db.SessionLocal() as s:
        s.execute(update(Seal).values(leaves_json=ledger.leaves_to_json(leaves), root_hex=core.merkle_root(leaves).hex()))
        s.commit()

    result = verify(client, fake)
    assert result["status"] == "forged"
    assert result["changed_tiles"] == []
    chain = client.get("/api/ledger/check").json()
    assert chain == {"ok": False, "entries": 1, "broken": [1]}


def test_ledger_hash_chain(client, device):
    for seed in range(3):
        seal(client, device, xray_png(seed=seed))
    assert client.get("/api/ledger/check").json() == {"ok": True, "entries": 3, "broken": []}


def test_dicom_seal_strips_patient_tags(client, device, ct_path):
    raw = open(ct_path, "rb").read()
    assert "PatientName" in pydicom.dcmread(ct_path)
    body, sealed = seal(client, device, raw, "ct.dcm")
    ds = pydicom.dcmread(io.BytesIO(sealed))
    assert "PatientName" not in ds and "PatientID" not in ds
    assert body["uid"] == str(ds.SOPInstanceUID)
    assert np.array_equal(ds.pixel_array, pydicom.dcmread(ct_path).pixel_array)

    # the original scanner file (with patient tags) verifies too: same pixels, same UID
    assert verify(client, raw, "ct.dcm")["status"] == "authentic"

    px = ds.pixel_array.copy()
    px[35, 20] += 1
    ds.PixelData = px.tobytes()
    buf = io.BytesIO()
    ds.save_as(buf)
    result = verify(client, buf.getvalue(), "ct.dcm")
    assert result["status"] == "tampered" and result["changed_tiles"] == [[32, 16]]


def test_reseal_same_image_is_idempotent(client, device):
    first, sealed = seal(client, device, xray_png())
    again, _ = seal(client, device, sealed)
    assert again["seal_id"] == first["seal_id"]

    px = png_pixels(sealed)
    px[0, 0] ^= 1
    r = client.post("/api/seal", files={"file": ("x.png", replace_png_pixels(sealed, px))}, data={"device_id": device["id"]})
    assert r.status_code == 409


def test_revoked_device(client, device):
    _, sealed = seal(client, device, xray_png())
    client.post(f"/api/devices/{device['id']}/revoke")
    result = verify(client, sealed)
    assert result["status"] == "forged" and result["reason"] == "device_revoked"
    r = client.post("/api/seal", files={"file": ("x.png", xray_png(seed=5))}, data={"device_id": device["id"]})
    assert r.status_code == 409


def test_rejects_unknown_format(client, device):
    r = client.post("/api/verify", files={"file": ("x.jpg", b"not an image")})
    assert r.status_code == 415


def test_stats(client, device):
    _, sealed = seal(client, device, xray_png())
    verify(client, sealed)
    verify(client, xray_png(seed=9))
    s = client.get("/api/stats").json()
    assert (s["sealed"], s["verified"], s["authentic"], s["unsigned"], s["tampered"]) == (1, 2, 1, 1, 0)
