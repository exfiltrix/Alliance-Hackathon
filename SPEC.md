# MedSeal — product spec

## Problem

Hospitals are starting to trust AI to read X-rays and CT scans. Both the image and the AI can be fooled invisibly:

- **CT-GAN (USENIX Security 2019):** fake lung tumors were injected into / removed from CT scans. Radiologists who were not warned saw cancer in 99% of injected scans and missed it in 94% of scans where it had been removed; a lung-cancer screening AI was fooled in every test.
- **Radiology (RSNA), March 2026:** 17 radiologists from 6 countries; when not warned, only 41% spotted AI-generated X-rays. The authors recommend cryptographic signatures at capture and invisible watermarks.
- **Adversarial attacks:** invisible noise can flip a medical AI's diagnosis (Finlayson et al., 2019).
- **Uzbekistan:** the state is rolling out AI for chest CT/X-ray and breast screening through 2026. Task №6 says ethics and safety standards for this are missing.

## Users

| User | Need |
|---|---|
| Radiologist / doctor | Know the image in front of them is real |
| Hospital IT / chief physician | Know which AI models are safe to use |
| AI vendor | Get a robustness certificate ("passport") for their model |
| Ministry of Health | One standard and one dashboard for all AI pilots |

## Pages and acceptance criteria

### 1. Seal (`/seal`) — imitates the scanner gateway
- Upload DICOM or PNG, choose a device (e.g. "KT-01, Namangan viloyat shifoxonasi").
- Result: seal ID, time, number of tiles, short root hash, "Muhrlandi" (sealed) badge.
- Download the sealed file (DICOM unchanged; PNG gets a `medseal_uid` text chunk, pixels unchanged).
- ✅ Sealing a 512×512 image takes < 50 ms on a laptop.

### 2. Verify (`/verify`)
- Upload any image. Three possible outcomes:
  - **Authentic** (green): signature valid, all tiles match.
  - **Tampered** (red): image shown with red boxes on changed tiles + "Snimok suratga olingandan keyin o'zgartirilgan".
  - **Unsigned** (grey): no seal found → run the AI detective → probability + heatmap, clearly labelled as a probability.
- Also runs the AI shield: "Yashirin hujum aniqlandi" (hidden attack detected) if adversarial noise is suspected.
- ✅ Detects a single changed pixel. ✅ Rejects a ledger record edited without the private key.

### 3. Crash test (`/crash-test`)
- Choose a model (at least the built-in torchxrayvision DenseNet) and the number of test images.
- Shows a live "before / after" pair: healthy image → model says "Pneumonia" after invisible noise.
- Chart: % of flipped diagnoses vs attack strength. Final robustness score 0–10.
- ✅ Runs on 50 images in < 2 minutes on CPU.

### 4. Model passport (`/passport/[id]`)
- Model name/version, intended use, robustness score, shield compatibility, protection status of image pipeline, verdict: *Allowed / Allowed with conditions / Not allowed*, responsible organisation.
- Export to PDF.

### 5. Dashboard (`/dashboard`) — optional
- Images sealed / verified / tampered, models tested with scores, map or list by hospital.

## Out of scope for the hackathon
Real scanner integration, real hospital data, user accounts beyond a simple demo login, HSM key storage (describe it in the pitch instead).
