# MedSeal

**A seal and an antivirus for medical images: we prove an X-ray or CT scan is authentic, and that the AI reading it cannot be fooled.**

*Muhr va antivirus tibbiy tasvirlar uchun. · Печать и антивирус для медицинских снимков.*

National AI Hackathon (Namangan, 2026) · track "Medicine" · official task №6 — ethics and safety standards for AI that reads X-ray and CT.

## The problem

- Fake tumours can be injected into or removed from CT scans; unwarned radiologists and a screening AI were fooled almost every time (CT-GAN, USENIX Security 2019).
- When not warned, only 41% of radiologists spotted AI-generated X-rays (*Radiology*, 2026). The authors recommend cryptographic signatures at capture.
- Invisible noise can flip a medical AI's diagnosis (adversarial attacks).
- Uzbekistan is rolling out AI for chest X-ray and CT; task №6 says the safety standard for it is missing.

## What MedSeal does

| Module | What it gives | Certainty |
|---|---|---|
| **Seal** | Signs an image at capture: tiles → SHA-256 → Merkle root → Ed25519 signature → append-only ledger | exact (cryptography) |
| **Verify** | Before a doctor or an AI sees an image: *authentic* / *tampered* (down to the 32×32 tile) / *unsigned* / *forged record* | exact |
| **Blockchain anchor** | Every 10 min the ledger's Merkle root goes to a smart contract: nobody — a hacker, the hospital or us — can rewrite the history of seals | exact |
| **AI detective** | For unsigned images: probability that the image was edited (ResNet18) | probability |
| **AI shield** | Flags adversarial noise before the image reaches the diagnostic AI (feature squeezing) | warning |
| **Crash test** | Attacks a medical AI (FGSM / PGD) and scores its robustness 0–10 | measured |
| **Model passport** | One page per AI model: robustness, protection status, verdict, PDF | rules |
| **Automation** | Scanner folder → sealed automatically; incoming folder → verified into the doctor's inbox (urgent first); QR code for the patient | — |

The seal gives an exact answer; the detective and the shield give probabilities, and the UI always says so. Every AI verdict carries the note that the final decision is the doctor's. UI in Uzbek (default), Russian and English.

## Measured, not promised

| | Result |
|---|---|
| Seal / verify, 512×512 | ≈ 1 ms each (2048×2048: ≈ 16 ms) |
| Change detected | a single pixel changed by 1 |
| Shield | 0.9% false alarms on clean adult X-rays; PGD attacks caught 100% at ε ≥ 1 px, FGSM 62% / 87% / 100% at ε 1 / 2 / 4 |
| Detective | AUC 0.94 on 1000 held-out images; finds ~8 of 10 edits (all removals); 8.4% false alarms — shown only as a probability |
| Robustness score | `round(10 × (1 − share of diagnoses flipped at ε = 1 px), 1)` |

Sources: `backend/app/ai/shield_calibration.json`, `backend/app/ai/detective_metrics.json`, `backend/tests/`.

## How it works

```
 scanner ──► SEAL (gateway)                                     doctor / AI
             tiles → SHA-256 → Merkle root → Ed25519 ──► ledger ──► VERIFY ──► result + red boxes
                                                        │  (hash chain)  │
                                     every 10 min: batch Merkle root     ├─ shield  (every image)
                                                        ▼                └─ detective (unsigned only)
                                              MedSealAnchor contract  ◄── root read from the chain,
                                              (append-only, hashes only)   not from our database
```

- Each tile hash binds the image ID, tile position, shape and dtype: moving, cropping or swapping images is caught.
- The ledger is a hash chain; editing a row without the device key breaks the signature.
- An insider with the database **and** the device keys can re-sign a fake and repair the chain — every local check passes. The root anchored on the blockchain still remembers the original, so verification says *forged: blockchain mismatch*.
- Only hashes go on-chain — never images, never patient data. DICOM patient tags are stripped on upload.

## Security

Standard primitives (SHA-256 FIPS 180-4, Ed25519 RFC 8032) and a 12-point threat model — [docs/SECURITY.md](docs/SECURITY.md). Every threat marked ✅ has a test that performs the attack and checks it is caught; a test fails if a new threat is added without one (`backend/tests/test_threats.py`). Also: append-only audit log, security headers, rate limiting, decompression-bomb limits, secrets only in `.env`.

Honest limits: an image altered *before* the seal (a compromised scanner) is not caught by the seal — that is why the gateway sits next to the scanner and the detective exists. The detective and the shield are probabilistic, not proofs.

## Run it

Requirements: Python 3.11+ (developed on 3.14), Node.js 20+.

```bash
# backend
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# optional AI modules (crash test, shield, detective; CPU is enough)
.venv/bin/pip install -r requirements-ai.txt --extra-index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m scripts.fetch_samples          # public X-rays + model weights
.venv/bin/python -m scripts.fetch_dataset && .venv/bin/python -m scripts.train_detective   # detective, ~20 min

# everything for the demo in one command: local blockchain + contract + backend on :8000
cd .. && ./demo.sh

# frontend (second terminal) — http://localhost:3000
cd by_billy/frontend && npm install && cp .env.example .env.local && npm run dev
```

Works offline: the blockchain runs locally (Hardhat). For a public testnet (Sepolia) put an RPC URL and a funded key in `backend/.env` — see `backend/.env.example`.

Tests: `cd backend && .venv/bin/pytest` · `cd contracts && npx hardhat test` · frontend `npx tsc --noEmit && npm run lint`. They also run on every commit (`git config core.hooksPath .githooks`) and on GitHub Actions.

## Repository

```
backend/            FastAPI: seal/, verify/, anchor/ (blockchain), ai/, passport/, automation/; tests/, scripts/
by_billy/frontend/  Next.js 16 + TypeScript + Tailwind, uz / ru / en
contracts/          MedSealAnchor smart contract (Solidity) + tests + deploy script
docs/               SPEC, ARCHITECTURE, API, BLOCKCHAIN, SECURITY, DEMO, TASKS
reference/          the original proof of concept the seal was ported from
demo.sh             one-command demo
```

Data: public datasets only (NIH ChestX-ray14, CC0; Kermany pediatric X-rays) and synthetic forgeries. No real patient data is stored in the repository.
