# MedSeal — 3-day plan

Rule: at the end of every day the demo must run end-to-end, even if parts are stubbed.

## Roles
1. **Backend + crypto** — seal, verify, ledger, devices, API.
2. **AI** — model loader, attacks, shield, detective, passport numbers.
3. **Frontend** — 4 pages + dashboard, Uzbek/Russian strings.
4. **Data + design** — datasets, fake images, UI polish, demo images.
5. **Pitch** — slides, script, backup video, jury Q&A.

## Day 1 — skeleton that works
- [ ] (1) FastAPI app, SQLite tables, `/devices`, `/seal`, `/verify` ported from `reference/medseal_poc.py`
- [ ] (1) pytest: round-trip, 1-pixel change, forged ledger rejected
- [ ] (2) load torchxrayvision, `predict()` returns pathology scores for a PNG/DICOM
- [ ] (2) FGSM on one image flips "Pneumonia" — save before/after PNG
- [ ] (3) Next.js app, pages `/seal` and `/verify` calling the API, red-box preview
- [ ] (4) download public chest X-rays; pick 10 demo images; make 3 convincing fakes
- [ ] (5) pitch outline: patient story → threat → demo → standard → business

## Day 2 — all features
- [ ] (1) PNG `medseal_uid` chunk, hash-chain ledger, `/stats`
- [ ] (2) crash test job over 50 images, flip rate per eps, robustness score
- [ ] (2) shield: calibrate threshold on clean images, flag attacked ones
- [ ] (2) detective: `scripts/make_fakes.py`, train ResNet18, Grad-CAM (keep a fallback: if accuracy is poor, show it as "experimental")
- [ ] (3) pages `/crash-test`, `/passport/[id]`, PDF export, `/dashboard`
- [ ] (4) UI polish, icons, colors (green/red/grey states)
- [ ] (5) slides draft, rehearsal #1

## Day 3 — demo quality
- [ ] everyone: run `docs/DEMO.md` 3 times end-to-end, fix whatever breaks
- [ ] (1) deploy (one VM or a laptop + QR code), seed demo data
- [ ] (3) loading states, error messages, mobile-friendly verify page
- [ ] (5) record backup video of the full demo; final slides; Q&A practice

## Useful prompts for Claude Code
- "Port `reference/medseal_poc.py` into `backend/app/seal/` as a module with functions `seal_image`, `verify_image`; add pytest tests for the three scenarios in the reference."
- "Implement `POST /api/verify` per `docs/API.md`, returning a PNG preview with red rectangles on changed tiles."
- "Implement targeted FGSM and PGD in `backend/app/ai/attacks.py` for the torchxrayvision DenseNet, target class 'Pneumonia', eps given in 0–255 pixel units."
- "Implement feature squeezing in `backend/app/ai/shield.py` and a calibration script that sets the threshold at the 95th percentile on clean images."
- "Build the Next.js page `/verify` with drag-and-drop upload and three result states (authentic / tampered / unsigned) per `docs/SPEC.md`."
