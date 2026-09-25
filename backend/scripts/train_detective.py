"""Train the AI detective (ResNet18: real X-ray vs forgery) on CPU and measure it honestly.

    .venv/bin/python -m scripts.train_detective            # ~20 min on a laptop CPU; needs data/nih

- Images: all NIH X-rays in data/nih, as the 224x224 8-bit model-input picture.
  80% train / 20% held-out test, split by image (a test image is never seen in training).
- Every epoch each training image appears twice: as is, and with a fresh random forgery
  (app/ai/fakes.py), so the network never sees the same fake twice.
- Test: each held-out image as is + one forgery (kinds in rotation, fixed seed).
  Reports AUC, accuracy, false alarms on real images, recall per forgery kind, and how often
  the Grad-CAM peak lands on the edited region. Also false alarms on out-of-domain real
  images (paediatric Kermany set), so the passport/UI can say where it is not reliable.
Writes weights/detective.pt (fp16, gitignored) and app/ai/detective_metrics.json (committed).
"""
import argparse
import json
import time
from datetime import datetime, timezone

import cv2
import numpy as np
import torch
import torch.nn.functional as F

from app.ai import detective, fakes, model
from app.config import settings
from app.imaging import display_pixels, load_image

SEED = 0
TEST_SHARE = 0.2
BATCH = 32


def load_dir(*dirs) -> np.ndarray:
    paths = sorted(p for d in dirs for p in (settings.data_dir / d).glob("*.png"))
    return np.stack([model.model_input(display_pixels(load_image(p.read_bytes()))) for p in paths])


def cached(name: str, *dirs) -> np.ndarray:
    path = settings.data_dir / "detective" / f"{name}.npy"
    if path.exists():
        return np.load(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = load_dir(*dirs)
    np.save(path, arr)
    return arr


def jitter(img: np.ndarray, rng) -> np.ndarray:
    """Same photometric noise for real and fake, so brightness is never the clue."""
    out = img.astype(np.float32) * rng.uniform(0.9, 1.1) + rng.uniform(-12, 12)
    if rng.random() < 0.5:
        out = out[:, ::-1]
    return np.clip(out, 0, 255).astype(np.uint8)


def auc(labels: np.ndarray, scores: np.ndarray) -> float:
    order = scores.argsort()
    ranks = np.empty(len(scores))
    ranks[order] = np.arange(1, len(scores) + 1)
    pos = labels == 1
    return float((ranks[pos].sum() - pos.sum() * (pos.sum() + 1) / 2) / (pos.sum() * (~pos).sum()))


@torch.no_grad()
def predict(net, imgs: np.ndarray) -> np.ndarray:
    return np.concatenate([torch.sigmoid(net(detective.to_tensor(list(imgs[i:i + 64])))).numpy()[:, 0]
                           for i in range(0, len(imgs), 64)])


def make_test_set(test: np.ndarray):
    rng = np.random.default_rng(SEED + 1)
    fake_imgs, masks, kinds = [], [], []
    for i, img in enumerate(test):
        kind = fakes.KINDS[i % len(fakes.KINDS)]
        f, m, _ = fakes.make_fake(img, rng, test[(i + 1) % len(test)], kind)
        fake_imgs.append(f), masks.append(m), kinds.append(kind)
    return np.stack(fake_imgs), np.stack(masks), np.array(kinds)


def evaluate(net, test, test_fakes, masks, kinds, with_cam: bool) -> dict:
    net.eval()
    p_real, p_fake = predict(net, test), predict(net, test_fakes)
    labels = np.r_[np.zeros(len(p_real)), np.ones(len(p_fake))]
    scores = np.r_[p_real, p_fake]
    out = {
        "auc": round(auc(labels, scores), 3),
        "accuracy": round(float(((scores > 0.5) == labels).mean()), 3),
        "false_alarms_on_real": round(float((p_real > 0.5).mean()), 3),
        "recall_by_kind": {k: round(float((p_fake[kinds == k] > 0.5).mean()), 3) for k in fakes.KINDS},
    }
    if with_cam:
        hits = []
        kernel = np.ones((15, 15), np.uint8)
        for f, m in zip(test_fakes, masks):
            _, cam = detective.grad_cam(net, detective.to_tensor(f))
            y, x = np.unravel_index(cam.argmax(), cam.shape)
            hits.append(bool(cv2.dilate(m, kernel)[y, x]))
        out["heatmap_hits_edit"] = round(float(np.mean(hits)), 3)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--lr", type=float, default=3e-4)
    args = ap.parse_args()
    torch.manual_seed(SEED)
    rng = np.random.default_rng(SEED)

    t0 = time.perf_counter()
    imgs = cached("nih", "nih/normal", "nih/findings")
    if not len(imgs):
        raise SystemExit("No images in data/nih. Run: python -m scripts.fetch_dataset")
    perm = np.random.default_rng(SEED).permutation(len(imgs))
    n_test = int(len(imgs) * TEST_SHARE)
    test, train = imgs[perm[:n_test]], imgs[perm[n_test:]]
    test_fakes, masks, kinds = make_test_set(test)
    print(f"{len(train)} train / {len(test)} test images, loaded in {time.perf_counter() - t0:.0f}s", flush=True)

    net = detective.build(pretrained=True)
    opt = torch.optim.AdamW(net.parameters(), lr=args.lr, weight_decay=1e-4)
    steps = args.epochs * (-(-2 * len(train) // BATCH))
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=steps, pct_start=0.15)

    for epoch in range(1, args.epochs + 1):
        net.train()
        t1, losses = time.perf_counter(), []
        order = rng.permutation(2 * len(train))  # index < len(train): real, else fake of that image
        for b in range(0, len(order), BATCH):
            xs, ys = [], []
            for j in order[b:b + BATCH]:
                i = j % len(train)
                img = train[i]
                if j >= len(train):
                    img, _, _ = fakes.make_fake(img, rng, train[rng.integers(len(train))])
                xs.append(jitter(img, rng))
                ys.append(float(j >= len(train)))
            logits = net(detective.to_tensor(xs))[:, 0]
            loss = F.binary_cross_entropy_with_logits(logits, torch.tensor(ys))
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
            losses.append(float(loss))
        m = evaluate(net, test, test_fakes, masks, kinds, with_cam=False)
        print(f"epoch {epoch}: loss {np.mean(losses):.3f}, test AUC {m['auc']}, acc {m['accuracy']}, "
              f"recall {m['recall_by_kind']} ({time.perf_counter() - t1:.0f}s)", flush=True)

    test_metrics = evaluate(net, test, test_fakes, masks, kinds, with_cam=True)
    kermany = cached("kermany", "xray/normal", "xray/pneumonia")
    ood = {"kermany_paediatric_false_alarms": round(float((predict(net, kermany) > 0.5).mean()), 3)} if len(kermany) else {}
    print("test", test_metrics, "out-of-domain", ood, flush=True)

    settings.detective_weights.parent.mkdir(parents=True, exist_ok=True)
    torch.save({k: v.half() for k, v in net.state_dict().items()}, settings.detective_weights)
    settings.detective_metrics.write_text(json.dumps({
        "model": "ResNet18 (ImageNet init), 1 channel, 224x224",
        "trained_on": f"NIH ChestX-ray14 (CC0), {len(train)} images + synthetic forgeries",
        "forgery_kinds": list(fakes.KINDS),
        "epochs": args.epochs,
        "test": {"images": len(test), "forgeries": len(test_fakes), **test_metrics},
        "out_of_domain": ood,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }, indent=2) + "\n")
    print(f"saved {settings.detective_weights} and {settings.detective_metrics} in {time.perf_counter() - t0:.0f}s")


if __name__ == "__main__":
    main()
