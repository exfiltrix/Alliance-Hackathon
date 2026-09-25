# MedSeal

MedSeal is a web platform that protects medical images (X-ray, CT) and the medical AI that
reads them from tampering. Built for the National AI Hackathon (Namangan, 2026), track
"Medicine", official task 6 (AI ethics and safety standards for X-ray/CT analysis).

One-line pitch: a seal and an antivirus for medical images — we cryptographically prove an
image has not changed since it was sealed, and we measure how easily the AI that reads it can
be fooled.

Six pieces, in one flow: **seal** an image at capture (tile hashes → Merkle root → Ed25519
signature → append-only ledger) → **verify** it before a doctor or AI sees it (authentic /
tampered / unsigned / forged) → an **AI detective** gives a probability for unsigned images →
a **crash test** attacks a chest X-ray model (FGSM/PGD) and scores its robustness 0–10 → an
**AI shield** flags adversarial noise before it reaches the model → a **model passport**
turns all of that into a one-page, PDF-exportable report. See root `SPEC.md` for the full page
list and acceptance criteria, `ARCHITECTURE.md` for the algorithms and data model, `API.md` for
the endpoint contracts, and `DEMO.md` for the stage script.

## Honest threat model

**What MedSeal actually protects against right now:**
- An image edited, cropped, or re-compressed after it was sealed (tile-level Merkle check).
- A ledger row edited directly in the database without the device's private key (Ed25519
  signature + hash-chain check).
- A forged device impersonating a certified device (root-signed device certificates, CRY-02).
- The image's seal ID being stripped or replaced to hide that an edited image is a derivative of
  a sealed one (content-based recovery by perceptual hash + tile overlap, P1-03).
- The whole hash chain being rewritten and re-linked consistently inside the database (external,
  root-signed anchor file outside the database, CRY-03).
- An adversarial (FGSM/PGD) perturbation reaching the diagnostic model undetected in most cases
  (feature-squeezing shield, calibrated at a 99th-percentile threshold — see the confidence
  intervals in every passport, not just the point estimate).

**What it explicitly does not protect against, and says so in the UI/PDF:**
- An attacker with the device's private key (the demo keeps it on the same host as the gateway
  simulator; production needs an HSM or a physically separate gateway).
- An adaptive attacker who knows the shield exists and optimises against it (AI-03, not
  implemented here — `adaptive_attack_tested: false` is shown everywhere the shield reports a
  result).
- A model that is simply bad at the clinical task: the robustness score is not a clinical
  validation. A passport can only reach `allowed` with a non-null `clinical_validation` block; a
  research-only crash test caps out at `allowed_with_conditions`.
- Anything about the AI detective beyond "experimental": it is trained on synthetic forgeries
  only (heatmap hits the actual edit in ≈4.8% of cases — close to chance) and is never the sole
  basis for a status shown to a user; the seal is the only certain signal.
- A doctor being wrong: every AI verdict in the UI and PDF states that the final decision is the
  doctor's.

## Quick start

### Backend

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
export MEDSEAL_ADMIN_TOKEN=dev-admin-token         # required for /devices, /revoke, /crash-test, /passport
.venv/bin/python -m scripts.create_root_key        # once: backend/keys/root.{pem,pub}
.venv/bin/python -m scripts.create_demo_device      # once: prints a device token for the frontend
.venv/bin/uvicorn app.main:app --reload --port 8000 # Swagger: http://localhost:8000/docs
```

### Frontend

```bash
cd by_billy/frontend
npm install
cp .env.example .env.local   # fill in MEDSEAL_DEVICE_TOKEN (from create_demo_device above),
                              # MEDSEAL_ADMIN_TOKEN, MEDSEAL_GATEWAY_USER/PASSWORD
npm run dev                  # http://localhost:3000  (development)
```

For the demo (and for `scripts/e2e_live.sh`) run the production build instead:

```bash
cd by_billy/frontend
npm run build && npm run start   # http://localhost:3000
```

`npm run start` listens on all interfaces, so a phone on the same Wi-Fi can open
`http://<your-lan-ip>:3000` (`ipconfig getifaddr en0`). The backend must allow that origin:
`MEDSEAL_CORS_ORIGIN_REGEX` already covers private `10./172.16-31./192.168.` addresses on port 3000.

Without a `MEDSEAL_GATEWAY_USER`/`PASSWORD`, the `/seal` page and its gateway API routes refuse
every request with `503` (fail closed, P1-01) rather than opening up. Without
`NEXT_PUBLIC_API_URL` and without `NEXT_PUBLIC_USE_MOCK=1`, API calls fail with an explicit
"backend is not configured" error instead of silently showing demo data.

### First-time setup order

1. `scripts.create_root_key` — creates the trust root once; refuses to overwrite an existing one.
2. `scripts.create_demo_device` — issues a device certified by that root key; prints a device
   token (shown once — copy it into the frontend's `.env.local`).
3. Set `MEDSEAL_ADMIN_TOKEN` (backend) and the matching frontend gateway/admin env vars.
4. `scripts.certify_devices` — only needed for a database created **before** device certificates
   existed (CRY-02): with `MEDSEAL_REQUIRE_DEVICE_CERT=1` (the default) an uncertified device makes
   its seals verify as `forged` / `untrusted_device`. Idempotent; prints
   `certified devices: 0` when everything is already certified, which is exactly what a fresh
   `create_demo_device` setup reports. Requires `MEDSEAL_ADMIN_TOKEN` in the environment.
5. Optional AI stack: see below.

### AI stack (shield, crash test, detective)

```bash
cd backend
.venv/bin/pip install -r requirements-ai.txt --extra-index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m scripts.fetch_samples    # data/samples: 2 X-rays + 1 DICOM + 1 JPG (~1 MB)
.venv/bin/python -m scripts.fetch_dataset    # data/nih + data/xray, ~231 MB, needed by the two below
```

`scripts.fetch_dataset` is a prerequisite, not an optional extra: `scripts.calibrate_shield` and
`scripts.train_detective` both read `data/nih` and exit with `No images in data/nih` without it.
`scripts.train_detective` takes roughly 20 minutes on a laptop CPU and writes
`weights/detective.pt` (gitignored) plus `app/ai/detective_metrics.json` (committed).

`scripts.calibrate_shield` and `scripts.train_detective` are only needed to **re-measure**: the
shield threshold and the detective's measured quality already ship with the repository, so a
normal demo run needs neither.

### Env vars

Backend (`backend/app/config.py`, all optional with the defaults shown; `MEDSEAL_ADMIN_TOKEN`
and `MEDSEAL_PATIENT_SALT` have no default on purpose — unset means the feature they gate is
off or refuses requests, never silently permissive):

| Variable | Default | Purpose |
|---|---|---|
| `MEDSEAL_DB_URL` | `sqlite:///backend/medseal.db` | SQLAlchemy database URL |
| `MEDSEAL_KEYS_DIR` | `backend/keys` | device private keys (gitignored) |
| `MEDSEAL_STORAGE_DIR` | `backend/storage` | sealed files served by `GET /seal/{id}/file` |
| `MEDSEAL_CORS_ORIGINS` | `localhost:3000` variants | comma-separated allowed origins |
| `MEDSEAL_CORS_ORIGIN_REGEX` | private-LAN `:3000` pattern | LAN demo access from a phone |
| `MEDSEAL_MAX_PIXELS` | `40000000` | pixel budget checked before decoding (SEC-03) |
| `MEDSEAL_DATA_DIR` | `../data` | public/synthetic datasets for crash tests |
| `MEDSEAL_AI` | `1` | `0` disables the shield/detective inside `/verify` |
| `MEDSEAL_ADMIN_TOKEN` | *(unset)* | bearer token for `/devices`, `/revoke`, `/crash-test`, `/passport` |
| `MEDSEAL_PATIENT_SALT` | *(unset)* | HMAC salt binding DICOM PatientID without storing it (CRY-01) |
| `MEDSEAL_ROOT_KEY_PATH` / `MEDSEAL_ROOT_PUBKEY_PATH` | `backend/keys/root.{pem,pub}` | trust root (CRY-02) |
| `MEDSEAL_REQUIRE_DEVICE_CERT` | `1` | `0` = migration mode: uncertified devices warn instead of failing verification |
| `MEDSEAL_ANCHOR_PATH` | `backend/anchors/anchors.jsonl` | external, root-signed ledger anchors (CRY-03) |
| `MEDSEAL_DETECTIVE_WEIGHTS` | `backend/weights/detective.pt` | trained detective CNN weights |

Frontend (`by_billy/frontend/.env.local`, see `.env.example`):

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_URL` | backend base URL the browser talks to |
| `NEXT_PUBLIC_USE_MOCK` | `1` = explicit demo-data mode; anything else requires a real backend |
| `MEDSEAL_BACKEND_URL` | server-only backend URL used by the Next.js route handlers |
| `MEDSEAL_DEVICE_TOKEN` | server-only device token, never sent to the browser |
| `MEDSEAL_ADMIN_TOKEN` | server-only admin token for the crash-test/passport route handlers |
| `MEDSEAL_GATEWAY_USER` / `MEDSEAL_GATEWAY_PASSWORD` | HTTP Basic Auth in front of `/seal` and the gateway API routes |

## Tests

```bash
cd backend
.venv/bin/pytest -m "not ai" -q   # fast gate, no torch/weights/data needed
.venv/bin/pytest -q               # full suite; AI-marked tests report SKIPPED without torch/weights/data
.venv/bin/python -m scripts.demo_smoke   # end-to-end smoke test against a temporary DB/keys/storage
```

```bash
cd by_billy/frontend
npm run lint
npm run build
```

## Live end-to-end check (HYG-05)

`scripts/demo_smoke.py` runs the whole pipeline in-process against a throwaway database.
`scripts/e2e_live.sh` proves the same thing over real HTTP against the two running servers, which
is what catches configuration mistakes (a stale device token, a `.env.local` pointing at the wrong
backend, a uvicorn left running against somebody else's database):

```bash
# terminal 1 - backend
cd backend && .venv/bin/uvicorn app.main:app --port 8000
# terminal 2 - frontend production build
cd by_billy/frontend && npm run build && npm run start
# terminal 3
cd backend && bash scripts/e2e_live.sh      # prints PASS/FAIL per check, exits non-zero on any FAIL
```

It reads the gateway credentials and the device token from `by_billy/frontend/.env.local`; every
value can be overridden through the environment (`MEDSEAL_GATEWAY_USER`, `MEDSEAL_GATEWAY_PASSWORD`,
`MEDSEAL_DEVICE_TOKEN`, `MEDSEAL_BACKEND_URL`, `MEDSEAL_FRONTEND_URL`). Check (e) runs a real
50-image PGD crash test, so allow it a few minutes (`MEDSEAL_E2E_CRASH_TIMEOUT`, default 1800 s).

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `/seal` uploads fail with 401 although the browser is authenticated | The device token in `.env.local` does not belong to a device in the database the backend is using. Re-mint it: `python -m scripts.create_demo_device`, then paste the printed token into `MEDSEAL_DEVICE_TOKEN`. |
| `/ledger/check` reports `anchor_mismatch` right after a fresh start | The database was reset or replaced but `backend/anchors/anchors.jsonl` was not. Anchors are append-only evidence kept outside the database, so move the stale file aside (`mv anchors/anchors.jsonl anchors/anchors.jsonl.old`) and seal again. |
| Old seals verify as `forged` / `untrusted_device` | The device predates device certificates. Run `python -m scripts.certify_devices` with `MEDSEAL_ADMIN_TOKEN` set. |
| `No images in data/nih` | `python -m scripts.fetch_dataset` has not been run. |
| `detective` is `null` in `/verify` | `weights/detective.pt` does not exist yet: run `python -m scripts.train_detective` (~20 min). Everything else (seal, verify, shield, crash test, passport) works without it. |
