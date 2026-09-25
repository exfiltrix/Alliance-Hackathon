# MedSeal — frontend context for Claude Code

Frontend part (`by_billy/frontend/`). Project-wide context, commands and invariants: `../CLAUDE.md`.

**MedSeal** (Uzbek UI name: *Muhr*, "seal") — a web platform that protects medical images (X-ray, CT) and medical AI from tampering.
Built for the National AI Hackathon (Namangan, 2026), track "Medicine", official task №6
(AI ethics and safety standards for X-ray/CT analysis).

One-line pitch: *"A seal and an antivirus for medical images: we prove an image is authentic and that the AI reading it can't be fooled."*

## What the product does

1. **Seal** — signs an image at capture: tiles → SHA-256 → Merkle root → Ed25519 signature → append-only ledger.
2. **Verify** — checks an image before a doctor/AI sees it: authentic / tampered (with tile-level location) / unsigned / forged record.
3. **AI detective** — for unsigned images: a CNN estimates tampering probability and shows a heatmap.
4. **Crash test** — attacks a medical AI model (FGSM/PGD) and scores its robustness 0–10.
5. **AI shield** — detects adversarial noise before an image reaches the diagnostic AI (feature squeezing).
6. **Model passport** — a one-page report per AI model (robustness score, protection status, verdict), exportable to PDF.

Detailed docs (repo root): `docs/SPEC.md`, `docs/ARCHITECTURE.md`, `docs/API.md` (the backend contract), `docs/DEMO.md`, `docs/BLOCKCHAIN.md`, `docs/SECURITY.md`.
Working, tested reference for the seal logic: `reference/medseal_poc.py`.

## Stack

- **Backend:** Python 3.11+, FastAPI, pydicom, numpy, cryptography (Ed25519), Pillow, OpenCV, SQLite (SQLAlchemy)
- **AI:** PyTorch (CPU is fine), torchxrayvision (pretrained chest X-ray DenseNet), torchvision
- **Frontend:** Next.js (App Router) + TypeScript + Tailwind
- **Tests:** pytest (backend), minimal Playwright smoke test (frontend, optional)

## Repository layout

```
backend/
  app/
    main.py            # FastAPI app, routers
    seal/              # hashing, merkle, signing, ledger
    verify/            # verification + tile diff heatmap
    ai/
      model.py         # torchxrayvision loader + predict()
      attacks.py       # FGSM / PGD
      shield.py        # feature squeezing detector
      detective.py     # tamper-detection CNN + Grad-CAM
    passport/          # report builder + PDF export
    db.py, models.py   # SQLite tables
  tests/
  scripts/             # data prep, fake generation, detective training
by_billy/frontend/      # Next.js 16: src/app/{seal,verify,inbox,check,crash-test,passport,dashboard}
contracts/             # MedSealAnchor smart contract (Hardhat)
docs/
data/                  # public/synthetic images only (gitignored)
reference/medseal_poc.py
```

## Commands

```bash
# backend
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
pytest -q

# frontend
cd by_billy/frontend && npm install && cp .env.example .env.local && npm run dev   # http://localhost:3000
npx tsc --noEmit -p . && npm run lint   # types + lint (also run by the pre-commit hook and CI)
```

## Rules

- **Data:** use only public datasets and synthetic images. Never commit real patient data. Strip DICOM patient tags (PatientName, PatientID, BirthDate…) on upload before storing anything.
- **Crypto code is the core — keep it exact:**
  - hash input per tile = `f"{uid}|{y}|{x}|{shape}|{dtype}"` + raw tile bytes (as in the reference);
  - never change the hashing format without updating tests and re-sealing demo data;
  - private keys never leave the "gateway" module and are never logged or returned by the API.
- **Honesty in the UI:** the seal gives a certain answer; the detective and shield give probabilities. Always label them differently ("Tasdiqlangan" vs "Ehtimollik 87%").
- **AI never decides alone:** every AI verdict in the UI says the final decision is the doctor's.
- **UI language:** Uzbek (Latin) by default, Russian as a switch. Keep strings in one dictionary file.
- **Priority for the hackathon:** a demo that works end-to-end beats extra features. Before adding anything, make sure the demo flow in `docs/DEMO.md` still runs.
- Write tests for: seal/verify round-trip, 1-pixel change detection, forged-ledger rejection, attack flips prediction, shield flags attacked images.
