"""Load the AI models in the background at startup, so the first check on stage has no pause."""
import logging
import threading
import time

import numpy as np

from app.ai import hooks
from app.config import settings

log = logging.getLogger(__name__)


def _warm() -> None:
    t0 = time.perf_counter()
    dummy = np.full((256, 256), 128, np.uint8)
    shield, detective = hooks.run_shield(dummy), hooks.run_detective(dummy)  # None when unavailable
    log.info("AI warm-up: shield %s, detective %s in %.1fs",
             "ready" if shield else "off", "ready" if detective else "off", time.perf_counter() - t0)


def start() -> None:
    if settings.ai_enabled:
        threading.Thread(target=_warm, name="medseal-warmup", daemon=True).start()
