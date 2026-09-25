import subprocess
import sys

from tests.conftest import xray_png


def test_tamper_demo_keeps_seal_and_is_caught(client, device, tmp_path):
    seal = client.post("/api/seal", files={"file": ("x.png", xray_png())}, headers=device["auth"]).json()
    sealed = tmp_path / "x.png"
    sealed.write_bytes(client.get(seal["download_url"], headers=device["auth"]).content)

    subprocess.run([sys.executable, "-m", "scripts.tamper_demo", str(sealed)], check=True, capture_output=True)

    r = client.post("/api/verify", files={"file": ("t.png", (tmp_path / "x_tampered.png").read_bytes())}).json()
    assert r["status"] == "tampered" and r["seal_id"] == seal["seal_id"]
    assert 0 < len(r["changed_tiles"]) < 20  # a local edit, not the whole image
