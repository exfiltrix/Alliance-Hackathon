"""AI tests. Need torch + cached DenseNet weights + data/samples (python -m scripts.fetch_samples); skipped otherwise."""
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("torchxrayvision")

from app.ai import attacks, model  # noqa: E402
from app.imaging import load_image  # noqa: E402

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"
HEALTHY = ["00000001_000.png", "00027426_000.png", "1.2.276.0.7230010.3.1.4.8323329.6904.1517875201.850819.dcm"]
WEIGHTS = Path.home() / ".torchxrayvision" / "models_data"

pytestmark = [
    pytest.mark.ai,
    pytest.mark.skipif(not all((SAMPLES / f).exists() for f in HEALTHY), reason="run python -m scripts.fetch_samples"),
    pytest.mark.skipif(not WEIGHTS.exists() or not any(WEIGHTS.iterdir()), reason="DenseNet weights not cached"),
]


@pytest.fixture(scope="module", params=HEALTHY)
def healthy(request):
    return model.preprocess(load_image((SAMPLES / request.param).read_bytes()).px)


def pneumonia(x) -> float:
    with torch.no_grad():
        return float(model.scores(x)[0, model.pathology_index("Pneumonia")])


def test_preprocess_shape_and_range(healthy):
    assert healthy.shape == (1, 1, 224, 224)
    assert model.LO <= float(healthy.min()) and float(healthy.max()) <= model.HI


def test_predict_returns_all_pathologies():
    px = load_image((SAMPLES / HEALTHY[0]).read_bytes()).px
    p = model.predict(px)
    assert len(p) == 18 and "Pneumonia" in p
    assert p["Pneumonia"] < model.THRESHOLD  # sample is read as healthy


@pytest.mark.parametrize("method,eps", [("fgsm", 1.0), ("pgd", 1.0), ("pgd", 2.0)])
def test_attack_flips_prediction(healthy, method, eps):
    assert pneumonia(healthy) < model.THRESHOLD
    x_adv = attacks.ATTACKS[method](healthy, eps)
    assert pneumonia(x_adv) > model.THRESHOLD
    # noise stays inside the eps-ball and is invisible
    assert float((x_adv - healthy).abs().max()) <= eps * model.PX_TO_NORM + 1e-3
    assert attacks.psnr(healthy, x_adv) > 40


def test_attack_survives_saving_as_png(healthy):
    """The attacked image must still fool the model after 8-bit quantisation (demo uploads a PNG)."""
    x_adv = attacks.pgd(healthy, 2.0)
    reread = model.preprocess(model.to_uint8(x_adv))
    assert pneumonia(reread) > model.THRESHOLD


def test_attack_can_also_hide_disease(healthy):
    """Direction is automatic: an image scored sick is pushed back below the threshold."""
    sick = attacks.pgd(healthy, 2.0)
    assert pneumonia(sick) > model.THRESHOLD
    assert pneumonia(attacks.pgd(sick, 2.0)) < model.THRESHOLD


def test_to_uint8_round_trip(healthy):
    img = model.to_uint8(healthy)
    assert img.dtype == np.uint8 and img.shape == (224, 224)
    assert float((model.preprocess(img) - healthy).abs().max()) <= 0.5 * model.PX_TO_NORM + 1e-3
