"""Download public chest X-ray sets from Hugging Face and unpack them as 8-bit PNG files.

    data/nih/normal/*.png        NIH ChestX-ray14 (adult, CC0), "No Finding"   -> crash test, shield calibration
    data/nih/findings/*.png      NIH ChestX-ray14, any finding                 -> shield calibration
    data/xray/normal/*.png       Kermany "Chest X-Ray Images (Pneumonia)" (paediatric, CC BY 4.0), 234 images
    data/xray/pneumonia/*.png    Kermany, 390 images

NIH is the main set: it is the same adult domain as the demo images. Kermany is kept for
the detective and as an out-of-domain check.

    .venv/bin/python -m scripts.fetch_dataset            # needs: pip install pyarrow
"""
import argparse
import io
import urllib.request
from pathlib import Path

from PIL import Image

HF = "https://huggingface.co/datasets/"
NIH_URL = HF + "g-ronimo/NIH-Chest-X-ray-dataset_10k/resolve/main/data/test-00000-of-00001.parquet"
KERMANY_URL = HF + "hf-vision/chest-xray-pneumonia/resolve/main/data/test-00000-of-00001.parquet"
DATA = Path(__file__).resolve().parents[2] / "data"
NIH_NO_FINDING = 0  # label index of "No Finding"


def rows(url: str, parquet: Path) -> list[dict]:
    import pyarrow.parquet as pq

    parquet.parent.mkdir(parents=True, exist_ok=True)
    if not parquet.exists():
        print("downloading", url)
        urllib.request.urlretrieve(url, parquet)
    return pq.read_table(parquet).to_pylist()


def save(image_bytes: bytes, out: Path) -> None:
    out.parent.mkdir(exist_ok=True)
    if not out.exists():
        Image.open(io.BytesIO(image_bytes)).convert("L").save(out)


def fetch_nih(n_normal: int, n_findings: int) -> None:
    counts = {"normal": 0, "findings": 0}
    limits = {"normal": n_normal, "findings": n_findings}
    for i, row in enumerate(rows(NIH_URL, DATA / "nih" / "test.parquet")):
        group = "normal" if row["labels"] == [NIH_NO_FINDING] else "findings"
        if counts[group] < limits[group]:
            save(row["image"]["bytes"], DATA / "nih" / group / f"nih_{i:04d}.png")
            counts[group] += 1
    print(counts, "->", DATA / "nih")


def fetch_kermany() -> None:
    labels = ["normal", "pneumonia"]
    counts = dict.fromkeys(labels, 0)
    for i, row in enumerate(rows(KERMANY_URL, DATA / "xray" / "test.parquet")):
        label = labels[row["label"]]
        save(row["image"]["bytes"], DATA / "xray" / label / f"{label}_{i:04d}.png")
        counts[label] += 1
    print(counts, "->", DATA / "xray")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nih-normal", type=int, default=5000, help="max images (the file has 1419)")
    ap.add_argument("--nih-findings", type=int, default=5000, help="max images (the file has 1081)")
    args = ap.parse_args()
    fetch_nih(args.nih_normal, args.nih_findings)
    fetch_kermany()


if __name__ == "__main__":
    main()
