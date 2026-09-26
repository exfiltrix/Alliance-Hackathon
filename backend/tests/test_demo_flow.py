"""docs/DEMO.md steps 1, 2 and 3b end to end, with the real demo scripts run as on stage.
If this fails, the live demo is broken. (Step 3 and the passport: test_ai, test_shield, test_passport.)"""
import os
import re
import subprocess
import sys

import pytest

from app.config import BACKEND_DIR, settings
from tests.conftest import admin_headers, doctor_headers, xray_png

DICTIONARY = BACKEND_DIR.parent / "by_billy" / "frontend" / "src" / "lib" / "dictionary.ts"
# Every `reason` /verify can return with status "forged" (docs/API.md).
FORGED_REASONS = {
    "ledger_entry_modified", "bad_signature", "device_revoked", "unknown_device", "untrusted_device",
    "blockchain_mismatch",
}


def run_script(*args, tmp_path):
    env = os.environ | {"MEDSEAL_DB_URL": settings.db_url, "MEDSEAL_KEYS_DIR": str(settings.keys_dir)}
    out = subprocess.run([sys.executable, "-m", *args], cwd=BACKEND_DIR, env=env, check=True,
                         capture_output=True, text=True)
    return out.stdout


def test_demo_flow(client, device, chain, tmp_path):
    verify = lambda path: client.post("/api/verify", files={"file": ("x.png", path.read_bytes())}).json()

    # 1. Seal
    body = client.post("/api/seal", files={"file": ("xray.png", xray_png(seed=90))}, headers=device["auth"]).json()
    original = tmp_path / "xray.png"
    original.write_bytes(client.get(body["download_url"], headers=device["auth"]).content)

    # 2. Spot the fake
    run_script("scripts.tamper_demo", str(original), tmp_path=tmp_path)
    fake = tmp_path / "xray_tampered.png"
    r = verify(fake)
    assert r["status"] == "tampered" and r["changed_tiles"] and r["note"]
    assert verify(original)["status"] == "authentic"

    # 3b. Even we can't cheat
    assert client.post("/api/anchors/run", headers=admin_headers()).json()["anchored"] == 1
    assert verify(original)["blockchain"]["status"] == "anchored"
    out = run_script("scripts.rewrite_history_demo", str(body["seal_id"]), "--image", str(fake), tmp_path=tmp_path)
    assert "clean" in out  # the in-database hash chain repairs cleanly, by itself
    ledger_check = client.get("/api/ledger/check").json()
    # CRY-03: the local, root-signed external anchor file still remembers the original entry_hash
    # for this row, so the full ledger check (unlike the bare DB chain above) is not fooled even
    # before the blockchain is consulted — an insider without the root key cannot repair it.
    assert not ledger_check["ok"] and body["seal_id"] in ledger_check["anchor_mismatch"]
    r = verify(fake)
    assert (r["status"], r["reason"]) == ("forged", "blockchain_mismatch")  # /verify only consults the chain
    assert client.get(f"/api/check/{body['check_token']}").json()["reason"] == "blockchain_mismatch"  # patient QR too

    inbox = client.post("/api/inbox", files=[("files", ("fake.png", fake.read_bytes()))],
                        headers=doctor_headers()).json()
    assert inbox[0]["severity"] == "danger"


def test_tamper_demo_on_dicom_shows_the_fake(client, device, ct_path, tmp_path):
    """Step 2 with a DICOM: the painted nodule keeps SOPInstanceUID, so /verify boxes exactly those tiles."""
    verify = lambda path: client.post("/api/verify", files={"file": ("x.dcm", path.read_bytes())}).json()
    body = client.post("/api/seal", files={"file": ("ct.dcm", open(ct_path, "rb").read())}, headers=device["auth"]).json()
    original = tmp_path / "ct.dcm"
    original.write_bytes(client.get(body["download_url"], headers=device["auth"]).content)

    run_script("scripts.tamper_demo", str(original), tmp_path=tmp_path)
    r = verify(tmp_path / "ct_tampered.dcm")
    assert r["status"] == "tampered" and r.get("reason") is None
    assert 0 < len(r["changed_tiles"]) < 64  # the nodule only, not the whole 128x128 image (64 tiles)
    assert verify(original)["status"] == "authentic"


def test_frontend_has_text_for_every_forged_reason():
    """The verify page renders t(d.forgedReasons[reason]): a reason without text crashes it."""
    if not DICTIONARY.exists():
        pytest.skip("frontend not checked out")
    src = DICTIONARY.read_text()
    block = src[src.index("forgedReasons:"):]
    block = block[:block.index("\n    },")]
    keys = set(re.findall(r"^\s{6}(\w+): \{", block, re.M))
    assert FORGED_REASONS <= keys, f"missing in dictionary.ts forgedReasons: {FORGED_REASONS - keys}"
