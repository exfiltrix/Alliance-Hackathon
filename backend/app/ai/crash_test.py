"""Crash test: attack the model on N images it reads as healthy and measure how often the diagnosis flips.

Robustness score = 10 x (1 - flip rate at eps = 1 px), rounded to 1 decimal.
"""
import time
from collections.abc import Callable
from pathlib import Path

import torch

from app.ai import attacks, model
from app.config import settings
from app.imaging import ImageError, display_pixels, load_image
from app.verify.preview import render_preview

SCORE_EPS = 1.0
BATCH = 4  # fastest on a laptop CPU; 8 and 50 measured slower with per-image early stop
IMAGE_SUFFIXES = {".png", ".dcm"}


class CrashTestError(Exception):
    pass


def image_files() -> list[Path]:
    dirs = [settings.data_dir / "nih" / "normal", settings.data_dir / "samples"]
    return [p for d in dirs if d.is_dir() for p in sorted(d.iterdir()) if p.suffix.lower() in IMAGE_SUFFIXES]


def load_healthy(n: int, pathology: str) -> tuple[torch.Tensor, list[str]]:
    """Up to n images the model scores below threshold for `pathology`, as a [k, 1, 224, 224] batch,
    plus the data folders they came from (e.g. ["nih/normal"])."""
    idx = model.pathology_index(pathology)
    picked, sources = [], set()
    for path in image_files():
        try:
            image = load_image(path.read_bytes())
            x = model.preprocess(display_pixels(image))
        except ImageError:
            continue
        with torch.no_grad():
            if float(model.scores(x)[0, idx]) < model.THRESHOLD:
                picked.append(x)
                sources.add(path.parent.relative_to(settings.data_dir).as_posix())
        if len(picked) == n:
            break
    if not picked:
        raise CrashTestError(f"No test images found in {settings.data_dir}. Run: python -m scripts.fetch_dataset")
    return torch.cat(picked), sorted(sources)


def _key(eps: float) -> str:
    return f"{eps:g}"


def run(
    n_images: int,
    eps_list: list[float],
    method: str = "pgd",
    pathology: str = model.DEMO_PATHOLOGY,
    progress: Callable[[float], None] = lambda _: None,
) -> dict:
    t0 = time.perf_counter()
    eps_list = sorted(set(eps_list) | {SCORE_EPS})
    idx = model.pathology_index(pathology)
    attack = attacks.ATTACKS[method]
    kwargs = {"stop_when_flipped": True} if method == "pgd" else {}

    x, sources = load_healthy(n_images, pathology)
    progress(0.1)

    flip_rate, psnr = {}, {}
    n_batches = -(-len(x) // BATCH)
    done, total = 0, len(eps_list) * n_batches
    for eps in eps_list:
        flips, psnrs = 0, []
        for i in range(0, len(x), BATCH):
            xb = x[i:i + BATCH]
            xa = attack(xb, eps, pathology, **kwargs)
            with torch.no_grad():
                flips += int((model.scores(xa)[:, idx] > model.THRESHOLD).sum())
            psnrs += [attacks.psnr(xb[j:j + 1], xa[j:j + 1]) for j in range(len(xb))]
            done += 1
            progress(0.1 + 0.85 * done / total)
        flip_rate[_key(eps)] = round(flips / len(x), 3)
        psnr[_key(eps)] = round(sum(psnrs) / len(psnrs), 1)

    # Showcase pair for the UI: full-strength attack (no early stop) on the first image.
    before = x[:1]
    after = attack(before, SCORE_EPS, pathology)
    with torch.no_grad():
        s_before = float(model.scores(before)[0, idx])
        s_after = float(model.scores(after)[0, idx])
    progress(1.0)

    return {
        "n_requested": n_images,
        "n_images": len(x),
        "method": method,
        "pathology": pathology,
        "data": sources,
        "eps": eps_list,
        "flip_rate": flip_rate,
        "psnr": psnr,
        "example": {
            "eps": SCORE_EPS,
            "before_png": render_preview(model.to_uint8(before)),
            "after_png": render_preview(model.to_uint8(after)),
            "before_score": round(s_before, 4),
            "after_score": round(s_after, 4),
        },
        "robustness_score": round(10 * (1 - flip_rate[_key(SCORE_EPS)]), 1),
        "duration_s": round(time.perf_counter() - t0, 1),
    }
