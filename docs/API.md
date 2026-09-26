# MedSeal — API (FastAPI, prefix `/api`)

All image uploads: `multipart/form-data`, field `file` (DICOM `.dcm` or `.png`). Images returned as base64 PNG previews (no `data:` prefix — use `data:image/png;base64,${preview_png}`).
Interactive docs while the backend runs: http://localhost:8000/docs. CORS allows `http://localhost:3000`.

Errors: `{"detail": "message"}` with status `404` (not found), `409` (conflict), `413` (file too large, > 50 MB, or decodes to > 64 Mpx), `429` (more than 120 POSTs per minute from one IP; `Retry-After` header), `415` (not a DICOM/PNG), `422` (missing/invalid field).
All times are UTC ISO strings: `"2026-09-26T10:00:00Z"`.

## Devices
| Method | Path | Auth | Body | Returns |
|---|---|---|---|---|
| GET | `/devices` | — (public) | — | list of devices |
| POST | `/devices` | `Authorization: Bearer <MEDSEAL_ADMIN_TOKEN>` | `{name, hospital}` | `201` device + a **one-time** bearer token; key pair is generated, private key stays server-side only |
| POST | `/devices/{id}/revoke` | admin token | — | device with `revoked: true` |

Device: `{id, name, hospital, public_key_hex, revoked, created_at}` (create also returns `token`, once — see below).
`401` without a valid admin token; `MEDSEAL_ADMIN_TOKEN` unset means these two endpoints refuse every request.

**Device tokens.** `POST /devices` mints a random bearer token and returns it **only in that response**; only its
sha256 (`token_hash`) is stored. That token — not `device_id` — is what proves a request comes from a given
scanner gateway, so keep it as secret as the private key: never in a browser-exposed `NEXT_PUBLIC_*` var. The demo
gateway's device is created with `backend/scripts/create_demo_device.py` (bypasses HTTP, no admin token needed for
that one bootstrap step), and the frontend reads its token from a server-only env var — see `POST /seal` below.

## Seal
`POST /seal` — form: `file`; **`Authorization: Bearer <device token>`** — the device is resolved from the token,
there is no `device_id` field anymore (a client can no longer seal as an arbitrary device).
```json
{ "seal_id": 12, "uid": "1.3.6.1...", "device_id": 1, "tiles": 256, "tile": 32,
  "shape": [512, 512], "root": "9f2c…", "created_at": "2026-09-26T10:00:00Z",
  "download_url": "/api/seal/12/file", "seal_ms": 0.7 }
```
- `401` missing/invalid device token, `403` the device is revoked.
- Sealing the same image again returns the existing seal (same `seal_id`).
- `409` if the image ID is already sealed with different pixels, or (P1-03) if an image with no ID is a partial content match of an already-sealed image ("Image is derived from sealed image #N").
- `root` is 64 hex chars; show a short form in the UI (e.g. first 8 + "…").
- The frontend never talks to this endpoint directly: `by_billy/frontend/src/app/api/seal/route.ts` is a Next.js
  route handler that adds the token server-side from `MEDSEAL_DEVICE_TOKEN` (see `by_billy/frontend/.env.example`).

### Changed in audit remediation (P1-01): the gateway simulator requires Basic Auth
`/seal` (the page) and `/api/seal`, `/api/crash-test`, `/api/passport` (the Next.js route handlers) require
`Authorization: Basic <base64(user:password)>`, checked in `by_billy/frontend/src/proxy.ts` (first) and again inside
each route handler (`by_billy/frontend/src/lib/gatewayAuth.ts`, defence in depth). Credentials come from server-only
env vars `MEDSEAL_GATEWAY_USER` / `MEDSEAL_GATEWAY_PASSWORD` (see `by_billy/frontend/.env.example`) — unset means
those routes refuse every request with `503` (fail closed, never open). Wrong credentials → `401` with
`WWW-Authenticate: Basic realm="MedSeal gateway"`. `/api/seal` also rejects bodies over 50 MB with `413`, checked
via the `Content-Length` header before the body is read. This protects the Next.js layer; `POST /seal` on the
Python backend still separately requires the device bearer token (P0-1) regardless.

`GET /seal/{id}/file` — sealed file to download: DICOM with patient tags removed (pixels unchanged) / PNG with `medseal_uid` chunk (pixels unchanged). **SEC-01:** requires a device bearer token *or* the admin token (`401` without one); the frontend's own `/api/seal/[id]/file` route handler forwards the device token server-side.
**For the demo, verify the downloaded file** — a PNG that never went through `/seal` has no `medseal_uid` and is always `unsigned`.

`GET /seals?limit=50` — latest seals (same shape as the `POST /seal` response, without `seal_ms`). **SEC-01:** same auth as the file download above (`401` without a device or admin token) — sealed files were previously listable by anyone.
`GET /ledger/check` (public — counts only) → `{ "ok": true, "entries": 12, "broken": [], "anchors_checked": 12, "anchor_mismatch": [] }` — walks the hash chain and (CRY-03) re-verifies every root-signed external anchor; `broken` lists rows whose stored content no longer matches their own `entry_hash`, `anchor_mismatch` lists row ids whose anchored `head_hash` no longer matches — this is what catches a full, internally-consistent chain rewrite that `broken` alone cannot.

## Verify
`POST /verify` — form: `file`
```json
{ "status": "authentic | tampered | unsigned | forged",
  "uid": "…", "device": "KT-01", "seal_id": 12,
  "changed_tiles": [[64,16],[64,32]], "tile": 32,
  "matched_by": "uid | content | null",
  "warning": "device_revoked_later",
  "patient_check": "matched | mismatch | not_available",
  "sealed_at": "2026-09-26T10:00:00Z",
  "blockchain": { "status": "anchored", "block": 6712345, "time": "2026-09-26T10:10:12Z",
                  "tx_hash": "0x…", "tx_url": "https://sepolia.etherscan.io/tx/0x…", "chain_id": 11155111 },
  "verify_ms": 1.1,
  "preview_png": "base64…",
  "detective": { "probability": 0.87, "experimental": true },
  "shield": { "attack_suspected": false, "score": 3.64, "threshold": 10.42 },
  "note": "Final decision is made by the doctor." }
```
- `changed_tiles`: `[y, x]` of the top-left corner of each changed tile, in original image pixels; tile size is `tile`. `preview_png` already has red-outer/white-inner boxes drawn on them (visible in greyscale mode too; preview is scaled down to max 1024 px).
- `unsigned`: `uid`, `device`, `seal_id`, `tile` are `null`.
- `forged`: extra field `reason` = `ledger_entry_modified | bad_signature | device_revoked | unknown_device | untrusted_device | blockchain_mismatch` (**CRY-02**: `untrusted_device` = the device has no valid root-signed certificate — a forged device row or a swapped public key). `changed_tiles` is empty (tiles are not compared against an untrusted record).
- **CRY-01 patient binding:** `patient_check` = `"matched"` (the upload's DICOM PatientID hashes to the same `patient_ref` the seal was made with), `"mismatch"` (an authentic-looking image attached to the wrong patient — the response is `status: "tampered", reason: "patient_mismatch"` even though every tile and pixel is untouched), or `"not_available"` (no PatientID on the upload, no `MEDSEAL_PATIENT_SALT` configured, or the row predates `sig_version` 2 and was never bound to a patient).
- **CRY-02 migration:** `warning` can also be `"device_not_certified"` (only when `MEDSEAL_REQUIRE_DEVICE_CERT=0`; a seal from an as-yet-uncertified device that would otherwise be `untrusted_device`).
- **IMG-05:** for a DICOM whose `Modality` is not `CR`/`DX` (e.g. a CT slice), `detective` and `shield` are both `null` and the response carries `"ai_note": "not_applicable"` — the bundled models are chest X-ray only and must not silently score images outside that domain.
- `sealed_at` (on `authentic`/`tampered`): when the image was sealed — together with `device` it exposes a replayed old image (threat T6).
- `blockchain` (docs/BLOCKCHAIN.md): `null` when anchoring is off on the backend or the image is `unsigned`. Otherwise `status` =
  - `anchored` — the ledger entry matches the Merkle root stored on-chain (read from the chain, not our DB); `block`, `time` (on-chain block time), `tx_hash`, `tx_url` (explorer link, `null` on a local chain), `chain_id`.
  - `pending` — sealed after the last batch; anchored within ~10 min (`POST /anchors/run` in the demo).
  - `unavailable` — the chain could not be reached; the seal check above still stands.
  - `mismatch` — **critical**: our database was rewritten after anchoring (`detail: "proof_missing"` if the proof itself was deleted). Always comes with `status: "forged"`, `reason: "blockchain_mismatch"`, even when every local check passed — an insider with the database and the device keys can fool those, not the chain. Show the Etherscan link: the original fingerprint and time are there.
- `tampered` can also carry `reason: "metadata_changed"` + `changed_meta: [tag names]` when a display-affecting DICOM tag (RescaleSlope/Intercept, WindowCenter/Width, Laterality, PixelSpacing, ...) was edited without touching any pixel — those tags never touch tile hashes, so they are bound into the signature separately (P0-5).
- `warning` (optional, on `authentic`/`tampered` only) = `device_revoked_later`: the device was revoked **after** this particular seal was made, so the seal itself is still trusted — revocation is not retroactive. A seal made at/after the device's `revoked_at` is `forged`/`device_revoked` instead, not a warning.
- **P1-03 content-based recovery.** `matched_by` = `"uid"` (the normal case: the record was found by the image's own ID), `"content"` (the ID was missing, stripped or replaced — the record was found instead by comparing pixels against every previously sealed image of the same shape/dtype), or `null` (`unsigned` only — no match at all). On a `"content"` match: all tiles and metadata identical → `authentic` + `warning: "seal_id_missing"` (an untouched image whose ID chunk was dropped, e.g. by a re-save that strips PNG text chunks); anything different → `tampered` + `reason: "seal_id_removed"` + `changed_tiles` computed against the matched record. `POST /seal` also refuses (`409`) to seal an ID-less image that is a partial (not exact) content match of something already sealed — that would otherwise let an attacker strip the ID, edit the image, and get a brand-new "clean" seal for a forged derivative.
- `detective` key is present only when `status == "unsigned"` (a sealed image is checked by the seal, exactly). `detective` / `shield` are `null` when the AI is off (`MEDSEAL_AI=0`, torch not installed, detective not trained) — the UI must handle `null` for both.
- `detective.probability` = chance the image was edited (0..1). The public verification response intentionally does not include Grad-CAM/heatmap output; it remains available to training evaluation code only. `experimental` is currently always `true`: the detector has not been validated on real, non-synthetic forgeries. ~50 ms; the first call after startup ~1 s.
- `shield` runs on every status, including `authentic`: the seal proves where the image came from, the shield checks whether its pixels carry an adversarial attack (an attacked image can be sealed too).
- `shield.score` is a distance, not a percentage (clean X-rays ≈ 3–8, attacked ≈ 10–100+); `attack_suspected = score > threshold`. Show it as "Yashirin hujum aniqlandi" / "Shubhali shovqin topilmadi" plus `score / threshold`, not as "87%". About 1% of clean images raise a false alarm, so it is a warning, not a verdict. Takes ~50 ms (first call after startup ~2 s: model load).
- UI labels: `authentic`/`tampered`/`forged` are certain ("Tasdiqlangan"); `detective` is a probability ("Ehtimollik 87%"), `shield` is a warning (see above).

## Blockchain anchoring
`GET /anchors` → `{ "enabled": true, "pending": 3, "anchors": [ {id, root, count, tx_hash, tx_url, block, chain_id, onchain_index, status, created_at}, … ] }` (newest first; `enabled: false` = anchoring off).
`POST /anchors/run` — admin token. Anchors every pending seal now, waits for the confirmation (local chain: instant; Sepolia ~15 s). → `{ "anchored": 5, "anchor": {…} }` or `{ "anchored": 0, "anchor": null }`; `503` if anchoring is off or the chain is unreachable (sealing and verifying keep working).

## Audit log
`GET /audit?limit=200&action=seal` — admin token. Newest first: `[{id, at, action, actor, target, result, ip}]`.
`action` = `seal | verify | device_create | device_revoke | anchor | auth_failed`; `actor` = `admin`, `device:<name>`, `anonymous`, `inbox:upload|folder`, `patient-qr`, `scheduler`. There is no endpoint that changes or deletes audit rows.

## Automation (no clicks)
Folders (backend setting `MEDSEAL_WATCH_DIR`, default `data/watch`), polled every 2 s while the backend runs (`MEDSEAL_WATCH=0` turns it off):
- `scanner/` — the X-ray machine drops files here → sealed by the gateway device `Shlyuz-Auto` → sealed copy moved to `incoming/`.
- `incoming/` — images arriving at the doctor → verified → inbox. Done files go to `<folder>/processed/`, unreadable ones to `failed/`.

`GET /automation` → `{watching, scanner_dir, incoming_dir, interval_s, gateway, sealed, verified, failed, last_event: {at, text} | null, warmup}`
`POST /automation/run` → process both folders now → `{sealed, verified}`

## Inbox (doctor)
`POST /inbox` — multipart, field `files` (repeat, max 50) → the new items, most urgent first. The
frontend's batch-check flow posts one file at a time (same endpoint, one-element `files` each call)
so it can show real per-file progress and bucket results as they land, instead of waiting for the
whole batch in one request.

`GET /inbox?limit=200&offset=0&severity=&reviewed=&since=&until=` →
```json
{ "counts": { "danger": 0, "warning": 1, "ok": 4, "total": 5 },
  "volume": { "today": 5, "week": 5, "all": 5 },
  "items": [ /* item, see below */ ] }
```
- `counts` are over **unreviewed** items only (the doctor's actual work queue); order: unreviewed, then danger → warning → ok, then newest.
- `volume` is a raw activity count (checks that finished, any severity) for the summary tiles — today (last 24h), this week (last 7d), all-time.
- `since`/`until` — plain `YYYY-MM-DD`, inclusive, filtering on `received_at`; `422` for anything else. `offset`/`limit` — plain pagination, `limit` capped at 500.

`GET /inbox/{id}` → item + `result` (the full `/verify` response, or `{error}` for unreadable files) · `POST /inbox/{id}/review` → item with `reviewed: true`.
```json
{ "id": 7, "file_name": "patient_A.png", "source": "upload | folder", "received_at": "…",
  "status": "authentic | tampered | unsigned | forged | error", "severity": "danger | warning | ok",
  "reasons": ["tampered" | "forged" | "attack_suspected" | "unsigned" | "unreadable" | "device_revoked_later"],
  "reviewed": false, "device": "Shlyuz-Auto", "changed_tiles": 0, "detective_probability": null, "error": null }
```
- danger = tampered / forged / shield attack / unreadable; warning = unsigned (detective gives a probability) or device revoked later; ok = authentic and shield quiet.

`GET /inbox/{id}/pdf?lang=uz|ru` → one-page PDF report for this check (same content as the detail
view: status, severity, reasons, device, changed tiles, detective probability, the rendered preview
with its red boxes, and the doctor-decides note).
`POST /inbox/batch-pdf?lang=uz|ru` — body `{ids: [7, 8, 9]}` (max 50) → one PDF, one page per id, in
the given order. `404` if any id does not exist (nothing is generated for a partially-valid batch).

## Client cabinet (hospital/clinic, org-level)

A separate role from the doctor: an org-level login for the hospital that owns the devices, not for
one doctor. Scoped to exactly one `hospital` string (the same free-text value already stored on
`Device.hospital` and `Passport.organisation`) — a client account can only ever see its own
organisation's devices, stats, alerts and passports.

`POST /clients` — admin token, body `{hospital}` → `201` `{id, hospital, created_at, token}` — the
bearer token is returned **only in this response**; only its sha256 is stored, exactly like a device
token (`POST /devices`). `409` if a client account for that hospital already exists.

Every endpoint below requires `Authorization: Bearer <client token>`, or the admin token **plus**
`?org=<hospital>` (the admin token may inspect any organisation, but must name it — it never
defaults to "everything"). `401` without a valid token, `400` for the admin token with no `org`.

`GET /client/devices` → `[{id, name, revoked, certified, created_at, last_seal_at, seal_count}]` — this
organisation's own devices only. `certified` = the device has a valid root-signed certificate (CRY-02).

`GET /client/stats` →
```json
{ "hospital": "…",
  "devices": { "total": 3, "active": 2, "revoked": 1, "certified": 2 },
  "seals": { "today": 4, "7d": 21, "total": 130 },
  "verifications": { "total": 40, "by_result": { "authentic": 35, "tampered": 3, "forged": 2 } } }
```
`verifications` counts only checks of this organisation's **own** sealed images (joined on the seal's
`uid`) — a doctor elsewhere checking someone else's image never counts toward these numbers.

`GET /client/alerts?limit=50` → `[{at, seal_id, uid, device, result, shield_flag}]` — newest first, only
non-`authentic` outcomes for this organisation's own sealed images (tampered / forged checks elsewhere).

`GET /client/passports` → same summary shape as `GET /passports`, filtered to
`Passport.organisation == hospital`. Issuing a passport (`POST /passport`, admin-only) still sets
`organisation` explicitly — matching a client account's hospital name is what makes it visible here.

## Public QR check (patients, no login)
`POST /seal` also returns `check_token` (random, not the seal id). Frontend page: `/check/{check_token}`.
`GET /check/{token}` → `{status: "valid" | "warning" | "invalid", reason, hospital, device, sealed_at, shape}` — no image, no patient data. 404 unknown token.
`POST /check/{token}` — form `file` → `{status: "authentic" | "tampered" | "forged" | "unsigned" | "mismatch", reason, changed_tiles, preview_png}` (`mismatch` = a different image than the one behind this QR).
`GET /check/{token}/qr.png?url=<the check page URL>` → QR PNG (url must be http(s) and contain the token).

## Models
`GET /models` → `[{id, name, version, source, intended_use}]` — the built-in torchxrayvision DenseNet is created on startup; it is the only model that can be crash-tested.

## Crash test
`POST /crash-test` — `Authorization: Bearer <MEDSEAL_ADMIN_TOKEN>` — `{model_id, n_images: 50, eps: [0.5,1,2,4], method: "fgsm" | "pgd"}` → `202 {job_id}`
- **P1-04:** admin-only (`401` without the admin token) — the frontend calls its own `POST /api/crash-test` route handler
  (Basic Auth + `MEDSEAL_ADMIN_TOKEN` added server-side), never the backend directly. Reading endpoints below stay public.
- Defaults as shown; `n_images` 1–200, each eps in (0, 16] pixel units. Errors: 404 unknown model, 400 not the built-in model, 422 bad input, 503 AI modules not installed.
- One job runs at a time; 50 images with PGD take ~80 s on a laptop CPU. Poll `GET /crash-test/{job_id}` every ~1 s.

`GET /crash-test/{job_id}` while running:
```json
{ "job_id": 3, "model_id": 1, "created_at": "2026-09-25T10:00:00Z",
  "status": "queued | running | error", "progress": 0.6, "error": "only when status = error" }
```
when done:
```json
{ "job_id": 3, "model_id": 1, "created_at": "…", "status": "done", "progress": 1.0,
  "n_requested": 50, "n_images": 50, "protocol_compliant": true,
  "method": "pgd", "pathology": "Pneumonia", "data": ["nih/normal"],
  "eps": [0.5, 1, 2, 4],
  "flip_rate": {"0.5": 0.32, "1": 0.98, "2": 1.0, "4": 1.0},
  "psnr": {"0.5": 54.7, "1": 50.0, "2": 47.9, "4": 45.0},
  "example": { "eps": 1, "before_png": "base64…", "after_png": "…", "before_score": 0.08, "after_score": 0.93 },
  "robustness_score": 0.2,
  "duration_s": 79.7 }
```
- `eps` always contains `1` (added if missing): the score is `round(10 × (1 − flip_rate["1"]), 1)`.
- `flip_rate` / `psnr` keys are eps formatted without trailing zeros (`"0.5"`, `"1"`, `"2"`). PSNR in dB: > 40 means the noise is invisible to the eye.
- Images are adult chest X-rays (NIH) the model reads as healthy; `data` lists the folders they came from (`nih/normal`, or `samples` when the dataset is not downloaded); a "flip" = the attack pushed the Pneumonia score above 0.5.
- `n_requested` vs `n_images`: fewer images than requested may have been available/healthy — always show both, never just the smaller number silently.
- **P1-04** `protocol_compliant` = `method == "pgd" and n_images >= 50 and 1 in eps` — the exact rule `POST /passport` enforces (see below). A job below this bar can still be inspected but cannot become a passport.
- A job interrupted by a server restart returns `status: "error"`.

`GET /crash-tests?model_id=1` → finished tests, newest first, same fields as "done" but without `example`.

## Passport
`POST /passport` — `Authorization: Bearer <MEDSEAL_ADMIN_TOKEN>` — `{model_id, crash_test_id?, organisation?}` → `201` passport JSON
- **P1-04:** admin-only (`401` without the admin token) — the frontend calls its own `POST /api/passport` route handler,
  same as crash tests above. Reading endpoints below stay public.
- `crash_test_id` defaults to the model's latest finished crash test. `organisation` = responsible organisation (free text, may be empty).
- Errors: 404 unknown model / crash test of another model, 409 no finished crash test yet, **409 crash test does not meet
  the passport protocol** (`PROTOCOL = {method: "pgd", min_images: 50, eps_required: [1]}` — see `protocol_compliant` above;
  message states what was required vs what the crash test actually had).
- A passport is frozen at issue time: later seals, verifications or crash tests do not change it. Issue a new one to refresh.

`GET /passport/{id}` → passport JSON · `GET /passports?model_id=1` → summaries `[{id, created_at, organisation, verdict, conditions, model, robustness_score}]`, newest first
`GET /passport/{id}/pdf?lang=uz|ru` → one-page A4 PDF (download; `Content-Disposition: attachment`). Default `uz`.
`GET /passport/{id}/verify` (public) → `{"valid": bool, "fingerprint": "…"}` — see CRY-04 below.

```json
{ "id": 1, "created_at": "2026-09-25T06:33:20Z", "organisation": "Namangan viloyat shifoxonasi",
  "model": { "id": 1, "name": "torchxrayvision DenseNet121", "version": "densenet121-res224-all", "source": "https://…", "intended_use": "…" },
  "robustness": { "score": 0.2, "formula": "10 × (1 − flip rate at eps = 1 px)", "crash_test_id": 1, "tested_at": "…",
                  "n_images": 50, "method": "pgd", "pathology": "Pneumonia", "data": ["nih/normal"],
                  "flip_rate": {"0.5": 0.32, "1": 0.98, "2": 1.0, "4": 1.0}, "psnr": {"0.5": 54.7, "1": 50.0, "2": 47.9, "4": 45.0},
                  "example": { "eps": 1, "before_png": "base64…", "after_png": "base64…", "before_score": 0.07, "after_score": 0.78 } },
  "clinical_validation": null,
  "shield": { "available": true, "compatible": true, "method": "median 3x3, L1 distance of DenseNet logits", "threshold": 10.419,
              "false_positive_rate": 0.009, "detection_pgd_eps1": 1.0, "detection_fgsm_eps1": 0.619, "calibrated_on": "NIH ChestX-ray14 …",
              "confidence_intervals": { "detection_pgd_eps1": { "successes": 29, "n": 29, "lower": 0.880555, "upper": 1.0 }, "false_positive_rate": { "successes": 4, "n": 450, "lower": 0.002427, "upper": 0.022602 } },
              "adaptive_attack_tested": false },
  "pipeline": { "devices_active": 1, "seals": 12, "verifications": 30, "tampered_or_forged": 4, "ledger_ok": true },
  "verdict": "allowed_with_conditions",
  "conditions": ["clinical_validation_required", "shield_required", "seal_required", "doctor_decides"],
  "rules": { "allow_score": 7.0, "shield_min_detection": 0.9, "shield_max_false_alarms": 0.02 },
  "protocol": { "method": "pgd", "min_images": 50, "eps_required": [1] },
  "fingerprint": "a1b2c3d4e5f60718",
  "verify_url": "/api/passport/1/verify",
  "note": "Final decision is made by the doctor." }
```
- `verdict` is a research robustness assessment, not a regulatory or clinical permission. Codes remain `allowed` / `allowed_with_conditions` / `not_allowed` for API stability; display text must say what the measured thresholds mean. The current decision rules are built from `rules` and are not a clinical validation.
- `shield.compatible` = catches ≥ 90% PGD attacks at eps 1 px with ≤ 2% false alarms **(point estimate, decided under AI-01 — see `ARCHITECTURE.md`)**. `confidence_intervals` are shown next to it but do not gate `compatible`. If the shield is not calibrated: `{"available": false, "compatible": false}` only.
- `conditions` are codes; texts go in the frontend dictionary (the PDF has the same texts in `backend/app/passport/i18n.py`):
  - `clinical_validation_required` (**AI-02**) — `clinical_validation` is `null`; a research score alone cannot reach `allowed`, only `allowed_with_conditions` at best
  - `shield_required` — every image passes the MedSeal shield before the model
  - `seal_required` — images sealed at capture and verified before the model
  - `doctor_decides` — the model only advises; the doctor makes the diagnosis
  - `retest_required` — retrain the model against attacks and re-run the crash test
- `clinical_validation`: `null`, or once populated, `{dataset, n, auc, sensitivity, specificity}`. **AI-02:** `allowed` is only reachable when this is non-null.
- `robustness.example` may be `null` (older crash tests).
- **CRY-04:** `fingerprint` (first 16 hex chars of the sha256 of the root-signed message) and `verify_url` are on every passport. `GET /passport/{id}/verify` → `{"valid": bool, "fingerprint": "…"}` — `valid: false` means the stored `report_json` no longer matches what was actually signed at issue time (e.g. edited directly in the database). Both the PDF and the passport page show the fingerprint and this path.

## Stats
`GET /stats` → `{sealed, verified, authentic, tampered, unsigned, forged, models_tested, avg_robustness}` (`avg_robustness` is `null` until a crash test has run)

`GET /health` → `{ "ok": true }`

## Changed in audit remediation

Everything below was added or changed against the pre-audit API; each item is also documented
inline above, in context. Collected here as one changelog per HYG-04.

**New auth requirements**
- `GET /seal/{id}/file`, `GET /seals` — now require a device or admin bearer token (SEC-01).
- `POST /crash-test`, `POST /passport` — now require the admin bearer token (P1-04).

**New/changed fields on `POST /verify`**
- `matched_by`: `"uid" | "content" | null` (P1-03).
- `warning`: added `"seal_id_missing"`, `"device_not_certified"` (P1-03, CRY-02) alongside the
  existing `"device_revoked_later"`.
- `reason` (on `forged`): added `"untrusted_device"` (CRY-02).
- `reason` (on `tampered`): added `"seal_id_removed"` (P1-03), `"patient_mismatch"` (CRY-01).
- `patient_check`: `"matched" | "mismatch" | "not_available"`, new field (CRY-01).
- `ai_note`: `"not_applicable"`, new field, `detective`/`shield` both `null` alongside it (IMG-05).
- `phi_warning`: `"burned_in_annotation"`, new field on `POST /seal` and `POST /verify` (IMG-03).
- `changed_meta`: list of changed metadata tag names alongside `reason: "metadata_changed"` (P0-5/IMG-04, tag set widened to `META_TAGS_V2` including DICOM overlay planes).
- `detective.heatmap_png` removed from this public response (P1-05); `detective.experimental` is now always `true`.

**`GET /ledger/check`**: response gained `anchors_checked`, `anchor_mismatch` (CRY-03); `ok`
is now `false` if either the hash chain or an anchor fails.

**`POST /passport` response / `GET /passport/{id}`**
- `clinical_validation`: `null` or `{dataset, n, auc, sensitivity, specificity}`, new field; new
  condition code `clinical_validation_required` (AI-02).
- `shield.confidence_intervals`, `shield.adaptive_attack_tested`: new fields (AI-01).
- `fingerprint`, `verify_url`: new fields; new endpoint `GET /passport/{id}/verify` (CRY-04).
- `protocol_compliant` on crash-test results, and the `409` "does not meet the passport
  protocol" refusal on `POST /passport`: new (P1-04).

**Removed**: nothing was removed from the public surface except `detective.heatmap_png`
(above) — every other change is additive.
