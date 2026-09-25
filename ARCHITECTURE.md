# MedSeal — architecture

```
Scanner ──► [Gateway: seal] ──► PACS / storage
                                     │
Doctor / AI ◄── [Verify + Shield] ◄──┘
                     │ unsigned
                     └──► [AI detective]

AI model ──► [Crash test] ──► [Passport]
```

In the demo the web page `/seal` plays the role of the gateway. In a real hospital the gateway is a small box next to the scanner — say this in the pitch.

## 1. Seal (deterministic crypto — no AI)

Port `reference/medseal_poc.py` (already tested: finds a 1-pixel change, rejects forged ledger, ~2 ms per 512×512 image).

1. Read pixels: `pydicom.dcmread(f).pixel_array` or `np.array(Image.open(f))` (convert to grayscale, keep dtype).
2. Image ID (`uid`): DICOM `SOPInstanceUID`; for PNG generate a UUID and write it to a `medseal_uid` tEXt chunk.
3. Split into tiles (32×32 for images ≥ 256 px, 16×16 for smaller). For each tile:
   `sha256(f"{uid}|{y}|{x}|{shape}|{dtype}".encode() + tile.tobytes())`.
4. Merkle root over tile hashes sorted by (y, x); duplicate the last node on odd levels.
5. Sign `root + uid` with the device's **Ed25519** private key.
6. Store in the ledger. Each entry also stores `prev_hash` and `entry_hash = sha256(prev_hash + record)` → a hash chain, so old records can't be silently rewritten.

### Verification
1. Find the ledger record by `uid` → none = **unsigned**.
2. Check the signature with the device public key and that the stored leaves really produce the stored root → otherwise **forged record**.
3. Recompute tile hashes of the uploaded image, compare with stored leaves → mismatches = **tampered** tiles → red boxes on a PNG preview.

### Keys
- `devices` table: `device_id`, `name`, `public_key_hex`, `revoked`.
- Private keys: in the demo, files in `backend/keys/` (gitignored) loaded only by the seal module. In production: hardware module (HSM/TPM) in the gateway.

## 2. AI modules

### Diagnostic model under test
`torchxrayvision`: `xrv.models.DenseNet(weights="densenet121-res224-all")`.
Input: grayscale, resized to 224×224, normalised with `xrv.datasets.normalize(img, 255)` (range ≈ [-1024, 1024]), shape `[1, 1, 224, 224]`.
Output: one score per pathology in `model.pathologies` (use "Pneumonia" for the demo).

### Crash test (`ai/attacks.py`)
- FGSM targeted: `x_adv = x + eps * sign(∇x score["Pneumonia"])`, clamp to valid range.
- PGD: 10 steps of FGSM with step `eps/4`, projected to the eps-ball.
- eps grid in pixel units of 0–255: `[0.5, 1, 2, 4]` → multiply by `2048/255` in normalised units.
- On N healthy images: flip = score crosses the model's threshold. Report flip rate per eps and PSNR (to show the noise is invisible).
- Robustness score: `10 × (1 − flip_rate at eps=1)`, rounded to 1 decimal. Explain the formula in the passport.

### Shield (`ai/shield.py`) — feature squeezing, no training needed
- Work on the 224×224 8-bit picture the model sees (the attack lives at that scale). Squeeze it with a 3×3 median filter.
- `d = Σ over pathologies |logit(original) − logit(squeezed)|` — raw logits, not the `op_threshs`-calibrated scores (calibration stretches small changes near each threshold, so clean images looked as unstable as attacked ones). 5-bit depth reduction was tried and caught fewer attacks.
- Threshold = 99th percentile of `d` on clean **adult** X-rays (NIH ChestX-ray14 subset, `scripts/calibrate_shield.py` → `app/ai/shield_calibration.json`, committed). 95th gave 8% false alarms. Calibrating on the paediatric Kermany set does not transfer: the model is out of domain there and `d` on clean images is ~4× larger.
- Measured on held-out NIH images: false alarms 0.9%; PGD caught 100% at eps ≥ 1 px, FGSM 62% / 87% / 100% at eps 1 / 2 / 4. Weak attacks (eps 0.5, which rarely fool the model on adult images) slip through — say so honestly.

### Detective (`ai/detective.py`) — for unsigned images
- Data: public chest X-rays (e.g. Kaggle "Chest X-Ray Images (Pneumonia)"). Generate fakes automatically in `scripts/make_fakes.py`:
  paste a nodule blob (Gaussian or a patch from another image via `cv2.seamlessClone`), remove a region (`cv2.inpaint`), copy-move.
- Model: torchvision ResNet18, 1 input channel, binary output (real/fake), 224×224. Train 3–5 epochs (Colab GPU or CPU on a small set).
- Explanation: Grad-CAM heatmap on the last conv block.
- Always shown as a probability, never as a certain verdict.

## 3. Data model (SQLite)

| Table | Columns |
|---|---|
| devices | id, name, hospital, public_key_hex, revoked, created_at |
| seals | id, uid, device_id, created_at, shape, dtype, tile, leaves_json, root_hex, sig_hex, prev_hash, entry_hash |
| verifications | id, uid, result (authentic/tampered/unsigned/forged), changed_tiles_json, detective_prob, shield_flag, created_at |
| models | id, name, version, source, intended_use |
| crash_tests | id, model_id, n_images, results_json, robustness_score, created_at |
| passports | id, model_id, crash_test_id, verdict, conditions (JSON codes), organisation, report_json (frozen snapshot), created_at |

New columns on existing tables are added on startup by `db._add_missing_columns` (no Alembic).

## 4. Performance targets
Seal/verify < 50 ms per image; shield < 1 s; crash test 50 images < 2 min on CPU.
