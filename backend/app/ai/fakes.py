"""Synthetic X-ray forgeries for training and demoing the detective.

Four edits people actually make to a scan, all on the 224x224 8-bit model-input picture:
  nodule     paint a round opacity (a fake tumour)
  splice     paste a patch from another patient's X-ray (cv2.seamlessClone)
  copy_move  copy a patch of the same X-ray to another place (hide or duplicate a finding)
  removal    erase a region and fill it in (cv2.inpaint + matching grain)
Each returns (fake, mask) where mask marks the edited pixels (for checking Grad-CAM).
"""
import cv2
import numpy as np

KINDS = ("nodule", "splice", "copy_move", "removal")
# lung fields of a centred PA chest X-ray at 224 px: keep edits where a radiologist would look
Y_RANGE, X_RANGE = (35, 140), (35, 189)


def _centre(rng: np.random.Generator, margin: int) -> tuple[int, int]:
    y = int(rng.integers(max(Y_RANGE[0], margin), min(Y_RANGE[1], 224 - margin)))
    x = int(rng.integers(max(X_RANGE[0], margin), min(X_RANGE[1], 224 - margin)))
    return y, x


def _ellipse_mask(shape, cy, cx, ry, rx, angle) -> np.ndarray:
    m = np.zeros(shape, np.uint8)
    cv2.ellipse(m, (cx, cy), (rx, ry), angle, 0, 360, 255, -1)
    return m


def _grain(img: np.ndarray) -> float:
    """Pixel noise level of the image (std of the high-pass residual)."""
    f = img.astype(np.float32)
    return float(np.std(f - cv2.GaussianBlur(f, (0, 0), 1.5)))


def nodule(img: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    r = float(rng.uniform(5, 16))
    cy, cx = _centre(rng, int(3 * r))
    yy, xx = np.mgrid[:224, :224].astype(np.float32)
    ang = rng.uniform(0, np.pi)
    dy, dx = yy - cy, xx - cx
    u = (dx * np.cos(ang) + dy * np.sin(ang)) / (r * rng.uniform(0.8, 1.2))
    v = (-dx * np.sin(ang) + dy * np.cos(ang)) / r
    d2 = u ** 2 + v ** 2
    blob = np.exp(-d2 ** rng.uniform(1.0, 2.0))  # soft to sharp edge
    texture = cv2.GaussianBlur(rng.normal(0, 1, (224, 224)).astype(np.float32), (0, 0), 2)
    amp = rng.uniform(25, 70)
    out = img.astype(np.float32) + amp * blob * (1 + 0.15 * texture)
    return np.clip(out, 0, 255).astype(np.uint8), (d2 < 2.5).astype(np.uint8)


def _clone(img, src, rng, src_centre=None) -> tuple[np.ndarray, np.ndarray]:
    ry, rx = int(rng.integers(10, 28)), int(rng.integers(10, 28))
    margin = max(ry, rx) + 4
    sy, sx = src_centre or _centre(rng, margin)
    for _ in range(20):  # destination not overlapping the source (copy-move) and inside the lungs
        ty, tx = _centre(rng, margin)
        if src is not img or abs(ty - sy) + abs(tx - sx) > 2 * margin:
            break
    ys, xs = slice(sy - margin, sy + margin), slice(sx - margin, sx + margin)
    patch = cv2.cvtColor(np.ascontiguousarray(src[ys, xs]), cv2.COLOR_GRAY2BGR)
    pmask = _ellipse_mask(patch.shape[:2], margin, margin, ry, rx, float(rng.uniform(0, 180)))
    mask = np.zeros((224, 224), np.uint8)
    mask[ty - margin:ty + margin, tx - margin:tx + margin] = pmask > 0  # before seamlessClone: it edits pmask
    dst = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    out = cv2.seamlessClone(patch, dst, pmask, (tx, ty), cv2.NORMAL_CLONE)
    return cv2.cvtColor(out, cv2.COLOR_BGR2GRAY), mask


def splice(img, rng, donor) -> tuple[np.ndarray, np.ndarray]:
    return _clone(img, donor, rng)


def copy_move(img, rng) -> tuple[np.ndarray, np.ndarray]:
    return _clone(img, img, rng)


def removal(img, rng) -> tuple[np.ndarray, np.ndarray]:
    ry, rx = int(rng.integers(8, 24)), int(rng.integers(8, 24))
    cy, cx = _centre(rng, max(ry, rx) + 2)
    m = _ellipse_mask(img.shape, cy, cx, ry, rx, float(rng.uniform(0, 180)))
    filled = cv2.inpaint(img, m, 5, cv2.INPAINT_TELEA).astype(np.float32)
    filled += (m > 0) * rng.normal(0, _grain(img), img.shape)  # inpaint is too smooth: add the image's grain
    return np.clip(filled, 0, 255).astype(np.uint8), (m > 0).astype(np.uint8)


def make_fake(img: np.ndarray, rng: np.random.Generator, donor: np.ndarray, kind: str | None = None):
    """-> (fake, mask, kind). img/donor: 224x224 uint8."""
    kind = kind or KINDS[int(rng.integers(len(KINDS)))]
    if kind == "nodule":
        fake, mask = nodule(img, rng)
    elif kind == "splice":
        fake, mask = splice(img, rng, donor)
    elif kind == "copy_move":
        fake, mask = copy_move(img, rng)
    else:
        fake, mask = removal(img, rng)
    return fake, mask, kind
