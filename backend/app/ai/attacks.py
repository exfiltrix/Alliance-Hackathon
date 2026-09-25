"""Adversarial attacks on the diagnostic model (crash test).

eps is given in 0-255 pixel units and converted with PX_TO_NORM. The attack pushes
the target pathology score across its threshold: up for an image the model calls
healthy, down for one it calls sick.
"""
import math

import torch

from app.ai.model import HI, LO, PX_TO_NORM, THRESHOLD, pathology_index, scores


def _direction(x: torch.Tensor, idx: int) -> torch.Tensor:
    """+1 where the score is below threshold (make it sick), -1 above (make it healthy). Shape [N, 1, 1, 1]."""
    with torch.no_grad():
        s = scores(x)[:, idx]
    return torch.where(s < THRESHOLD, 1.0, -1.0).view(-1, 1, 1, 1)


def _grad(x: torch.Tensor, idx: int) -> torch.Tensor:
    x = x.clone().requires_grad_(True)
    scores(x)[:, idx].sum().backward()
    return x.grad


def fgsm(x: torch.Tensor, eps_px: float, pathology: str = "Pneumonia") -> torch.Tensor:
    """One step: x + eps * sign(grad) toward the opposite diagnosis."""
    idx = pathology_index(pathology)
    eps = eps_px * PX_TO_NORM
    x_adv = x + _direction(x, idx) * eps * _grad(x, idx).sign()
    return x_adv.clamp(LO, HI).detach()


def pgd(x: torch.Tensor, eps_px: float, pathology: str = "Pneumonia", steps: int = 10) -> torch.Tensor:
    """`steps` FGSM steps of size eps/4, projected back into the L-inf eps-ball around x."""
    idx = pathology_index(pathology)
    eps = eps_px * PX_TO_NORM
    direction = _direction(x, idx)
    x_adv = x.clone()
    for _ in range(steps):
        x_adv = x_adv + direction * (eps / 4) * _grad(x_adv, idx).sign()
        x_adv = torch.max(torch.min(x_adv, x + eps), x - eps).clamp(LO, HI).detach()
    return x_adv


ATTACKS = {"fgsm": fgsm, "pgd": pgd}


def psnr(x: torch.Tensor, x_adv: torch.Tensor) -> float:
    """PSNR in 0-255 pixel units; > 40 dB is invisible to the eye."""
    mse = float(((x_adv - x) / PX_TO_NORM).pow(2).mean())
    return math.inf if mse == 0 else 20 * math.log10(255.0 / math.sqrt(mse))
