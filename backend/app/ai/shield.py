"""AI shield: feature squeezing (Xu et al., 2018) in front of the diagnostic model.

Adversarial noise is fragile: a 3x3 median filter wipes most of it out, so the model's
answer on an attacked image jumps after filtering, while on a clean image it barely moves.

    score = sum over pathologies |logit(image) - logit(median3x3(image))|

Raw logits, not the op_threshs-calibrated scores: calibration stretches small changes
near each threshold, which makes clean images look as unstable as attacked ones.
The threshold is the 99th percentile of the score on clean X-rays
(scripts/calibrate_shield.py -> shield_calibration.json), so ~1% of clean images are flagged
(95th gave 8% false alarms on held-out images; PGD at eps >= 1 px is still caught 100%).
"""
import json
from functools import lru_cache

import numpy as np
import torch
from PIL import Image, ImageFilter

from app.ai import model
from app.config import settings


def squeeze(img: np.ndarray) -> np.ndarray:
    return np.array(Image.fromarray(img).filter(ImageFilter.MedianFilter(3)))


@torch.no_grad()
def distances(imgs: list[np.ndarray]) -> np.ndarray:
    """224x224 uint8 model-input images -> squeeze distance per image."""
    x = torch.cat([model.preprocess(v) for img in imgs for v in (img, squeeze(img))])
    m = model.load_model()
    logits = m.classifier(m.features2(x))
    return (logits[0::2] - logits[1::2]).abs().sum(dim=1).numpy()


@lru_cache(maxsize=1)
def calibration() -> dict:
    return json.loads(settings.shield_calibration.read_text())


def check(px: np.ndarray) -> dict:
    score = float(distances([model.model_input(px)])[0])
    threshold = calibration()["threshold"]
    return {"attack_suspected": score > threshold, "score": round(score, 3), "threshold": threshold}
