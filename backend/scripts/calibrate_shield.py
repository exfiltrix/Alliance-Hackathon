"""Calibrate the AI shield threshold and measure how well it works.

    .venv/bin/python -m scripts.calibrate_shield          # needs data/nih (python -m scripts.fetch_dataset)

Clean adult X-rays from data/nih (same domain as the demo images) are split in two halves:
  - calibration half: threshold = 99th percentile of the squeeze distance;
  - held-out half: false positive rate on clean images, and detection rate on images
    attacked with FGSM/PGD (only attacks that actually flipped the diagnosis count).
Everything goes to app/ai/shield_calibration.json (commit it; the passport reads the numbers).
"""
import argparse
import json
from datetime import datetime, timezone

import numpy as np
import torch

from app.ai import attacks, model, shield
from app.config import settings
from app.imaging import load_image

PERCENTILE = 99
EPS = [0.5, 1, 2, 4]
BATCH = 8


def load_inputs(paths) -> list[np.ndarray]:
    return [model.model_input(load_image(p.read_bytes()).px) for p in paths]


def batched_distances(imgs: list[np.ndarray]) -> np.ndarray:
    return np.concatenate([shield.distances(imgs[i:i + BATCH]) for i in range(0, len(imgs), BATCH)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-attack", type=int, default=30, help="held-out healthy images to attack")
    args = ap.parse_args()

    nih = settings.data_dir / "nih"
    files = sorted((nih / "normal").glob("*.png")) + sorted((nih / "findings").glob("*.png"))
    if not files:
        raise SystemExit(f"No images in {nih}. Run: python -m scripts.fetch_dataset")
    calib, held = files[0::2], files[1::2]

    d_calib = batched_distances(load_inputs(calib))
    threshold = round(float(np.percentile(d_calib, PERCENTILE)), 3)
    held_imgs = load_inputs(held)
    fpr = float((batched_distances(held_imgs) > threshold).mean())
    print(f"threshold {threshold} ({PERCENTILE}th pct of {len(calib)} clean), held-out FPR {fpr:.1%} on {len(held)}")

    idx = model.pathology_index()
    healthy = [img for img, p in zip(held_imgs, held) if "normal" in p.parent.name]
    healthy = [img for img in healthy if model.predict(img)[model.DEMO_PATHOLOGY] < model.THRESHOLD][: args.n_attack]
    x = torch.cat([model.preprocess(img) for img in healthy])
    detection = {}
    for method, attack in attacks.ATTACKS.items():
        detection[method] = {}
        for eps in EPS:
            adv = [model.to_uint8(attack(x[i:i + 1], eps)) for i in range(len(x))]  # uint8: as uploaded
            with torch.no_grad():
                s = model.scores(torch.cat([model.preprocess(a) for a in adv]))[:, idx]
            fooled = [a for a, v in zip(adv, s) if v > model.THRESHOLD]
            rate = round(float((batched_distances(fooled) > threshold).mean()), 3) if fooled else None
            detection[method][f"{eps:g}"] = {"attacks_that_fooled_model": len(fooled), "detected": rate}
            print(f"{method} eps={eps:g}: fooled {len(fooled)}/{len(x)}, detected {rate if rate is None else f'{rate:.0%}'}")

    settings.shield_calibration.write_text(json.dumps({
        "method": "median 3x3, L1 distance of DenseNet logits",
        "threshold": threshold,
        "percentile": PERCENTILE,
        "dataset": "NIH ChestX-ray14 (CC0), 300 px subset: No Finding + findings",
        "n_calibration": len(calib),
        "n_held_out": len(held),
        "false_positive_rate": round(fpr, 3),
        "detection_rate": detection,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }, indent=2) + "\n")
    print("saved", settings.shield_calibration)


if __name__ == "__main__":
    main()
