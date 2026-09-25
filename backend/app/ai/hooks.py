"""Entry points the verify flow uses to call the AI modules.

Both return None while the module is not available (torch not installed, shield not
calibrated, MEDSEAL_AI=0), and the API then returns `null` for that block.

run_detective -> {"probability": float 0..1, "heatmap_png": base64 str}
run_shield    -> {"attack_suspected": bool, "score": float, "threshold": float}
"""
import logging

import numpy as np

from app.config import settings

log = logging.getLogger(__name__)


def run_detective(px: np.ndarray) -> dict | None:
    return None


def run_shield(px: np.ndarray) -> dict | None:
    if not settings.ai_enabled:
        return None
    try:
        from app.ai import shield
    except ImportError:
        return None
    if not shield.CALIBRATION.exists():
        log.warning("shield is not calibrated: run python -m scripts.calibrate_shield")
        return None
    try:
        return shield.check(px)
    except Exception:  # the seal verdict must not be lost because the AI block failed
        log.exception("shield failed")
        return None
