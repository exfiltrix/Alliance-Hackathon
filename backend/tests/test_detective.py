import base64
import io

import numpy as np
import pytest
from PIL import Image

from tests.test_ai import HEALTHY, SAMPLES

cv2 = pytest.importorskip("cv2")
torch = pytest.importorskip("torch")
pytest.importorskip("torchxrayvision")

from app.ai import detective, fakes, hooks, model  # noqa: E402
from app.config import settings  # noqa: E402
from app.imaging import load_image  # noqa: E402


@pytest.fixture(scope="module")
def xray():
    """224x224 model-input picture of a real adult chest X-ray."""
    if not (SAMPLES / HEALTHY[0]).exists():
        pytest.skip("run python -m scripts.fetch_samples")
    return model.model_input(load_image((SAMPLES / HEALTHY[0]).read_bytes()).px)


@pytest.mark.parametrize("kind", fakes.KINDS)
def test_fake_edits_stay_in_mask(xray, kind):
    donor = model.model_input(load_image((SAMPLES / HEALTHY[1]).read_bytes()).px)
    fake, mask, got = fakes.make_fake(xray, np.random.default_rng(0), donor, kind)
    assert got == kind and fake.shape == xray.shape and fake.dtype == np.uint8
    diff = np.abs(fake.astype(int) - xray.astype(int))
    assert diff.sum() > 0 and mask.sum() > 0
    near = cv2.dilate(mask, np.ones((9, 9), np.uint8)).astype(bool)
    assert diff[near].sum() >= 0.9 * diff.sum()  # the mask really marks the edit


@pytest.mark.ai
@pytest.mark.skipif(not settings.detective_weights.exists(), reason="run python -m scripts.train_detective")
class TestTrained:
    def test_check_shape(self, xray):
        r = detective.check(xray)
        assert 0 <= r["probability"] <= 1
        assert isinstance(r["experimental"], bool)
        png = Image.open(io.BytesIO(base64.b64decode(r["heatmap_png"])))
        assert png.size == (448, 448) and png.mode == "RGB"

    def test_forgeries_score_higher_than_originals(self, xray):
        rng = np.random.default_rng(7)
        donor = model.model_input(load_image((SAMPLES / HEALTHY[1]).read_bytes()).px)
        p_real = detective.check(xray)["probability"]
        p_fakes = [detective.check(fakes.make_fake(xray, rng, donor, k)[0])["probability"] for k in fakes.KINDS * 2]
        assert np.mean(p_fakes) > p_real + 0.3, (p_real, p_fakes)

    def test_metrics_are_committed(self):
        m = detective.metrics()["test"]
        assert m["forgeries"] > 0 and 0.5 < m["auc"] <= 1

    def test_verify_runs_detective_only_on_unsigned(self, client, device, monkeypatch):
        monkeypatch.setattr(settings, "ai_enabled", True)
        png = (SAMPLES / HEALTHY[0]).read_bytes()
        r = client.post("/api/verify", files={"file": ("x.png", png)}).json()
        assert r["status"] == "unsigned" and 0 <= r["detective"]["probability"] <= 1
        seal = client.post("/api/seal", files={"file": ("x.png", png)}, headers=device["auth"]).json()
        sealed = client.get(seal["download_url"], headers=device["auth"]).content
        r = client.post("/api/verify", files={"file": ("x.png", sealed)}).json()
        assert r["status"] == "authentic" and "detective" not in r

    def test_hook_respects_switch(self, xray, monkeypatch):
        monkeypatch.setattr(settings, "ai_enabled", False)
        assert hooks.run_detective(xray) is None

    def test_grad_cam_is_thread_safe(self, xray):
        """SEC-04: grad_cam registers a forward hook on the shared net; _GRAD_CAM_LOCK must
        serialise concurrent callers so two requests never see each other's hook/activation."""
        import threading

        net = detective.load()
        x = detective.to_tensor(xray)
        expected_prob, expected_cam = detective.grad_cam(net, x)

        results: list[tuple[float, np.ndarray]] = [None, None]  # type: ignore[list-item]
        errors: list[Exception] = []

        def call(i: int) -> None:
            try:
                results[i] = detective.grad_cam(net, x)
            except Exception as e:  # pragma: no cover - surfaced via errors list
                errors.append(e)

        threads = [threading.Thread(target=call, args=(i,)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, errors
        for prob, cam in results:
            assert prob == pytest.approx(expected_prob)
            assert np.allclose(cam, expected_cam)
