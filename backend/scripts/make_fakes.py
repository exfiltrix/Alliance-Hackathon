"""Make demo forgeries for the detective, from held-out NIH images the detective never saw.

    .venv/bin/python -m scripts.make_fakes            # after scripts.train_detective

For each forgery kind it tries a few held-out images and keeps one where the original reads
as real and the forgery as edited (a demo example, not a quality measure: the honest numbers
are in app/ai/detective_metrics.json). Writes data/demo/fakes/<kind>.png (upload this to
/verify: it has no seal, so the detective runs), <kind>_original.png and <kind>_mask.png.
"""
import numpy as np
from PIL import Image

from app.ai import detective, fakes
from app.config import settings
from scripts.train_detective import SEED, TEST_SHARE, cached

TRIES = 30


def main():
    imgs = cached("nih", "nih/normal", "nih/findings")
    perm = np.random.default_rng(SEED).permutation(len(imgs))
    test = imgs[perm[: int(len(imgs) * TEST_SHARE)]]
    out = settings.data_dir / "demo" / "fakes"
    out.mkdir(parents=True, exist_ok=True)
    net = detective.load()
    rng = np.random.default_rng(42)

    for k, kind in enumerate(fakes.KINDS):
        best = None
        for t in range(TRIES):
            img = test[(k * TRIES + t) % len(test)]
            fake, mask, _ = fakes.make_fake(img, rng, test[rng.integers(len(test))], kind)
            p_real, _ = detective.grad_cam(net, detective.to_tensor(img))
            p_fake, _ = detective.grad_cam(net, detective.to_tensor(fake))
            margin = p_fake - p_real
            if best is None or margin > best[0]:
                best = (margin, img, fake, mask, p_real, p_fake)
            if p_real < 0.2 and p_fake > 0.8:
                break
        _, img, fake, mask, p_real, p_fake = best
        Image.fromarray(fake).save(out / f"{kind}.png")
        Image.fromarray(img).save(out / f"{kind}_original.png")
        Image.fromarray(mask * 255).save(out / f"{kind}_mask.png")
        print(f"{kind:10s} original {p_real:.0%} -> forgery {p_fake:.0%}")
    print("saved to", out)


if __name__ == "__main__":
    main()
