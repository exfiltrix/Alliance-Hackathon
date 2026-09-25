# MedSeal — API (FastAPI, prefix `/api`)

All image uploads: `multipart/form-data`, field `file` (DICOM `.dcm` or `.png`). Images returned as base64 PNG previews (no `data:` prefix — use `data:image/png;base64,${preview_png}`).
Interactive docs while the backend runs: http://localhost:8000/docs. CORS allows `http://localhost:3000`.

Errors: `{"detail": "message"}` with status `404` (not found), `409` (conflict), `413` (file too large, > 50 MB), `415` (not a DICOM/PNG), `422` (missing/invalid field).
All times are UTC ISO strings: `"2026-09-26T10:00:00Z"`.

## Devices
| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/devices` | — | list of devices |
| POST | `/devices` | `{name, hospital}` | `201` device; key pair is generated, private key stays server-side only |
| POST | `/devices/{id}/revoke` | — | device with `revoked: true` |

Device: `{id, name, hospital, public_key_hex, revoked, created_at}`

## Seal
`POST /seal` — form: `file`, `device_id`
```json
{ "seal_id": 12, "uid": "1.3.6.1...", "device_id": 1, "tiles": 256, "tile": 32,
  "shape": [512, 512], "root": "9f2c…", "created_at": "2026-09-26T10:00:00Z",
  "download_url": "/api/seal/12/file", "seal_ms": 0.7 }
```
- Sealing the same image again returns the existing seal (same `seal_id`).
- `409` if the image ID is already sealed with different pixels, or the device is revoked. `404` unknown device.
- `root` is 64 hex chars; show a short form in the UI (e.g. first 8 + "…").

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
  "verify_ms": 1.1,
  "preview_png": "base64…",
  "detective": { "probability": 0.87, "heatmap_png": "base64…" },
  "shield": { "attack_suspected": false, "score": 0.03, "threshold": 0.11 },
  "note": "Final decision is made by the doctor." }
```
- `changed_tiles`: `[y, x]` of the top-left corner of each changed tile, in original image pixels; tile size is `tile`. `preview_png` already has red boxes drawn on them (preview is scaled down to max 1024 px).
- `unsigned`: `uid`, `device`, `seal_id`, `tile` are `null`.
- `forged`: extra field `reason` = `ledger_entry_modified | bad_signature | device_revoked | unknown_device`; `changed_tiles` is empty (tiles are not compared against an untrusted record).
- `detective` key is present only when `status == "unsigned"`. `detective` and `shield` are `null` until the AI modules are connected — the UI must handle `null`.
- UI labels: `authentic`/`tampered`/`forged` are certain ("Tasdiqlangan"); `detective` and `shield` are probabilities ("Ehtimollik 87%").

## Models
`GET /models` → `[{id, name, version, source, intended_use}]` — the built-in torchxrayvision DenseNet is created on startup; it is the only model that can be crash-tested.

## Crash test
`POST /crash-test` — `{model_id, n_images: 50, eps: [0.5,1,2,4], method: "fgsm" | "pgd"}` → `202 {job_id}`
- Defaults as shown; `n_images` 1–200, each eps in (0, 16] pixel units. Errors: 404 unknown model, 400 not the built-in model, 422 bad input, 503 AI modules not installed.
- One job runs at a time; 50 images with PGD take ~40 s on a laptop CPU. Poll `GET /crash-test/{job_id}` every ~1 s.

`GET /crash-test/{job_id}` while running:
```json
{ "job_id": 3, "model_id": 1, "created_at": "2026-09-25T10:00:00Z",
  "status": "queued | running | error", "progress": 0.6, "error": "only when status = error" }
```
when done:
```json
{ "job_id": 3, "model_id": 1, "created_at": "…", "status": "done", "progress": 1.0,
  "n_images": 50, "method": "pgd", "pathology": "Pneumonia",
  "eps": [0.5, 1, 2, 4],
  "flip_rate": {"0.5": 0.96, "1": 1.0, "2": 1.0, "4": 1.0},
  "psnr": {"0.5": 57.5, "1": 56.0, "2": 52.6, "4": 48.1},
  "example": { "eps": 1, "before_png": "base64…", "after_png": "…", "before_score": 0.08, "after_score": 0.93 },
  "robustness_score": 0.0,
  "duration_s": 41.6 }
```
- `eps` always contains `1` (added if missing): the score is `round(10 × (1 − flip_rate["1"]), 1)`.
- `flip_rate` / `psnr` keys are eps formatted without trailing zeros (`"0.5"`, `"1"`, `"2"`). PSNR in dB: > 40 means the noise is invisible to the eye.
- Images are ones the model reads as healthy; a "flip" = the attack pushed the Pneumonia score above 0.5.
- A job interrupted by a server restart returns `status: "error"`.

`GET /crash-tests?model_id=1` → finished tests, newest first, same fields as "done" but without `example`.

## Passport
`POST /passport` — `{model_id, crash_test_id}` → passport JSON
`GET /passport/{id}` → passport JSON · `GET /passport/{id}/pdf` → PDF

## Stats
`GET /stats` → `{sealed, verified, authentic, tampered, unsigned, forged, models_tested, avg_robustness}` (`avg_robustness` is `null` until a crash test has run)

`GET /health` → `{ "ok": true }`
