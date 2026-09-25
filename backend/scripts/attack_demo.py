"""Attack one X-ray and save the before/after pair for the demo.

    .venv/bin/python -m scripts.attack_demo ../data/samples/00000001_000.png --eps 2 --method pgd

Writes <out>/<name>_before.png and <name>_attacked.png (224x224, 8-bit). The attacked
PNG still fools the model after being re-read, so it can be uploaded to /verify to
demo the shield.
"""
import argparse
from pathlib import Path

from PIL import Image

from app.ai import attacks, model
from app.imaging import load_image


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--eps", type=float, default=2.0, help="attack strength in 0-255 pixel units")
    ap.add_argument("--method", choices=attacks.ATTACKS, default="pgd")
    ap.add_argument("--pathology", default=model.DEMO_PATHOLOGY)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "data" / "demo"))
    args = ap.parse_args()

    img = load_image(Path(args.image).read_bytes())
    x = model.preprocess(img.px)
    x_adv = attacks.ATTACKS[args.method](x, args.eps, args.pathology)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = Path(args.image).stem[:40]
    before, after = model.to_uint8(x), model.to_uint8(x_adv)
    Image.fromarray(before, "L").save(out / f"{stem}_before.png")
    Image.fromarray(after, "L").save(out / f"{stem}_attacked.png")

    s0 = model.predict(before)[args.pathology]
    s1 = model.predict(after)[args.pathology]
    print(f"{args.pathology}: before {s0:.1%} -> after {s1:.1%} (threshold {model.THRESHOLD:.0%})")
    print(f"{args.method} eps={args.eps}px, PSNR {attacks.psnr(x, x_adv):.1f} dB; saved to {out}")


if __name__ == "__main__":
    main()
