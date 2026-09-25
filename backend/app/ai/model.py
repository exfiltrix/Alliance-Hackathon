"""Diagnostic model under test: torchxrayvision DenseNet121 (chest X-ray, 18 pathologies).

The model is calibrated with per-pathology operating thresholds (op_threshs), so every
output score crosses its decision threshold at 0.5.

Tensors live in the model's normalised space: shape [N, 1, 224, 224], values in
[-1024, 1024] (xrv.datasets.normalize(img, 255)). One 0-255 pixel step = 2048/255 units.
"""
from functools import lru_cache

import numpy as np
import torch
import torch.nn.functional as F
import torchxrayvision as xrv

WEIGHTS = "densenet121-res224-all"
SIZE = 224
LO, HI = -1024.0, 1024.0
PX_TO_NORM = 2048.0 / 255.0
THRESHOLD = 0.5
DEMO_PATHOLOGY = "Pneumonia"


@lru_cache(maxsize=1)
def load_model() -> torch.nn.Module:
    torch.set_num_threads(max(1, torch.get_num_threads()))
    model = xrv.models.DenseNet(weights=WEIGHTS)
    model.eval()
    for p in model.parameters():
        p.requires_grad_(False)
    return model


def pathologies() -> list[str]:
    return list(load_model().pathologies)


def pathology_index(name: str = DEMO_PATHOLOGY) -> int:
    return pathologies().index(name)


def to_unit255(px: np.ndarray) -> np.ndarray:
    """Grayscale pixels -> float32 in 0..255. 8-bit is kept as is, other depths are windowed 1..99 percentile."""
    if px.dtype == np.uint8:
        return px.astype(np.float32)
    lo, hi = np.percentile(px, [1, 99])
    if hi <= lo:
        hi = lo + 1
    return np.clip((px.astype(np.float32) - lo) * 255.0 / (hi - lo), 0, 255)


def preprocess(px: np.ndarray) -> torch.Tensor:
    """2-D grayscale image -> [1, 1, 224, 224] tensor in the model's normalised space."""
    img = to_unit255(px)
    h, w = img.shape
    side = min(h, w)
    y0, x0 = (h - side) // 2, (w - side) // 2
    img = img[y0:y0 + side, x0:x0 + side]  # XRayCenterCrop
    x = torch.from_numpy(np.ascontiguousarray(img))[None, None]
    if side != SIZE:
        x = F.interpolate(x, size=(SIZE, SIZE), mode="area" if side > SIZE else "bilinear")
    return (2 * (x / 255.0) - 1.0) * HI  # == xrv.datasets.normalize(img, 255), on a tensor


def to_uint8(x: torch.Tensor) -> np.ndarray:
    """[1, 1, H, W] normalised tensor -> H x W uint8 image (for PNG previews and saved attacks)."""
    img = (x.detach()[0, 0].cpu().numpy() - LO) * 255.0 / (HI - LO)
    return np.clip(np.round(img), 0, 255).astype(np.uint8)


def model_input(px: np.ndarray) -> np.ndarray:
    """Any grayscale image -> the 224x224 8-bit picture the model sees (attacks and fakes live at this scale)."""
    return to_uint8(preprocess(px))


def scores(x: torch.Tensor) -> torch.Tensor:
    """[N, 1, 224, 224] -> [N, n_pathologies] calibrated scores (threshold 0.5). Differentiable."""
    return load_model()(x)


@torch.no_grad()
def predict(px: np.ndarray) -> dict[str, float]:
    s = scores(preprocess(px))[0]
    return {name: round(float(v), 4) for name, v in zip(pathologies(), s)}
