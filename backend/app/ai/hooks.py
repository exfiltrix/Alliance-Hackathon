"""Entry points the verify flow uses to call the AI modules.

Both return None while the module is not available (torch not installed, shield not
calibrated / detective not trained, MEDSEAL_AI=0), and the API then returns `null` for that block.

run_detective -> {"probability": float 0..1, "experimental": bool}; Grad-CAM stays in the
                  training/evaluation module and is not part of the public verification contract.
run_shield    -> {"attack_suspected": bool, "score": float, "threshold": float}
"""
import logging

import numpy as np

from app.config import settings

log = logging.getLogger(__name__)


def run_detective(px: np.ndarray) -> dict | None:
    if not settings.ai_enabled:
        return None
    try:
        from app.ai import detective
    except ImportError:
        return None
    if not settings.detective_weights.exists() or not settings.detective_metrics.exists():
        log.warning("detective is not trained: run python -m scripts.train_detective")
        return None
    try:
        result = detective.check(px)
        # Grad-CAM is useful for training evaluation, but exposing it in /verify implied a
        # second, validated forensic signal. Keep the API probability-only and experimental.
        result.pop("heatmap_png", None)
        return result
    except Exception:  # the seal verdict must not be lost because the AI block failed
        log.exception("detective failed")
        return None


def run_shield(px: np.ndarray) -> dict | None:
    if not settings.ai_enabled:
        return None
    try:
        from app.ai import shield
    except ImportError:
        return None
    if not settings.shield_calibration.exists():
        log.warning("shield is not calibrated: run python -m scripts.calibrate_shield")
        return None
    try:
        return shield.check(px)
    except Exception:  # the seal verdict must not be lost because the AI block failed
        log.exception("shield failed")
        return None
