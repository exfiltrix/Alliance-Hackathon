"""Entry points the verify flow uses to call the AI modules.

Both return None while the module is not available (e.g. torch not installed),
and the API then returns `null` for that block.

run_detective -> {"probability": float 0..1, "heatmap_png": base64 str}
run_shield    -> {"attack_suspected": bool, "score": float, "threshold": float}
"""
import numpy as np


def run_detective(px: np.ndarray) -> dict | None:
    return None


def run_shield(px: np.ndarray) -> dict | None:
    return None
