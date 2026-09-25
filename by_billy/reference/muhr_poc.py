"""Muhr proof of concept: tile-level signing of a medical image and tamper detection."""
import hashlib
import time

import numpy as np
import pydicom
from pydicom.data import get_testdata_file
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


def tile_hashes(px, uid, tile):
    """SHA-256 fingerprint of every tile, bound to image ID and tile position."""
    h, w = px.shape
    out = {}
    for y in range(0, h, tile):
        for x in range(0, w, tile):
            block = np.ascontiguousarray(px[y:y + tile, x:x + tile])
            m = hashlib.sha256()
            m.update(f"{uid}|{y}|{x}|{block.shape}|{block.dtype}".encode())
            m.update(block.tobytes())
            out[(y, x)] = m.digest()
    return out


def merkle_root(leaves):
    level = [leaves[k] for k in sorted(leaves)]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest() for i in range(0, len(level), 2)]
    return level[0]


def seal(px, uid, key, tile):
    """Gateway side: fingerprint tiles, build Merkle root, sign it."""
    leaves = tile_hashes(px, uid, tile)
    root = merkle_root(leaves)
    return {"uid": uid, "tile": tile, "leaves": leaves, "root": root, "sig": key.sign(root + uid.encode())}


def verify(px, record, pub):
    """Viewer/AI side: check the ledger record is authentic, then compare tiles."""
    try:
        pub.verify(record["sig"], record["root"] + record["uid"].encode())
        record_ok = merkle_root(record["leaves"]) == record["root"]
    except InvalidSignature:
        record_ok = False
    now = tile_hashes(px, record["uid"], record["tile"])
    changed = sorted(k for k in now if now[k] != record["leaves"].get(k))
    return record_ok, changed


def ms(fn, *a, n=20):
    t0 = time.perf_counter()
    for _ in range(n):
        r = fn(*a)
    return r, (time.perf_counter() - t0) * 1000 / n


key = Ed25519PrivateKey.generate()   # lives only on the scanner gateway
pub = key.public_key()               # published in the device registry

ds = pydicom.dcmread(get_testdata_file("CT_small.dcm"))
orig = ds.pixel_array.copy()
uid = str(ds.SOPInstanceUID)
TILE = 16
record, t_seal = ms(seal, orig, uid, key, TILE)
print(f"CT image {orig.shape}, {orig.dtype}, value range {orig.min()}..{orig.max()}, tiles: {len(record['leaves'])}")

# Scenario 0: untouched image
ok, changed = verify(orig, record, pub)
print(f"[0] original: record_ok={ok}, changed_tiles={len(changed)}")

# Scenario A: inject a fake 'nodule' (smooth blob, like CT-GAN)
fake = orig.astype(np.float64)
yy, xx = np.mgrid[0:orig.shape[0], 0:orig.shape[1]]
cy, cx, r = 78, 44, 4.0
amp = 0.35 * (np.percentile(orig, 99) - np.percentile(orig, 1))
fake += amp * np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / (2 * r ** 2))
fake = np.clip(np.round(fake), np.iinfo(orig.dtype).min, np.iinfo(orig.dtype).max).astype(orig.dtype)
(okA, changedA), t_ver = ms(verify, fake, record, pub)
print(f"[A] fake nodule: record_ok={okA}, changed_tiles={len(changedA)} at {changedA}, pixels changed={int((fake != orig).sum())}")

# Scenario B: change a single pixel by +1
one = orig.copy()
one[10, 100] += 1
okB, changedB = verify(one, record, pub)
print(f"[B] one pixel +1: changed_tiles={len(changedB)} at {changedB}")

# Scenario C: attacker edits image AND rewrites the ledger hashes, but has no private key
forged = dict(record)
forged["leaves"] = tile_hashes(fake, uid, TILE)
forged["root"] = merkle_root(forged["leaves"])
okC, changedC = verify(fake, forged, pub)
print(f"[C] forged ledger without key: record_ok={okC}  -> rejected={not okC}")

print(f"timing on 128x128: seal {t_seal:.2f} ms, verify {t_ver:.2f} ms")

# Timing on a typical 512x512 CT slice
big = np.random.default_rng(0).integers(-1024, 3000, size=(512, 512), dtype=np.int16)
rec_big, t_seal_big = ms(seal, big, "demo-512", key, 32)
_, t_ver_big = ms(verify, big, rec_big, pub)
print(f"timing on 512x512 (tile 32): seal {t_seal_big:.2f} ms, verify {t_ver_big:.2f} ms")

# Picture for the pitch
lo, hi = np.percentile(orig, [1, 99])
fig, axes = plt.subplots(1, 3, figsize=(12, 4.3), dpi=150)
titles = ["1. Оригинал (запечатан)", "2. Подделка: добавлен «узел»", "3. Muhr: подделка найдена"]
for ax, img, t in zip(axes, [orig, fake, fake], titles):
    ax.imshow(img, cmap="gray", vmin=lo, vmax=hi)
    ax.set_title(t, fontsize=12)
    ax.axis("off")
for (y, x) in changedA:
    axes[2].add_patch(Rectangle((x - 0.5, y - 0.5), TILE, TILE, fill=False, edgecolor="red", linewidth=2))
axes[2].text(2, 124, "Снимок изменён после съёмки", color="white", fontsize=9,
             bbox=dict(facecolor="red", edgecolor="none", pad=3))
fig.tight_layout()
fig.savefig("muhr_check.png", bbox_inches="tight")
print("saved picture")
