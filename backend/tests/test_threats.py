"""One test (or more) per threat in docs/SECURITY.md. THREAT_TESTS is the index; the first test
below fails if a threat marked ✅ in SECURITY.md has no test, or a listed test no longer exists."""
import importlib
import io
import re
import struct
import zlib
from pathlib import Path

import pydicom
import pytest
from PIL import Image, PngImagePlugin

from app import security
from app.anchor import chain as chain_mod
from app.config import BACKEND_DIR, settings
from app.main import app
from tests.conftest import admin_headers, xray_png
from tests.test_api import seal, verify

THREAT_TESTS = {
    "T1": ["test_seal_core::test_fake_nodule_is_localised"],
    "T2": ["test_seal_core::test_one_pixel_change", "test_api::test_png_one_pixel_change"],
    "T3": ["test_seal_core::test_forged_ledger_without_key_is_rejected", "test_api::test_forged_ledger_row_is_rejected",
           "test_seal_core::test_leaves_edited_but_root_kept_is_rejected"],
    "T4": ["test_api::test_ledger_hash_chain", "test_anchor::test_t4_insider_rewrites_history",
           "test_anchor::test_t4_backdated_seal", "test_anchor::test_deleting_the_proof_does_not_hide_the_seal"],
    "T5": ["test_seal_core::test_seal_bound_to_uid", "test_demo_scripts::test_tamper_demo_keeps_seal_and_is_caught"],
    "T6": ["test_threats::test_t6_replay_shows_original_date_and_device"],
    "T7": ["test_shield::test_attacked_image_is_flagged", "test_shield::test_verify_reports_shield"],
    "T8": ["test_threats::test_t8_unsigned_gets_probability_not_verdict", "test_detective::test_fake_edits_stay_in_mask"],
    "T9": ["test_api::test_revoked_device", "test_api::test_seal_made_after_revocation_is_forged"],
    "T10": ["test_threats::test_t10_oversized_upload", "test_threats::test_t10_malformed_dicom",
            "test_threats::test_t10_dicom_pixel_bomb", "test_threats::test_t10_png_decompression_bomb",
            "test_api::test_rejects_unknown_format"],
    "T11": ["test_threats::test_t11_security_headers", "test_threats::test_t11_rate_limit",
            "test_threats::test_t11_sql_injection_in_uid", "test_api::test_create_device_requires_admin_token",
            "test_api::test_seal_requires_a_device_token"],
    "T12": ["test_api::test_dicom_seal_strips_patient_tags", "test_threats::test_t12_chain_gets_only_hashes"],
}
SECURITY_MD = BACKEND_DIR.parent / "docs" / "SECURITY.md"


def test_every_threat_has_a_test():
    if not SECURITY_MD.exists():
        pytest.skip("docs/SECURITY.md not found")
    rows = re.findall(r"^\| (T\d+) \|.*\| (\S+) \|$", SECURITY_MD.read_text(), re.M)
    assert rows, "threat table not found in SECURITY.md"
    for threat, mark in rows:
        if mark == "✅":
            assert THREAT_TESTS.get(threat), f"{threat} is marked ✅ in SECURITY.md but has no test"
    for threat, tests in THREAT_TESTS.items():
        for ref in tests:
            module, name = ref.split("::")
            assert hasattr(importlib.import_module(f"tests.{module}"), name), f"{threat}: {ref} does not exist"


# --- T6: replay ---

def test_t6_replay_shows_original_date_and_device(client, device):
    body, sealed = seal(client, device, xray_png(seed=60))
    again, _ = seal(client, device, sealed)  # re-sealing the same image cannot give it a new date
    assert again["seal_id"] == body["seal_id"] and again["created_at"] == body["created_at"]
    result = verify(client, sealed)
    assert result["sealed_at"] == body["created_at"]
    assert result["device"] == device["name"]


# --- T8: unsigned image ---

def test_t8_unsigned_gets_probability_not_verdict(client):
    result = verify(client, xray_png(seed=61))
    assert result["status"] == "unsigned"
    assert "detective" in result  # a probability (null here: AI off in tests), never a certain status
    assert result["blockchain"] is None and result["note"]


# --- T10: malicious uploads ---

def test_t10_oversized_upload(client, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_bytes", 1000)
    r = client.post("/api/verify", files={"file": ("x.png", xray_png(seed=62))})
    assert r.status_code == 413


def test_t10_malformed_dicom(client):
    data = b"\0" * 128 + b"DICM" + b"\xff" * 500
    r = client.post("/api/verify", files={"file": ("x.dcm", data)})
    assert r.status_code == 415


def test_t10_dicom_pixel_bomb(client, ct_path):
    ds = pydicom.dcmread(ct_path)
    ds.Rows, ds.Columns = 20000, 20000  # header promises 400 Mpx; must be refused before decoding
    buf = io.BytesIO()
    ds.save_as(buf)
    r = client.post("/api/verify", files={"file": ("x.dcm", buf.getvalue())})
    assert r.status_code == 413


def _png_bomb(w: int, h: int) -> bytes:
    """Tiny file, huge image: w*h 8-bit zeros, zlib-compressed without ever holding them in memory."""
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))
    comp, row, out = zlib.compressobj(9), b"\0" * (w + 1), []
    for _ in range(h):
        out.append(comp.compress(row))
    out.append(comp.flush())
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", b"".join(out)) + chunk(b"IEND", b"")


def test_t10_png_decompression_bomb(client):
    data = _png_bomb(10000, 10000)  # 100 Mpx
    assert len(data) < settings.max_upload_bytes
    r = client.post("/api/verify", files={"file": ("x.png", data)})
    assert r.status_code == 413


# --- T11: web attacks ---

def test_t11_security_headers(client):
    r = client.get("/api/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["Cache-Control"] == "no-store"
    assert "Strict-Transport-Security" not in r.headers  # plain http in tests; HSTS only over https
    assert "Content-Security-Policy" not in client.get("/docs").headers  # Swagger UI keeps working


def test_t11_rate_limit(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_per_min", 3)
    security.reset_rate_limit()
    try:
        codes = [client.post("/api/verify", files={"file": ("x.png", xray_png(seed=63))}).status_code
                 for _ in range(4)]
        assert codes == [200, 200, 200, 429]
        assert client.get("/api/health").status_code == 200  # reads are not limited
    finally:
        security.reset_rate_limit()


def test_t11_sql_injection_in_uid(client, device):
    img = Image.open(io.BytesIO(xray_png(seed=64)))
    info = PngImagePlugin.PngInfo()
    info.add_text("medseal_uid", "' OR '1'='1'; DROP TABLE seals; --")
    buf = io.BytesIO()
    img.save(buf, "PNG", pnginfo=info)
    seal(client, device, xray_png(seed=65))
    assert verify(client, buf.getvalue())["status"] == "unsigned"
    assert len(client.get("/api/seals").json()) == 1  # table intact


# --- T12: patient data ---

def test_t12_chain_gets_only_hashes(client, device, chain):
    anchor_fn = next(f for f in chain_mod.ABI if f.get("name") == "anchor")
    assert [i["type"] for i in anchor_fn["inputs"]] == ["bytes32", "uint32"]  # a hash and a count, nothing else
    seal(client, device, xray_png(seed=66))
    client.post("/api/anchors/run", headers=admin_headers())
    assert len(chain.anchors) == 1 and len(chain.anchors[0].root) == 32


# --- audit log ---

def test_audit_log_records_who_did_what(client, device, chain):
    body, sealed = seal(client, device, xray_png(seed=67))
    verify(client, sealed)
    client.post("/api/devices", json={"name": "x"}, headers={"Authorization": "Bearer wrong"})
    client.post("/api/anchors/run", headers=admin_headers())
    client.post(f"/api/devices/{device['id']}/revoke", headers=admin_headers())

    assert client.get("/api/audit").status_code == 401
    events = client.get("/api/audit", headers=admin_headers()).json()
    seen = {(e["action"], e["actor"], e["result"]) for e in events}
    assert ("device_create", "admin", "KT-01") in seen
    assert ("seal", "device:KT-01", "sealed") in seen
    assert ("verify", "anonymous", "authentic") in seen
    assert ("auth_failed", "admin?", "401") in seen
    assert ("anchor", "admin", "1 seals, block 100") in seen
    assert ("device_revoke", "admin", "KT-01") in seen
    assert all(e["at"].endswith("Z") for e in events)


def test_audit_log_cannot_be_changed_via_api():
    methods = {m for r in app.routes if getattr(r, "path", "").startswith("/api/audit") for m in r.methods}
    assert methods <= {"GET", "HEAD"}
