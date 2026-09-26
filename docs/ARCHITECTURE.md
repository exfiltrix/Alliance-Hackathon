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

Port `reference/medseal_poc.py` (already tested: finds a 1-pixel change, rejects forged ledger, ~2 ms per 512×512 image). **The tile-hash and Merkle format below is frozen** (`tests/test_seal_core.py::test_hash_format_is_frozen`, `GOLDEN_ROOT`) — everything added after the audit remediation (signature v2, certificates, anchors, versioned metadata) is layered around it in new, versioned fields, never inside it.

1. Read pixels: `pydicom.dcmread(f).pixel_array` or `np.array(Image.open(f))` (native array — DICOM LUT/windowing and `MONOCHROME1` inversion are display-only and never touch this; see §1a).
2. Image ID (`uid`): DICOM `SOPInstanceUID`; for PNG generate a UUID and write it to a `medseal_uid` tEXt chunk.
3. Split into tiles (32×32 for images ≥ 256 px, 16×16 for smaller). For each tile:
   `sha256(f"{uid}|{y}|{x}|{shape}|{dtype}".encode() + tile.tobytes())`.
4. Merkle root over tile hashes sorted by (y, x); duplicate the last node on odd levels.
5. Sign the record with the device's **Ed25519** private key — the frozen v1 message (`root + meta_hash + uid`, `app/seal/core.py::seal`) for rows that predate the audit, or the versioned v2 header below for every new seal.
6. Store in the ledger. Each entry also stores `prev_hash` and `entry_hash = sha256(prev_hash + record)` → a hash chain, so old records can't be silently rewritten. Since CRY-03, every append is also mirrored into a signed, external anchor file (§1c) so a full in-database chain rewrite is still detected.

### Verification
1. Find the ledger record by `uid`, or by content when the ID is missing/replaced (§1b) → neither = **unsigned**.
2. `sig_version >= 2`: check the v2 signature over the canonical header (binds `created_at`, `device_id`, `meta_hash`, `patient_ref` — editing any of them without the key now fails signature verification directly, not just the hash-chain check). `sig_version < 2` (pre-migration rows): check the frozen v1 signature over `root + meta_hash + uid`. Either way, also check the device has a valid root-signed certificate (§1d), the hash-chain link (`entry_hash`), and that the device was not revoked before this seal → otherwise **forged record**, with the specific reason in the response (`bad_signature` / `untrusted_device` / `ledger_entry_modified` / `device_revoked`).
3. Recompute tile hashes of the uploaded image, compare with stored leaves → mismatches = **tampered** tiles → red-and-white boxes on a preview (visible in greyscale/accessibility mode too).
4. If the row carries a non-empty `patient_ref` and the upload still has a `PatientID`, compare the HMAC (§1e); a mismatch is **tampered**/`patient_mismatch` even though every pixel and tile is untouched — this catches an authentic image filed under the wrong patient.

### 1a. Display pipeline (AI + preview only, never hashing)
`imaging.display_pixels()` applies the DICOM Modality LUT (RescaleSlope/Intercept), VOI LUT when present, and inverts `MONOCHROME1` datasets, then feeds that to the preview, the shield and the detective. The seal, `changed_tiles` and the Merkle root always hash the native array from `pixel_array`/`np.array(Image.open(...))` — a display-only change (e.g. correcting the LUT) can never flip a status.

### 1b. Content-based seal recovery (P1-03)
When the uploaded image has no `uid`, or the `uid` is not in the ledger, `verify.recovery` computes a 64-bit difference hash (`dhash_hex`, on the grayscale display view, 9×8) and ranks the 5 closest sealed rows with the same `shape`/`dtype` by Hamming distance. A candidate is accepted only if at least half its tiles hash-match the upload (different X-rays share ~0% of tiles, so this cannot false-match two unrelated images). An accepted candidate whose tiles and metadata all match returns **authentic** with `warning: "seal_id_missing"` and `matched_by: "content"`; a partial match returns **tampered**/`seal_id_removed` against that candidate. Sealing also runs this search first: an image ≥ 50% but < 100% identical to an existing seal is refused with `409` ("derived from sealed image #N"), closing the strip-ID-then-edit-then-reseal-as-new loophole. This is a linear scan over all sealed rows — fine for a demo; production would index by a dhash prefix. `dhash_hex` is stored but deliberately excluded from `record_bytes()`, so backfilling it on old rows never changes `entry_hash` or the anchor chain.

### 1c. External anchors (CRY-03)
The database alone is not a trust root: an attacker with write access to SQLite can rewrite every row and recompute a fully consistent `prev_hash`/`entry_hash` chain. After each seal, `seal/anchors.py` appends one fsync'ed, root-signed line — `{n, head_hash, at, sig}` over `b"MEDSEAL-ANCHOR-v1\n" + canonical_json(...)` — to `MEDSEAL_ANCHOR_PATH` (default `backend/anchors/anchors.jsonl`, gitignored, outside the database file). `GET /ledger/check` re-verifies every anchor's signature and that the n-th row's `entry_hash` still equals the anchored `head_hash`; a full, internally-consistent chain rewrite now shows up as `anchor_mismatch`, which a database-only hash chain could never catch on its own.

### 1d. Device keys and certificates (CRY-02)
- `devices` table: `device_id`, `name`, `public_key_hex`, `revoked`, `cert_sig_hex`.
- Private keys: in the demo, files in `backend/keys/` (gitignored) loaded only by the seal module. In production: hardware module (HSM/TPM) in the gateway.
- A **root key** (`scripts/create_root_key.py`, `backend/keys/root.{pem,pub}`, gitignored) signs a certificate over each device's `{device_id, name, hospital, public_key_hex, created_at}` at creation time. Verification loads only `root.pub` and rejects a record whose device has no valid certificate — inserting a new device row directly in the database, or swapping a device's `public_key_hex`, now fails with `forged`/`untrusted_device` instead of silently being trusted. `MEDSEAL_REQUIRE_DEVICE_CERT=0` is a migration escape hatch for old data: an uncertified device downgrades to a `device_not_certified` warning on an otherwise-authentic seal instead of `forged`. `scripts/certify_devices.py` is the one-time migration action — see root `CLAUDE.md` for the exact commands.
- In the demo the root key sits on the same host as everything else; in production it belongs offline or in an HSM, and every verifier holds only the public half.

### 1e. Patient binding (CRY-01)
`patient_ref = HMAC-SHA256(MEDSEAL_PATIENT_SALT, PatientID)`, computed before patient tags are stripped, stored on the seal row (never the PatientID itself), empty when there is no salt or no PatientID. See "Verification" step 4 above.

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
- **Shield `compatible` rule uses point estimates, not confidence-interval bounds (AI-01, decided).** `passport/report.shield_block()` computes exact 95% Clopper–Pearson intervals for the PGD-eps-1 detection rate and the false-positive rate (`app/ai/statistics.py`, stdlib only) and returns them in `confidence_intervals`, shown next to the point estimates in the passport UI and PDF, labelled "95% confidence interval", together with `adaptive_attack_tested: false`. The pass/fail rule itself (`compatible = detection ≥ 0.9 and FPR ≤ 0.02`) still reads the point estimates. With the current calibration sample (29/29 PGD detections at eps 1, 4/450 false alarms) the interval's lower detection bound is 0.881 and the interval's upper FPR bound is 0.023 — neither alone clears the 0.9 / 0.02 thresholds, so switching the rule to interval bounds would flip the demo passport from `allowed_with_conditions` to `not_allowed` on this sample size alone, not because the shield got worse. A larger calibration set (more held-out clean images and more successful attacks at eps 1) is required before the rule can safely move to interval bounds; until then the intervals are informational, and `tests/test_passport.py::test_shield_compatible_uses_point_estimates_not_interval_bounds` pins this behaviour.

### Detective (`ai/detective.py`) — for unsigned images
- Data: public chest X-rays (e.g. Kaggle "Chest X-Ray Images (Pneumonia)"). Generate fakes automatically in `scripts/make_fakes.py`:
  paste a nodule blob (Gaussian or a patch from another image via `cv2.seamlessClone`), remove a region (`cv2.inpaint`), copy-move.
- Model: torchvision ResNet18, 1 input channel, binary output (real/fake), 224×224. Train 3–5 epochs (Colab GPU or CPU on a small set).
- Explanation: Grad-CAM heatmap on the last conv block.
- Always shown as a probability, never as a certain verdict.

## 3. Versioned metadata and de-identification (IMG-03, IMG-04)

- `meta_fields(image, version)` binds display-affecting metadata into the signed message via
  `meta_hash`, so it can't be edited independently of the pixels. `META_TAGS` (v1) is the
  original small set; `META_TAGS_V2` adds `VOILUTSequence`, `ModalityLUTSequence`,
  `PresentationLUTShape`, `ImageOrientationPatient`, `PatientOrientation`,
  `ImagerPixelSpacing`, `NumberOfFrames`, `BurnedInAnnotation`, `StudyDate`,
  `AcquisitionDate`, and every element in the overlay-plane groups `0x6000`–`0x60FF` (canonical
  JSON of sequence items, so a fake finding drawn as an overlay is caught even though it never
  touches `PixelData`). `seals.meta_version` records which set a row was signed against; v1 rows
  keep verifying with the v1 set forever, only new seals use v2.
- De-identification (`strip_patient_tags`) removes every element with VR `PN` recursively
  through sequences, plus `AccessionNumber`, `InstitutionName`, `InstitutionAddress`,
  `InstitutionalDepartmentName`, `ReferringPhysicianName`, `PerformingPhysicianName`,
  `OperatorsName`, `PhysiciansOfRecord`, `RequestingPhysician`, `StudyID`,
  `DeviceSerialNumber`, `StationName`, and private tags. **Deliberate deviation from DICOM
  PS3.15's Basic Profile: every UID is kept**, because `SOPInstanceUID` is the seal's own image
  identifier — removing it would break the seal, not protect the patient. If
  `BurnedInAnnotation == "YES"`, seal and verify responses carry `phi_warning:
  "burned_in_annotation"` (the pixels themselves may still show a name; MedSeal cannot inspect
  pixel content for PHI).

## 4. Data model (SQLite)

| Table | Columns |
|---|---|
| devices | id, name, hospital, public_key_hex, revoked, cert_sig_hex, created_at |
| seals | id, uid, device_id, created_at, shape, dtype, tile, leaves_json, root_hex, sig_hex, sig_version, meta_hash_hex, meta_json, meta_version, patient_ref, phi_warning, dhash_hex, prev_hash, entry_hash, file_name |
| anchors | id, batch_root_hex, count, tx_hash, block_number, chain_id, onchain_index, status, created_at — one row per confirmed on-chain batch (docs/BLOCKCHAIN.md) |
| seal_anchors | id, seal_id, anchor_id, proof_json — kept out of `seals` so the ledger stays append-only |
| audit_log | id, at, action, actor, target, result, ip — insert/list only (docs/SECURITY.md) |
| verifications | id, uid, result (authentic/tampered/unsigned/forged), changed_tiles_json, detective_prob, shield_flag, created_at |
| models | id, name, version, source, intended_use |
| crash_tests | id, model_id, n_images, results_json, robustness_score, created_at |
| passports | id, model_id, crash_test_id, verdict, conditions (JSON codes), organisation, report_json (frozen snapshot), signature_hex, created_at |

New columns on existing tables are added on startup by `db._add_missing_columns` (no Alembic);
`db._ensure_seal_uid_index` adds a unique index on `seals.uid` once no legacy duplicates block it.
The external anchor file (§1c) lives outside this database on purpose — see CRY-03.

## 5. Performance targets
Seal/verify < 50 ms per image; shield < 1 s; crash test 50 images < 2 min on CPU.

## 6. Known limitations

- **Demo root key on the same host.** The trust root that signs device certificates and anchors
  lives in `backend/keys/root.pem` next to everything else. Production needs it offline or in an
  HSM, with verifiers holding only `root.pub`.
- **O(n) content-based recovery.** §1b scans every sealed row's `dhash_hex` linearly. Fine at
  demo scale; production would index by a dhash prefix (e.g. a bucketed/LSH index).
- **Single-process locks.** `ledger.append`'s lock (SEC-05) and the crash-test worker's queue
  lock (SEC-02) are `threading.Lock`s local to one Python process. A multi-worker deployment
  (multiple `uvicorn` processes) needs a database-level lock instead — SQLite's own
  `prev_hash UNIQUE` constraint plus the one-retry-on-`IntegrityError` path is what currently
  keeps a multi-process race from corrupting the chain, at the cost of an occasional 500 under
  very tight concurrency across processes.
- **No rate limiting.** Every endpoint is open to as many requests as the process can serve
  (beyond the crash-test worker's own single-job queue and the 50 MB / `MEDSEAL_MAX_PIXELS`
  upload limits). Out of scope for this remediation round.
- **Merkle tree has no leaf/node domain separation.** The frozen format hashes leaves and
  internal nodes the same way (no distinguishing prefix byte), which is a known weakness in some
  Merkle constructions (a second-preimage style leaf/node confusion). The tile-hash and Merkle
  format is frozen (`GOLDEN_ROOT`) and deliberately not changed here; a future tile-format v2
  would be the place to fix this, versioned the same way `sig_version`/`meta_version` are.
- **Shield not proven robust to an adaptive attacker.** Every shield result carries
  `adaptive_attack_tested: false`; AI-03 (PGD against the shield itself via a BPDA
  approximation) is not implemented in this environment (no local torch install).
- **Shield false alarms on full-resolution X-rays.** The threshold (10.419) was calibrated on
  300 px NIH images (~1% false alarms). On clean 1024 px RSNA Pneumonia DICOMs (the same NIH
  source at full resolution, n=300) it flags **18–22%**: a single area resize 1024→224 keeps
  sensor grain that the 3×3 median wipes, so the logits move. Two fixes were measured
  (2026-09-26) and rejected: (a) resizing large inputs via 300 px first brings false alarms to
  1.3% but blurs detail the model needs (Pneumonia AUC on RSNA 0.864→0.834, positives drop
  from ~0.8–0.96 to ~0.52); (b) a separate threshold for large inputs (p99 on RSNA = 23.55)
  gives 0% false alarms but catches only 11–28% of eps=1 attacks made at full resolution
  (vs 85–100% now). Kept as is: a false alarm only asks the doctor to recheck, a missed
  attack does not. A real fix needs a resolution-aware detector, calibrated and attack-tested
  on full-resolution images.
- **Detective is not validated on real forgeries.** Trained and measured only on synthetic
  edits; `experimental: true` is hardcoded and the passport/UI never treat it as more than a
  probability.
