# MedSeal — API (FastAPI, prefix `/api`)

All image uploads: `multipart/form-data`, field `file` (DICOM `.dcm` or `.png`). Images returned as base64 PNG previews (no `data:` prefix — use `data:image/png;base64,${preview_png}`).
Interactive docs while the backend runs: http://localhost:8000/docs. CORS allows `http://localhost:3000`.

Errors: `{"detail": "message"}` with status `404` (not found), `409` (conflict), `413` (file too large, > 50 MB), `415` (not a DICOM/PNG), `422` (missing/invalid field).
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

`GET /seal/{id}/file` — sealed file to download: DICOM with patient tags removed (pixels unchanged) / PNG with `medseal_uid` chunk (pixels unchanged).
**For the demo, verify the downloaded file** — a PNG that never went through `/seal` has no `medseal_uid` and is always `unsigned`.

`GET /seals?limit=50` — latest seals (same shape as the `POST /seal` response, without `seal_ms`).
`GET /ledger/check` → `{ "ok": true, "entries": 12, "broken": [] }` — walks the hash chain; `broken` lists rewritten ledger rows.

## Verify
`POST /verify` — form: `file`
```json
{ "status": "authentic | tampered | unsigned | forged",
  "uid": "…", "device": "KT-01", "seal_id": 12,
  "changed_tiles": [[64,16],[64,32]], "tile": 32,
  "matched_by": "uid | content | null",
  "warning": "device_revoked_later",
  "verify_ms": 1.1,
  "preview_png": "base64…",
  "detective": { "probability": 0.87, "experimental": true },
  "shield": { "attack_suspected": false, "score": 3.64, "threshold": 10.42 },
  "note": "Final decision is made by the doctor." }
```
- `changed_tiles`: `[y, x]` of the top-left corner of each changed tile, in original image pixels; tile size is `tile`. `preview_png` already has red boxes drawn on them (preview is scaled down to max 1024 px).
- `unsigned`: `uid`, `device`, `seal_id`, `tile` are `null`.
- `forged`: extra field `reason` = `ledger_entry_modified | bad_signature | device_revoked | unknown_device`; `changed_tiles` is empty (tiles are not compared against an untrusted record).
- `tampered` can also carry `reason: "metadata_changed"` + `changed_meta: [tag names]` when a display-affecting DICOM tag (RescaleSlope/Intercept, WindowCenter/Width, Laterality, PixelSpacing, ...) was edited without touching any pixel — those tags never touch tile hashes, so they are bound into the signature separately (P0-5).
- `warning` (optional, on `authentic`/`tampered` only) = `device_revoked_later`: the device was revoked **after** this particular seal was made, so the seal itself is still trusted — revocation is not retroactive. A seal made at/after the device's `revoked_at` is `forged`/`device_revoked` instead, not a warning.
- **P1-03 content-based recovery.** `matched_by` = `"uid"` (the normal case: the record was found by the image's own ID), `"content"` (the ID was missing, stripped or replaced — the record was found instead by comparing pixels against every previously sealed image of the same shape/dtype), or `null` (`unsigned` only — no match at all). On a `"content"` match: all tiles and metadata identical → `authentic` + `warning: "seal_id_missing"` (an untouched image whose ID chunk was dropped, e.g. by a re-save that strips PNG text chunks); anything different → `tampered` + `reason: "seal_id_removed"` + `changed_tiles` computed against the matched record. `POST /seal` also refuses (`409`) to seal an ID-less image that is a partial (not exact) content match of something already sealed — that would otherwise let an attacker strip the ID, edit the image, and get a brand-new "clean" seal for a forged derivative.
- `detective` key is present only when `status == "unsigned"` (a sealed image is checked by the seal, exactly). `detective` / `shield` are `null` when the AI is off (`MEDSEAL_AI=0`, torch not installed, detective not trained) — the UI must handle `null` for both.
- `detective.probability` = chance the image was edited (0..1). The public verification response intentionally does not include Grad-CAM/heatmap output; it remains available to training evaluation code only. `experimental` is currently always `true`: the detector has not been validated on real, non-synthetic forgeries. ~50 ms; the first call after startup ~1 s.
- `shield` runs on every status, including `authentic`: the seal proves where the image came from, the shield checks whether its pixels carry an adversarial attack (an attacked image can be sealed too).
- `shield.score` is a distance, not a percentage (clean X-rays ≈ 3–8, attacked ≈ 10–100+); `attack_suspected = score > threshold`. Show it as "Yashirin hujum aniqlandi" / "Shubhali shovqin topilmadi" plus `score / threshold`, not as "87%". About 1% of clean images raise a false alarm, so it is a warning, not a verdict. Takes ~50 ms (first call after startup ~2 s: model load).
- UI labels: `authentic`/`tampered`/`forged` are certain ("Tasdiqlangan"); `detective` is a probability ("Ehtimollik 87%"), `shield` is a warning (see above).

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

```json
{ "id": 1, "created_at": "2026-09-25T06:33:20Z", "organisation": "Namangan viloyat shifoxonasi",
  "model": { "id": 1, "name": "torchxrayvision DenseNet121", "version": "densenet121-res224-all", "source": "https://…", "intended_use": "…" },
  "robustness": { "score": 0.2, "formula": "10 × (1 − flip rate at eps = 1 px)", "crash_test_id": 1, "tested_at": "…",
                  "n_images": 50, "method": "pgd", "pathology": "Pneumonia", "data": ["nih/normal"],
                  "flip_rate": {"0.5": 0.32, "1": 0.98, "2": 1.0, "4": 1.0}, "psnr": {"0.5": 54.7, "1": 50.0, "2": 47.9, "4": 45.0},
                  "example": { "eps": 1, "before_png": "base64…", "after_png": "base64…", "before_score": 0.07, "after_score": 0.78 } },
  "shield": { "available": true, "compatible": true, "method": "median 3x3, L1 distance of DenseNet logits", "threshold": 10.419,
              "false_positive_rate": 0.009, "detection_pgd_eps1": 1.0, "detection_fgsm_eps1": 0.619, "calibrated_on": "NIH ChestX-ray14 …" },
  "pipeline": { "devices_active": 1, "seals": 12, "verifications": 30, "tampered_or_forged": 4, "ledger_ok": true },
  "verdict": "allowed_with_conditions",
  "conditions": ["shield_required", "seal_required", "doctor_decides"],
  "rules": { "allow_score": 7.0, "shield_min_detection": 0.9, "shield_max_false_alarms": 0.02 },
  "protocol": { "method": "pgd", "min_images": 50, "eps_required": [1] },
  "note": "Final decision is made by the doctor." }
```
- `verdict` is a research robustness assessment, not a regulatory or clinical permission. Codes remain `allowed` / `allowed_with_conditions` / `not_allowed` for API stability; display text must say what the measured thresholds mean. The current decision rules are built from `rules` and are not a clinical validation.
- `shield.compatible` = catches ≥ 90% PGD attacks at eps 1 px with ≤ 2% false alarms. If the shield is not calibrated: `{"available": false, "compatible": false}` only.
- `conditions` are codes; texts go in the frontend dictionary (the PDF has the same texts in `backend/app/passport/i18n.py`):
  - `shield_required` — every image passes the MedSeal shield before the model
  - `seal_required` — images sealed at capture and verified before the model
  - `doctor_decides` — the model only advises; the doctor makes the diagnosis
  - `retest_required` — retrain the model against attacks and re-run the crash test
- `robustness.example` may be `null` (older crash tests).

## Stats
`GET /stats` → `{sealed, verified, authentic, tampered, unsigned, forged, models_tested, avg_robustness}` (`avg_robustness` is `null` until a crash test has run)

`GET /health` → `{ "ok": true }`
