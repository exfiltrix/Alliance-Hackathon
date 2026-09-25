import io

import numpy as np
import pydicom
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydicom.data import get_testdata_file

from app.config import settings


@pytest.fixture
def client(tmp_path, monkeypatch):
    """API client with its own SQLite file, key dir and storage dir."""
    monkeypatch.setattr(settings, "db_url", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(settings, "keys_dir", tmp_path / "keys")
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "storage")
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def device(client):
    r = client.post("/api/devices", json={"name": "KT-01", "hospital": "Namangan viloyat shifoxonasi"})
    assert r.status_code == 201
    return r.json()


@pytest.fixture
def ct_path():
    return get_testdata_file("CT_small.dcm")


@pytest.fixture
def ct_dataset(ct_path):
    return pydicom.dcmread(ct_path)


def xray_png(size=512, seed=0) -> bytes:
    """Synthetic 8-bit 'X-ray' PNG (smooth gradient + noise)."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:size, 0:size]
    px = 60 + 120 * np.exp(-(((yy - size / 2) / (size / 3)) ** 2 + ((xx - size / 2) / (size / 4)) ** 2))
    px = np.clip(px + rng.normal(0, 8, px.shape), 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(px, "L").save(buf, "PNG")
    return buf.getvalue()


def png_pixels(data: bytes) -> np.ndarray:
    return np.array(Image.open(io.BytesIO(data)))


def replace_png_pixels(sealed: bytes, px: np.ndarray) -> bytes:
    """Same PNG (keeps the medseal_uid chunk) with new pixels: what an attacker's editor would produce."""
    img = Image.open(io.BytesIO(sealed))
    from PIL import PngImagePlugin

    info = PngImagePlugin.PngInfo()
    for k, v in img.text.items():
        info.add_text(k, v)
    buf = io.BytesIO()
    Image.fromarray(px, img.mode).save(buf, "PNG", pnginfo=info)
    return buf.getvalue()
