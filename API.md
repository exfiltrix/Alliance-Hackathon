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

## Crash test
`POST /crash-test` — `{model_id, n_images: 50, eps: [0.5,1,2,4], method: "fgsm" | "pgd"}` → `{job_id}`
`GET /crash-test/{job_id}`
```json
{ "status": "running | done", "progress": 0.6,
  "flip_rate": {"0.5": 0.12, "1": 0.48, "2": 0.9, "4": 1.0},
  "psnr": {"1": 52.1},
  "example": { "before_png": "…", "after_png": "…", "before_score": 0.08, "after_score": 0.93 },
  "robustness_score": 5.2 }
```

## Passport
`POST /passport` — `{model_id, crash_test_id}` → passport JSON
`GET /passport/{id}` → passport JSON · `GET /passport/{id}/pdf` → PDF

## Stats
`GET /stats` → `{sealed, verified, authentic, tampered, unsigned, forged, models_tested, avg_robustness}` (`avg_robustness` is `null` until a crash test has run)

`GET /health` → `{ "ok": true }`
