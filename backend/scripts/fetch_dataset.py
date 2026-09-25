"""Download the public "Chest X-Ray Images (Pneumonia)" test split (Kermany et al., CC BY 4.0)
from Hugging Face and unpack it as PNG files:

    data/xray/normal/*.png      234 images, used by the crash test and shield calibration
    data/xray/pneumonia/*.png   390 images

    .venv/bin/python -m scripts.fetch_dataset            # needs: pip install pyarrow
"""
import io
import urllib.request
from pathlib import Path

from PIL import Image

URL = "https://huggingface.co/datasets/hf-vision/chest-xray-pneumonia/resolve/main/data/test-00000-of-00001.parquet"
DATA = Path(__file__).resolve().parents[2] / "data"
LABELS = ["normal", "pneumonia"]


def main():
    import pyarrow.parquet as pq

    parquet = DATA / "xray" / "test.parquet"
    parquet.parent.mkdir(parents=True, exist_ok=True)
    if not parquet.exists():
        print("downloading", URL)
        urllib.request.urlretrieve(URL, parquet)

    table = pq.read_table(parquet).to_pylist()
    counts = dict.fromkeys(LABELS, 0)
    for i, row in enumerate(table):
        label = LABELS[row["label"]]
        out = DATA / "xray" / label / f"{label}_{i:04d}.png"
        out.parent.mkdir(exist_ok=True)
        if not out.exists():
            Image.open(io.BytesIO(row["image"]["bytes"])).convert("L").save(out)
        counts[label] += 1
    print(counts, "->", DATA / "xray")


if __name__ == "__main__":
    main()
