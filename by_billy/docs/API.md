# Muhr — API (FastAPI, prefix `/api`)

All image uploads: `multipart/form-data`, field `file` (DICOM `.dcm` or `.png`). Images returned as base64 PNG previews.

## Devices
| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/devices` | — | list of devices |
| POST | `/devices` | `{name, hospital}` | device + generated key pair (private key saved server-side only) |

## Seal
`POST /seal` — form: `file`, `device_id`
```json
{ "seal_id": 12, "uid": "1.3.6.1...", "device_id": 1, "tiles": 256,
  "root": "9f2c…", "created_at": "2026-09-26T10:00:00Z",
  "download_url": "/api/seal/12/file" }
```
`GET /seal/{id}/file` — sealed file (DICOM unchanged / PNG with `muhr_uid` chunk).

## Verify
`POST /verify` — form: `file`
```json
{ "status": "authentic | tampered | unsigned | forged",
  "uid": "…", "device": "KT-01",
  "changed_tiles": [[64,16],[64,32]],
  "preview_png": "base64…",
  "detective": { "probability": 0.87, "heatmap_png": "base64…" },
  "shield": { "attack_suspected": false, "score": 0.03, "threshold": 0.11 },
  "note": "Final decision is made by the doctor." }
```
`detective` is present only when `status == "unsigned"`.

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
`GET /stats` → `{sealed, verified, tampered, unsigned, models_tested, avg_robustness}`
