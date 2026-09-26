"""Paint a fake nodule on a SEALED PNG or DICOM, keeping its seal ID: the demo "spot the fake" file.

    .venv/bin/python -m scripts.tamper_demo ~/Downloads/00000001_000.png      # file downloaded from /seal
    .venv/bin/python -m scripts.tamper_demo ~/Downloads/002cb550.dcm          # DICOM: SOPInstanceUID is kept

Writes <name>_tampered.png (or .dcm) next to it. Upload it to /verify: status "tampered", red boxes
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


def tamper_dicom(src: Path) -> None:
    """Only the pixels change; every tag (SOPInstanceUID included) stays, like an attacker with a hex editor."""
    import pydicom
    from pydicom.uid import ExplicitVRLittleEndian

    ds = pydicom.dcmread(src)
    if int(getattr(ds, "NumberOfFrames", 1) or 1) > 1:
        raise SystemExit("Expected a single-frame X-ray DICOM.")
    px = paint_nodule(ds.pixel_array)
    # Compressed sources (RSNA ships JPEG Baseline) are rewritten uncompressed: the seal hashes
    # decoded pixels, so only the painted tiles differ.
    ds.PixelData = px.tobytes()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    if "PlanarConfiguration" in ds and ds.SamplesPerPixel == 1:
        del ds.PlanarConfiguration
    out = src.with_name(f"{src.stem}_tampered.dcm")
    ds.save_as(out, enforce_file_format=True)
    print("saved", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sealed_png")
    args = ap.parse_args()
    src = Path(args.sealed_png).expanduser()
    if src.suffix.lower() == ".dcm":
        return tamper_dicom(src)
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
