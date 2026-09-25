"""AI detective: probability that an unsigned X-ray was edited, plus a Grad-CAM heatmap of where.

ResNet18 (ImageNet init, 1 input channel, 1 logit) trained by scripts/train_detective.py on
NIH X-rays vs synthetic forgeries (app/ai/fakes.py), on the same 224x224 8-bit picture the
diagnostic model sees. Weights: settings.detective_weights; quality on held-out images:
detective_metrics.json. The output is a probability, never a verdict.
"""
import base64
import io
import json
import threading
from functools import lru_cache

import cv2
import numpy as np
import torch
import torch.nn as nn
import torchvision
from PIL import Image

from app.ai import model
from app.config import settings

MEAN, STD = 0.449, 0.226  # ImageNet statistics, grey
EXPERIMENTAL_BELOW_AUC = 0.9  # retained for training reports; public detector is always experimental
_GRAD_CAM_LOCK = threading.Lock()


def build(pretrained: bool = False) -> nn.Module:
    weights = torchvision.models.ResNet18_Weights.IMAGENET1K_V1 if pretrained else None
    net = torchvision.models.resnet18(weights=weights)
    w = net.conv1.weight.detach().sum(dim=1, keepdim=True)  # RGB filters -> one grey channel
    net.conv1 = nn.Conv2d(1, 64, kernel_size=7, stride=2, padding=3, bias=False)
    net.conv1.weight.data.copy_(w)
    net.fc = nn.Linear(net.fc.in_features, 1)
    return net


def to_tensor(imgs: list[np.ndarray] | np.ndarray) -> torch.Tensor:
    """224x224 uint8 image(s) -> [N, 1, 224, 224] normalised batch."""
    arr = np.stack(imgs) if isinstance(imgs, list) else imgs[None]
    return (torch.from_numpy(arr).float()[:, None] / 255.0 - MEAN) / STD


@lru_cache(maxsize=1)
def load() -> nn.Module:
    net = build()
    net.load_state_dict({k: v.float() for k, v in torch.load(settings.detective_weights, map_location="cpu", weights_only=True).items()})
    net.eval()
    return net


@lru_cache(maxsize=1)
def metrics() -> dict:
    return json.loads(settings.detective_metrics.read_text())


def grad_cam(net: nn.Module, x: torch.Tensor) -> tuple[float, np.ndarray]:
    with _GRAD_CAM_LOCK:
        return _grad_cam_unlocked(net, x)


def _grad_cam_unlocked(net: nn.Module, x: torch.Tensor) -> tuple[float, np.ndarray]:
    """-> (probability of forgery, 224x224 heatmap in 0..1) for a [1, 1, 224, 224] input."""
    feats = {}
    handle = net.layer4.register_forward_hook(lambda _m, _i, out: feats.update(a=out))
    try:
        x = x.clone().requires_grad_(True)
        logit = net(x)[0, 0]
        (grads,) = torch.autograd.grad(logit, feats["a"])
    finally:
        handle.remove()
    weights = grads.mean(dim=(2, 3), keepdim=True)
    cam = torch.relu((weights * feats["a"]).sum(dim=1))[0].detach().numpy()
    cam = cv2.resize(cam, (224, 224), interpolation=cv2.INTER_CUBIC).clip(min=0)
    cam = cam / cam.max() if cam.max() > 0 else cam
    return float(torch.sigmoid(logit)), cam


def overlay_png(img: np.ndarray, cam: np.ndarray) -> str:
    """Grey X-ray with the heatmap blended on top where it is strong; base64 PNG."""
    colour = cv2.cvtColor(cv2.applyColorMap((cam * 255).astype(np.uint8), cv2.COLORMAP_JET), cv2.COLOR_BGR2RGB)
    grey = np.repeat(img[..., None], 3, axis=2).astype(np.float32)
    alpha = (np.clip((cam - 0.2) / 0.8, 0, 1) * 0.55)[..., None]
    out = (grey * (1 - alpha) + colour * alpha).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(out).resize((448, 448), Image.BICUBIC).save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def check(px: np.ndarray) -> dict:
    img = model.model_input(px)
    prob, cam = grad_cam(load(), to_tensor(img))
    return {
        "probability": round(prob, 3),
        "heatmap_png": overlay_png(img, cam),
        # The detector remains experimental until it is validated on real, non-synthetic
        # forgeries. The committed synthetic metrics (heatmap hits ≈ chance and high
        # out-of-domain false-alarm rate) are not a clinical validation result.
        "experimental": True,
    }
