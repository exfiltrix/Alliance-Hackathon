"""Scenarios from reference/medseal_poc.py, on the ported module."""
import time

import numpy as np
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.seal import core


@pytest.fixture(scope="module")
def key():
    return Ed25519PrivateKey.generate()


@pytest.fixture
def ct(ct_dataset):
    return ct_dataset.pixel_array.copy(), str(ct_dataset.SOPInstanceUID)


def test_hash_format_is_frozen():
    """Golden value: fails if the tile hash input or Merkle construction changes.

    If you change them on purpose, update this value AND re-seal all demo data.
    """
    px = np.arange(40 * 24, dtype=np.int16).reshape(40, 24)
    root = core.merkle_root(core.tile_hashes(px, "golden-uid", 16))
    assert root.hex() == GOLDEN_ROOT


def test_tile_size():
    assert core.tile_size_for((512, 512)) == 32
    assert core.tile_size_for((256, 300)) == 32
    assert core.tile_size_for((128, 128)) == 16
    assert core.tile_size_for((1024, 200)) == 16


def test_round_trip(ct, key):
    px, uid = ct
    record = core.seal(px, uid, key)
    assert record["tile"] == 16
    assert core.verify(px, record, key.public_key()) == (True, [])


def test_fake_nodule_is_localised(ct, key):
    px, uid = ct
    record = core.seal(px, uid, key, 16)
    fake = px.astype(np.float64)
    yy, xx = np.mgrid[0:px.shape[0], 0:px.shape[1]]
    amp = 0.35 * (np.percentile(px, 99) - np.percentile(px, 1))
    fake += amp * np.exp(-((yy - 78) ** 2 + (xx - 44) ** 2) / (2 * 4.0 ** 2))
    fake = np.clip(np.round(fake), np.iinfo(px.dtype).min, np.iinfo(px.dtype).max).astype(px.dtype)

    ok, changed = core.verify(fake, record, key.public_key())
    assert ok
    ys, xs = np.nonzero(fake != px)
    expected = sorted({(y // 16 * 16, x // 16 * 16) for y, x in zip(ys, xs)})
    assert changed == expected
    assert (64, 32) in changed  # tile holding the nodule centre (78, 44)


def test_one_pixel_change(ct, key):
    px, uid = ct
    record = core.seal(px, uid, key, 16)
    one = px.copy()
    one[10, 100] += 1
    assert core.verify(one, record, key.public_key()) == (True, [(0, 96)])


def test_forged_ledger_without_key_is_rejected(ct, key):
    px, uid = ct
    record = core.seal(px, uid, key, 16)
    fake = px.copy()
    fake[50:60, 50:60] = 0
    forged = dict(record)
    forged["leaves"] = core.tile_hashes(fake, uid, 16)
    forged["root"] = core.merkle_root(forged["leaves"])
    ok, _ = core.verify(fake, forged, key.public_key())
    assert not ok


def test_leaves_edited_but_root_kept_is_rejected(ct, key):
    px, uid = ct
    record = core.seal(px, uid, key, 16)
    forged = dict(record, leaves=dict(record["leaves"]))
    forged["leaves"][(0, 0)] = b"\0" * 32
    assert not core.check_record(forged, key.public_key())


def test_other_device_key_is_rejected(ct, key):
    px, uid = ct
    record = core.seal(px, uid, key, 16)
    assert not core.check_record(record, Ed25519PrivateKey.generate().public_key())


def test_seal_bound_to_uid(ct, key):
    """Moving a record to another image ID breaks it: uid is inside every tile hash and the signature."""
    px, uid = ct
    record = core.seal(px, uid, key, 16)
    moved = dict(record, uid="1.2.3.other")
    assert not core.check_record(moved, key.public_key())


def test_cropped_image_is_tampered(ct, key):
    px, uid = ct
    record = core.seal(px, uid, key, 16)
    _, changed = core.verify(px[:, :64], record, key.public_key())
    assert changed  # the missing right half must show up, not silently pass


def test_speed_512(key):
    big = np.random.default_rng(0).integers(-1024, 3000, size=(512, 512), dtype=np.int16)
    t0 = time.perf_counter()
    record = core.seal(big, "demo-512", key)
    core.verify(big, record, key.public_key())
    assert (time.perf_counter() - t0) * 1000 < 100  # spec: < 50 ms each


# Computed with the functions in reference/medseal_poc.py (the port matches byte for byte).
GOLDEN_ROOT = "dfd32173cb5802ca810476b4a5b0372fbf30fa82113a07bc9db1d84c04505d6d"
