"""Scratch verification for the v2 hardening review — NOT part of the suite yet.

Each test encodes what the FIXED behaviour should be; right now every one of
them should FAIL against the current code, proving the finding is real.
Run: .venv/bin/pytest tests/test_hardening_v2_p0.py -v
"""
import io

import numpy as np
import pydicom
from PIL import Image

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


# P0-1, P0-2, P0-3 are fixed; their regression tests now live permanently in test_api.py.

# ---------- P0-5: DICOM display metadata is not covered by the signature ----------

def test_p0_5_rescale_intercept_change_is_detected(client, device, ct_path):
    raw = open(ct_path, "rb").read()
    body, sealed = seal(client, device, raw, "ct.dcm")

    ds = pydicom.dcmread(io.BytesIO(sealed))
    original_intercept = float(getattr(ds, "RescaleIntercept", 0))
    ds.RescaleIntercept = original_intercept + 1000  # shifts every displayed HU value by 1000
    buf = io.BytesIO()
    ds.save_as(buf, enforce_file_format=True)

    result = verify(client, buf.getvalue(), "ct.dcm")
    assert result["status"] == "tampered", (
        f"got {result['status']!r} — RescaleIntercept is not part of the signed message or any tile hash, "
        "so shifting every HU value by 1000 still verifies as authentic"
    )
