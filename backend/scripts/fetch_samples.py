"""Download public sample chest X-rays (NIH ChestX-ray14 / RSNA, via the torchxrayvision repo) into data/samples/.

Also caches the DenseNet weights (~/.torchxrayvision) so the demo runs offline afterwards.

    .venv/bin/python -m scripts.fetch_samples
"""
import urllib.request
from pathlib import Path

BASE = "https://raw.githubusercontent.com/mlmed/torchxrayvision/master/tests/"
FILES = [
    "00000001_000.png",
    "00027426_000.png",
    "1.2.276.0.7230010.3.1.4.8323329.6904.1517875201.850819.dcm",
    "16747_3_1.jpg",
]
DEST = Path(__file__).resolve().parents[2] / "data" / "samples"


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        path = DEST / name
        if not path.exists():
            print("downloading", name)
            urllib.request.urlretrieve(BASE + name, path)
    from app.ai.model import load_model

    load_model()
    print("samples in", DEST)


if __name__ == "__main__":
    main()
