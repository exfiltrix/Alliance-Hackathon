"""Paint a fake nodule on a SEALED PNG, keeping its medseal_uid chunk: the demo "spot the fake" file.

    .venv/bin/python -m scripts.tamper_demo ~/Downloads/00000001_000.png      # file downloaded from /seal

Writes <name>_tampered.png next to it. Upload it to /verify: status "tampered", red boxes
exactly on the nodule. (An image editor would drop the medseal_uid chunk and the file would
read as "unsigned" instead.) The nodule sits in the right lung field, ~4% of the image wide.
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image, PngImagePlugin


def paint_nodule(px: np.ndarray, cy: float = 0.42, cx: float = 0.30, size: float = 0.04) -> np.ndarray:
    h, w = px.shape
    hi = float(np.iinfo(px.dtype).max) if px.dtype.kind in "ui" else 255.0
    r = size * min(h, w)
    yy, xx = np.mgrid[:h, :w]
    d2 = ((yy - cy * h) ** 2 + ((xx - cx * w) / 1.15) ** 2) / r**2
    blob = np.exp(-(d2**1.5))  # soft round opacity
    grain = np.random.default_rng(0).normal(0, 0.04, px.shape)
    out = px.astype(np.float64) + 0.22 * hi * blob * (1 + grain)
    return np.clip(out, 0, hi).astype(px.dtype)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sealed_png")
    args = ap.parse_args()
    src = Path(args.sealed_png).expanduser()
    img = Image.open(src)
    if "medseal_uid" not in getattr(img, "text", {}):
        raise SystemExit("This PNG has no medseal_uid: download the sealed file from the Seal page first.")
    info = PngImagePlugin.PngInfo()
    for k, v in img.text.items():
        info.add_text(k, v)
    px = np.array(img)
    if px.ndim == 3:
        raise SystemExit("Expected a greyscale X-ray PNG.")
    out = src.with_name(f"{src.stem}_tampered.png")
    Image.fromarray(paint_nodule(px), img.mode).save(out, pnginfo=info)
    print("saved", out)


if __name__ == "__main__":
    main()
