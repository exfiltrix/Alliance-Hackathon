import pytest
import base64
import io
import json
import struct
import sys

import numpy as np
import pydicom
from PIL import Image
from sqlalchemy import update

from app import db
from app.models import Device, Seal
from tests.conftest import admin_headers, png_pixels, replace_png_pixels, xray_png


def seal(client, device, data: bytes, name="img.png"):
    r = client.post("/api/seal", files={"file": (name, data)}, headers=device["auth"])
    assert r.status_code == 200, r.text
    body = r.json()
    return body, client.get(body["download_url"], headers=device["auth"]).content


def verify(client, data: bytes, name="img.png"):
    r = client.post("/api/verify", files={"file": (name, data)})
    assert r.status_code == 200, r.text
    return r.json()


def test_seal_requires_a_device_token(client, device):
    """P0-1: sealing must not be possible with a bare device_id and no credentials."""
    r = client.post("/api/seal", files={"file": ("x.png", xray_png(seed=42))})
    assert r.status_code == 401


def test_admin_auth_rejects_non_ascii_without_500():
    from fastapi import HTTPException

    from app.auth import require_admin

    with pytest.raises(HTTPException) as exc:
        require_admin("Bearer токен")
    assert exc.value.status_code == 401


def test_revoke_is_idempotent(client, device):
    from app import db
    from app.models import Device

    first = client.post(f"/api/devices/{device['id']}/revoke", headers=admin_headers())
    assert first.status_code == 200
    with db.SessionLocal() as session:
        revoked_at = session.get(Device, device["id"]).revoked_at
    second = client.post(f"/api/devices/{device['id']}/revoke", headers=admin_headers())
    assert second.status_code == 200
    with db.SessionLocal() as session:
        assert session.get(Device, device["id"]).revoked_at == revoked_at


def test_create_device_requires_admin_token(client):
    """P0-1: anyone reaching the API must not be able to mint a trusted device."""
    assert client.post("/api/devices", json={"name": "attacker-forged-device"}).status_code == 401
    assert client.post(
        "/api/devices", json={"name": "attacker-forged-device"}, headers={"Authorization": "Bearer wrong"}
    ).status_code == 401


def test_replacing_device_key_is_untrusted(client, device):
    body, sealed = seal(client, device, xray_png(seed=22))
    with db.SessionLocal() as session:
        device_row = session.get(Device, device["id"])
        device_row.public_key_hex = "00" * 32
        session.commit()
    result = verify(client, sealed)
    assert result["status"] == "forged" and result["reason"] == "untrusted_device"


def test_uncertified_device_is_rejected_or_warned_by_migration_mode(client, device, monkeypatch):
    from app.config import settings
    from app.models import Device

    body, sealed = seal(client, device, xray_png(seed=23))
    with db.SessionLocal() as session:
        session.get(Device, device["id"]).cert_sig_hex = ""
        session.commit()
    result = verify(client, sealed)
    assert result["status"] == "forged" and result["reason"] == "untrusted_device"

    monkeypatch.setattr(settings, "require_device_cert", False)
    result = verify(client, sealed)
    assert result["status"] == "authentic" and result["warning"] == "device_not_certified"


def test_certify_devices_script_migrates_existing_seals_back_to_authentic(client, device, monkeypatch):
    """CRY-02 migration (§3.2 / Step 4.1 of the follow-up order): run the real
    `scripts.certify_devices` against an uncertified pre-existing device and confirm a seal made
    under it verifies `authentic` again afterwards, with the default `require_device_cert=True`
    unchanged -- no settings escape hatch involved, unlike the migration-mode test above."""
    from app.config import settings
    from app.models import Device
    from scripts import certify_devices

    body, sealed = seal(client, device, xray_png(seed=24))
    with db.SessionLocal() as session:
        row = session.get(Device, device["id"])
        row.cert_sig_hex = ""
        session.commit()
    assert verify(client, sealed)["status"] == "forged"  # confirms the "before migration" state

    monkeypatch.setattr(sys, "argv", ["certify_devices.py", "--authorization", f"Bearer {settings.admin_token}"])
    certify_devices.main()

    result = verify(client, sealed)
    assert result["status"] == "authentic", result
    with db.SessionLocal() as session:
        assert session.get(Device, device["id"]).cert_sig_hex


def test_v1_seal_still_verifies_with_its_original_message_format(client, device):
    """CRY-01: `sig_version` defaults to 1 for rows written before this migration, and those
    rows must keep verifying with the pre-v2 message (root + meta_hash + uid), not the new
    canonical v2 header. Builds a genuine pre-migration row with the frozen `core.seal()` (the
    same function `reference/muhr_poc.py`/pre-CRY-01 code used) instead of the current
    `signing.sign_v2()` path, so this exercises the `(row.sig_version or 1) < 2` branch in
    `verify/service.py::_check_row` that no other test reaches."""
    import uuid

    from PIL import Image as PILImage, PngImagePlugin

    from app.imaging import load_image, meta_fields, meta_hash, to_grayscale, dhash
    from app.seal import core, keys, ledger
    from app.models import Seal, utcnow

    raw = xray_png(seed=99)
    uid = str(uuid.uuid4())
    img = PILImage.open(io.BytesIO(raw))
    info = PngImagePlugin.PngInfo()
    info.add_text("medseal_uid", uid)
    buf = io.BytesIO()
    img.save(buf, "PNG", pnginfo=info)
    v1_png = buf.getvalue()

    image = load_image(v1_png)
    assert image.uid == uid
    fields = meta_fields(image, version=1)
    mh = meta_hash(fields)
    key = keys.load_private_key(device["id"])
    record = core.seal(image.px, uid, key, meta_hash=mh)

    with db.SessionLocal() as session:
        row = Seal(
            uid=uid, device_id=device["id"], created_at=utcnow(),
            shape=json.dumps(list(image.px.shape)), dtype=str(image.px.dtype), tile=record["tile"],
            leaves_json=ledger.leaves_to_json(record["leaves"]), root_hex=record["root"].hex(),
            meta_hash_hex=mh.hex(), meta_json="{}", meta_version=1, sig_version=1, patient_ref="",
            phi_warning="", dhash_hex=dhash(to_grayscale(image.px)), sig_hex=record["sig"].hex(),
            file_name="v1-fixture.png",
        )
        ledger.append(session, row)
        session.commit()
        row_id = row.id

    result = verify(client, v1_png, name="v1-fixture.png")
    assert result["status"] == "authentic", result

    # Confirm this exact row is really reaching the v1 `core.check_record` signature check (the
    # `(row.sig_version or 1) < 2` branch), not just passing by luck: corrupt the signature and
    # keep the ledger link intact (recompute entry_hash, as a real forger with a re-hash tool but
    # no private key would) so the failure can only come from that v1 branch.
    with db.SessionLocal() as session:
        tampered = session.get(Seal, row_id)
        tampered.sig_hex = "00" * 64
        tampered.entry_hash = ledger.entry_hash(tampered.prev_hash, tampered)
        session.commit()
    bad = verify(client, v1_png, name="v1-fixture.png")
    assert bad["status"] == "forged" and bad["reason"] == "bad_signature"


def test_v2_signature_binds_created_at(client, device):
    body, sealed = seal(client, device, xray_png(seed=24))
    with db.SessionLocal() as session:
        row = session.get(Seal, body["seal_id"])
        row.created_at = row.created_at.replace(year=row.created_at.year + 1)
        session.commit()
    result = verify(client, sealed)
    assert result["status"] == "forged" and result["reason"] == "bad_signature"


def test_v2_signature_binds_device_id(client, device):
    body, sealed = seal(client, device, xray_png(seed=25))
    second = client.post("/api/devices", json={"name": "other"}, headers=admin_headers()).json()
    with db.SessionLocal() as session:
        session.get(Seal, body["seal_id"]).device_id = second["id"]
        session.commit()
    result = verify(client, sealed)
    assert result["status"] == "forged" and result["reason"] == "bad_signature"


def test_patient_reference_detects_wrong_patient(client, device, ct_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "patient_salt", "stable-test-salt")
    raw = open(ct_path, "rb").read()
    body, sealed = seal(client, device, raw, "ct.dcm")
    ds = pydicom.dcmread(io.BytesIO(sealed))
    ds.PatientID = "different-patient"
    buf = io.BytesIO()
    ds.save_as(buf, enforce_file_format=True)
    result = verify(client, buf.getvalue(), "ct.dcm")
    assert result["status"] == "tampered" and result["reason"] == "patient_mismatch"
    assert result["patient_check"] == "mismatch"


def test_sealed_files_and_list_require_auth(client, device):
    body, _ = seal(client, device, xray_png(seed=12))
    assert client.get(body["download_url"]).status_code == 401
    assert client.get("/api/seals").status_code == 401
    assert client.get(body["download_url"], headers=device["auth"]).status_code == 200
    assert client.get(body["download_url"], headers=admin_headers()).status_code == 200
    assert client.get("/api/seals", headers=admin_headers()).status_code == 200


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
    assert chain == {"ok": False, "entries": 1, "broken": [1], "anchors_checked": 1, "anchor_mismatch": []}


def test_anchor_detects_rewritten_but_rechained_row(client, device):
    from app.seal import ledger

    body, _ = seal(client, device, xray_png(seed=26))
    with db.SessionLocal() as session:
        row = session.get(Seal, body["seal_id"])
        row.root_hex = "e" * 64
        row.entry_hash = ledger.entry_hash(row.prev_hash, row)
        session.commit()
    result = client.get("/api/ledger/check").json()
    assert result["ok"] is False
    assert result["anchor_mismatch"] == [body["seal_id"]]


def test_ledger_hash_chain(client, device):
    for seed in range(3):
        seal(client, device, xray_png(seed=seed))
    assert client.get("/api/ledger/check").json() == {
        "ok": True, "entries": 3, "broken": [], "anchors_checked": 3, "anchor_mismatch": []
    }


def test_concurrent_seals_keep_the_ledger_intact(client, device):
    """SEC-05: ledger.append serialises the read-head/insert race under a process-local lock
    with one retry on IntegrityError; 10 concurrent seals of different images must all succeed
    and leave an unbroken, correctly anchored hash chain."""
    from concurrent.futures import ThreadPoolExecutor

    images = [xray_png(seed=100 + i) for i in range(10)]
    with ThreadPoolExecutor(max_workers=10) as pool:
        responses = list(pool.map(lambda data: client.post(
            "/api/seal", files={"file": ("img.png", data)}, headers=device["auth"]
        ), images))

    assert all(r.status_code == 200 for r in responses), [r.text for r in responses if r.status_code != 200]
    seal_ids = [r.json()["seal_id"] for r in responses]
    assert len(set(seal_ids)) == 10  # every image got its own seal, none silently merged

    result = client.get("/api/ledger/check").json()
    assert result == {"ok": True, "entries": 10, "broken": [], "anchors_checked": 10, "anchor_mismatch": []}


def test_ai_is_not_applied_to_ct(client, device, ct_path):
    result = verify(client, open(ct_path, "rb").read(), "ct.dcm")
    assert result["status"] == "unsigned"
    assert result["ai_note"] == "not_applicable"
    assert result["shield"] is None
    assert result["detective"] is None


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


def test_v2_overlay_metadata_change_is_detected(client, device, ct_path):
    raw = open(ct_path, "rb").read()
    _, sealed = seal(client, device, raw, "ct.dcm")
    ds = pydicom.dcmread(io.BytesIO(sealed))
    ds.add_new((0x6000, 0x0010), "LO", "overlay")
    buf = io.BytesIO()
    ds.save_as(buf, enforce_file_format=True)
    result = verify(client, buf.getvalue(), "ct.dcm")
    assert result["status"] == "tampered"
    assert result["reason"] == "metadata_changed"
    assert "60000010" in result["changed_meta"]


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


def test_content_recovery_blocks_reseal_with_random_replaced_uid(client, device):
    _, sealed = seal(client, device, xray_png())
    px = png_pixels(sealed)
    px[300, 70] ^= 1
    forged = _set_png_uid(replace_png_pixels(sealed, px), "1.2.3.random-but-new")

    response = client.post("/api/seal", files={"file": ("x.png", forged)}, headers=device["auth"])
    assert response.status_code == 409


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
    assert before == {
        "ok": True, "entries": 1, "broken": [], "anchors_checked": 1, "anchor_mismatch": []
    }

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
    assert after == {
        "ok": True, "entries": 1, "broken": [], "anchors_checked": 1, "anchor_mismatch": []
    }


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


def test_png_la_alpha_only_edit_is_detected(client, device):
    rng = np.random.default_rng(8)
    rgba = rng.integers(0, 256, (256, 256, 2), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(rgba, "LA").save(buf, "PNG")
    _, sealed_bytes = seal(client, device, buf.getvalue())
    px = np.array(Image.open(io.BytesIO(sealed_bytes)))
    px[64:128, 64:128, 1] = 0
    result = verify(client, replace_png_pixels(sealed_bytes, px))
    assert result["status"] == "tampered"


def test_16_bit_colour_png_is_rejected(client, device):
    data = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">IIBBBBB", 4, 4, 16, 2, 0, 0, 0)
    response = client.post("/api/verify", files={"file": ("rgb16.png", data)})
    assert response.status_code == 415
    assert "16-bit" in response.json()["detail"]


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


def test_oversized_png_header_is_rejected_before_decode(client, device, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "max_pixels", 100)
    # Valid signature and IHDR dimensions, but no pixel payload: the loader must reject the
    # header before Pillow tries to decode or allocate the claimed image.
    data = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">IIBBBBB", 512, 512, 8, 0, 0, 0, 0)
    response = client.post("/api/verify", files={"file": ("huge.png", data)})
    assert response.status_code == 415
    assert "too large" in response.json()["detail"].lower()


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
