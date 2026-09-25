import pytest
import base64
import io

import numpy as np
import pydicom
from PIL import Image
from sqlalchemy import update

from app import db
from app.models import Seal
from tests.conftest import admin_headers, png_pixels, replace_png_pixels, xray_png


def seal(client, device, data: bytes, name="img.png"):
    r = client.post("/api/seal", files={"file": (name, data)}, headers=device["auth"])
    assert r.status_code == 200, r.text
    body = r.json()
    return body, client.get(body["download_url"]).content


def verify(client, data: bytes, name="img.png"):
    r = client.post("/api/verify", files={"file": (name, data)})
    assert r.status_code == 200, r.text
    return r.json()


def test_seal_requires_a_device_token(client, device):
    """P0-1: sealing must not be possible with a bare device_id and no credentials."""
    r = client.post("/api/seal", files={"file": ("x.png", xray_png(seed=42))})
    assert r.status_code == 401


def test_create_device_requires_admin_token(client):
    """P0-1: anyone reaching the API must not be able to mint a trusted device."""
    assert client.post("/api/devices", json={"name": "attacker-forged-device"}).status_code == 401
    assert client.post(
        "/api/devices", json={"name": "attacker-forged-device"}, headers={"Authorization": "Bearer wrong"}
    ).status_code == 401


def test_device_never_exposes_private_key_or_token(client, device, tmp_path):
    assert set(device) - {"auth"} == {"id", "name", "hospital", "public_key_hex", "revoked", "created_at", "token"}
    assert len(device["public_key_hex"]) == 64
    assert len(device["token"]) > 20  # returned once, at creation, only
    pem = (tmp_path / "keys" / f"device_{device['id']}.pem").read_bytes()
    listed = client.get("/api/devices").text
    assert b"PRIVATE KEY" in pem
    assert "PRIVATE" not in listed
    assert device["token"] not in listed


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


def test_dicom_rescale_intercept_change_is_detected(client, device, ct_path):
    """P0-5: RescaleIntercept shifts every displayed HU value without touching a single pixel."""
    raw = open(ct_path, "rb").read()
    _, sealed = seal(client, device, raw, "ct.dcm")

    ds = pydicom.dcmread(io.BytesIO(sealed))
    ds.RescaleIntercept = float(getattr(ds, "RescaleIntercept", 0)) + 1000
    buf = io.BytesIO()
    ds.save_as(buf, enforce_file_format=True)

    result = verify(client, buf.getvalue(), "ct.dcm")
    assert result["status"] == "tampered"
    assert result["reason"] == "metadata_changed"
    assert "RescaleIntercept" in result["changed_meta"]


# ---------- P1-03: content-based recovery when the seal ID was stripped/replaced ----------

def _strip_png_uid(sealed: bytes) -> bytes:
    """Re-saves the PNG with no text chunks at all — what a re-save in an editor that drops
    metadata would produce."""
    img = Image.open(io.BytesIO(sealed))
    buf = io.BytesIO()
    Image.fromarray(np.array(img), img.mode).save(buf, "PNG")
    return buf.getvalue()


def _set_png_uid(sealed: bytes, new_uid: str) -> bytes:
    from PIL import PngImagePlugin

    img = Image.open(io.BytesIO(sealed))
    info = PngImagePlugin.PngInfo()
    info.add_text("medseal_uid", new_uid)
    buf = io.BytesIO()
    Image.fromarray(np.array(img), img.mode).save(buf, "PNG", pnginfo=info)
    return buf.getvalue()


def test_content_recovery_tampered_uid_stripped(client, device):
    _, sealed = seal(client, device, xray_png())
    px = png_pixels(sealed)
    px[300, 70] ^= 1  # same edit as test_png_one_pixel_change -> tile (288, 64)
    edited = _strip_png_uid(replace_png_pixels(sealed, px))

    result = verify(client, edited)
    assert result["status"] == "tampered"
    assert result["reason"] == "seal_id_removed"
    assert result["matched_by"] == "content"
    assert result["changed_tiles"] == [[288, 64]]


def test_content_recovery_tampered_uid_replaced(client, device):
    _, sealed = seal(client, device, xray_png())
    px = png_pixels(sealed)
    px[300, 70] ^= 1
    edited = _set_png_uid(replace_png_pixels(sealed, px), "1.2.3.4.not-a-real-seal")

    result = verify(client, edited)
    assert result["status"] == "tampered"
    assert result["reason"] == "seal_id_removed"
    assert result["matched_by"] == "content"
    assert result["changed_tiles"] == [[288, 64]]


def test_content_recovery_untouched_resave_without_chunk(client, device):
    _, sealed = seal(client, device, xray_png())
    resaved = _strip_png_uid(sealed)  # pixels identical, just no medseal_uid chunk

    result = verify(client, resaved)
    assert result["status"] == "authentic"
    assert result["warning"] == "seal_id_missing"
    assert result["matched_by"] == "content"


def test_content_recovery_does_not_false_match_unrelated_image(client, device):
    seal(client, device, xray_png(seed=0))
    unrelated = _strip_png_uid(xray_png(seed=99))  # never sealed, same shape, different content

    result = verify(client, unrelated)
    assert result["status"] == "unsigned"
    assert result["matched_by"] is None


def test_content_recovery_blocks_reseal_of_stripped_and_edited_image(client, device):
    _, sealed = seal(client, device, xray_png())
    px = png_pixels(sealed)
    px[300, 70] ^= 1
    forged = _strip_png_uid(replace_png_pixels(sealed, px))

    r = client.post("/api/seal", files={"file": ("x.png", forged)}, headers=device["auth"])
    assert r.status_code == 409


def test_content_recovery_dicom_replaced_sop_instance_uid(client, device, ct_path):
    raw = open(ct_path, "rb").read()
    _, sealed = seal(client, device, raw, "ct.dcm")

    ds = pydicom.dcmread(io.BytesIO(sealed))
    px = ds.pixel_array.copy()
    px[35, 20] += 1
    ds.PixelData = px.tobytes()
    from pydicom.uid import generate_uid

    ds.SOPInstanceUID = generate_uid()  # attacker swaps the ID after editing
    buf = io.BytesIO()
    ds.save_as(buf, enforce_file_format=True)

    result = verify(client, buf.getvalue(), "ct.dcm")
    assert result["status"] == "tampered"
    assert result["reason"] == "seal_id_removed"
    assert result["matched_by"] == "content"


def test_dhash_backfill_does_not_affect_the_ledger(client, device, tmp_path):
    """dhash_hex is a similarity index only, never part of the signed/hashed format (P1-03)."""
    from app.seal.recovery import backfill_dhash

    _, sealed = seal(client, device, xray_png())
    before = client.get("/api/ledger/check").json()
    assert before == {"ok": True, "entries": 1, "broken": []}

    with db.SessionLocal() as s:
        row = s.get(Seal, 1)
        real_dhash, row.dhash_hex = row.dhash_hex, ""
        s.commit()

        def read_file(r):
            return (tmp_path / "storage" / r.file_name).read_bytes()

        updated = backfill_dhash(s, read_file)
        assert updated == 1
        assert s.get(Seal, 1).dhash_hex == real_dhash

    after = client.get("/api/ledger/check").json()
    assert after == {"ok": True, "entries": 1, "broken": []}


def test_reseal_same_image_is_idempotent(client, device):
    first, sealed = seal(client, device, xray_png())
    again, _ = seal(client, device, sealed)
    assert again["seal_id"] == first["seal_id"]

    px = png_pixels(sealed)
    px[0, 0] ^= 1
    r = client.post("/api/seal", files={"file": ("x.png", replace_png_pixels(sealed, px))}, headers=device["auth"])
    assert r.status_code == 409


def test_revoked_device(client, device):
    """P0-2: revocation is not retroactive. A seal made before revoked_at stays trusted
    (with a warning); a NEW seal from the same (now revoked) token/device is refused outright."""
    _, sealed = seal(client, device, xray_png())
    client.post(f"/api/devices/{device['id']}/revoke", headers=admin_headers())

    result = verify(client, sealed)
    assert result["status"] == "authentic"
    assert result["warning"] == "device_revoked_later"

    r = client.post("/api/seal", files={"file": ("x.png", xray_png(seed=5))}, headers=device["auth"])
    assert r.status_code == 403  # require_device rejects a revoked device's token before sealing


def test_seal_made_after_revocation_is_forged(client, device):
    """A row whose created_at is at/after revoked_at (e.g. the key was stolen and used, then the
    theft was noticed and reported) must still be forged, unlike the case above."""
    _, sealed = seal(client, device, xray_png())
    from datetime import timedelta

    from app import db
    from app.models import Device, Seal, utcnow

    with db.SessionLocal() as s:
        # Backdate the revocation to before the seal was made, simulating a key compromised earlier.
        s.get(Device, device["id"]).revoked_at = s.get(Seal, 1).created_at - timedelta(minutes=1)
        s.get(Device, device["id"]).revoked = True
        s.commit()

    result = verify(client, sealed)
    assert result["status"] == "forged" and result["reason"] == "device_revoked"


def test_png_alpha_only_edit_is_detected(client, device):
    """P0-3: alpha carries no luminance, so this edit is luminance-invariant — catching it proves
    the seal hashes every channel, not just grayscale luminance."""
    rng = np.random.default_rng(7)
    rgba = np.zeros((256, 256, 4), np.uint8)
    rgba[..., :3] = rng.integers(0, 256, (256, 256, 3), dtype=np.uint8)
    rgba[..., 3] = 255
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, "PNG")

    _, sealed_bytes = seal(client, device, buf.getvalue())
    px = np.array(Image.open(io.BytesIO(sealed_bytes)))
    edited = px.copy()
    edited[64:128, 64:128, 3] = 0  # a region becomes fully transparent; R/G/B untouched
    fake = replace_png_pixels(sealed_bytes, edited)

    result = verify(client, fake)
    assert result["status"] == "tampered"


def test_rejects_unknown_format(client, device):
    r = client.post("/api/verify", files={"file": ("x.jpg", b"not an image")})
    assert r.status_code == 415


def test_stats(client, device):
    _, sealed = seal(client, device, xray_png())
    verify(client, sealed)
    verify(client, xray_png(seed=9))
    s = client.get("/api/stats").json()
    assert (s["sealed"], s["verified"], s["authentic"], s["unsigned"], s["tampered"]) == (1, 2, 1, 1, 0)


@pytest.mark.parametrize("origin,allowed", [
    ("http://localhost:3000", True),
    ("http://192.168.1.5:3000", True),
    ("http://10.178.233.180:3000", True),
    ("http://172.16.8.233:3000", True),
    ("http://172.32.0.1:3000", False),  # not a private range
    ("http://evil.com", False),
])
def test_cors_allows_frontend_on_any_private_ip(client, origin, allowed):
    r = client.options("/api/verify", headers={"Origin": origin, "Access-Control-Request-Method": "POST"})
    assert (r.headers.get("access-control-allow-origin") == origin) is allowed
