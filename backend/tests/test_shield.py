import io
import time

import pytest
from PIL import Image

from tests.test_ai import HEALTHY, SAMPLES, WEIGHTS

torch = pytest.importorskip("torch")
pytest.importorskip("torchxrayvision")

from app.ai import attacks, hooks, model, shield  # noqa: E402
from app.config import settings  # noqa: E402
from app.imaging import load_image  # noqa: E402

pytestmark = [
    pytest.mark.ai,
    pytest.mark.skipif(not (SAMPLES / HEALTHY[0]).exists() or not WEIGHTS.exists(), reason="needs samples and weights"),
]


@pytest.fixture(scope="module")
def clean_px():
    return load_image((SAMPLES / HEALTHY[0]).read_bytes()).px


@pytest.fixture(scope="module")
def attacked_png(clean_px) -> bytes:
    """What an attacker uploads: PGD eps=2 px, saved as an 8-bit PNG (same as scripts.attack_demo)."""
    x_adv = attacks.pgd(model.preprocess(clean_px), 2.0)
    buf = io.BytesIO()
    Image.fromarray(model.to_uint8(x_adv), "L").save(buf, "PNG")
    return buf.getvalue()


def test_calibration_is_committed():
    c = shield.calibration()
    assert c["threshold"] > 0 and c["false_positive_rate"] < 0.05
    assert c["detection_rate"]["pgd"]["1"]["detected"] >= 0.9


@pytest.mark.parametrize("name", HEALTHY)
def test_clean_images_pass(name):
    r = shield.check(load_image((SAMPLES / name).read_bytes()).px)
    assert r["attack_suspected"] is False, r


def test_attacked_image_is_flagged(attacked_png):
    px = load_image(attacked_png).px
    assert model.predict(px)[model.DEMO_PATHOLOGY] > model.THRESHOLD  # the attack did fool the model
    r = shield.check(px)
    assert r["attack_suspected"] is True, r
    assert r["score"] > r["threshold"]


def test_shield_is_fast(clean_px):
    shield.check(clean_px)  # model load
    t0 = time.perf_counter()
    shield.check(clean_px)
    assert time.perf_counter() - t0 < 1.0


def test_hook_respects_switch(clean_px, monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", False)
    assert hooks.run_shield(clean_px) is None
    monkeypatch.setattr(settings, "ai_enabled", True)
    assert hooks.run_shield(clean_px)["attack_suspected"] is False


def test_verify_reports_shield(client, device, attacked_png, monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", True)
    # sealing does not clean the image: the seal proves origin, the shield checks content
    seal = client.post("/api/seal", files={"file": ("a.png", attacked_png)}, headers=device["auth"]).json()
    sealed = client.get(seal["download_url"], headers=device["auth"]).content
    r = client.post("/api/verify", files={"file": ("a.png", sealed)}).json()
    assert r["status"] == "authentic"
    assert r["shield"]["attack_suspected"] is True
    assert r["analysis"] == {"status": "blocked", "reason": "attack_suspected"}  # never read an attacked image

    clean = client.post("/api/verify", files={"file": ("c.png", (SAMPLES / HEALTHY[0]).read_bytes())}).json()
    assert clean["status"] == "unsigned" and clean["shield"]["attack_suspected"] is False


def test_verify_reads_a_trusted_image(client, device, monkeypatch):
    monkeypatch.setattr(settings, "ai_enabled", True)
    seal = client.post("/api/seal", files={"file": ("c.png", (SAMPLES / HEALTHY[0]).read_bytes())}, headers=device["auth"]).json()
    sealed = client.get(seal["download_url"], headers=device["auth"]).content
    r = client.post("/api/verify", files={"file": ("c.png", sealed)}).json()
    assert r["status"] == "authentic" and r["shield"]["attack_suspected"] is False
    a = r["analysis"]
    assert a["status"] == "done" and a["experimental"] is True
    assert all(f["probability"] >= a["threshold"] for f in a["findings"])
    assert a["referrals"]
