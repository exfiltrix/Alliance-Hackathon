# MedSeal — demo script (≈ 3 minutes)

## 0. Hook (20 s)
"A healthy person was told they have cancer — because of one fake image. In 2026 the journal *Radiology* showed: when not warned, only 41% of radiologists noticed AI-generated X-rays."

## 1. Seal (30 s)
Open `/seal` → upload a real chest X-ray → "Muhrlandi" + seal ID.
Say: "In a hospital this happens automatically next to the scanner."

## 2. Spot the fake (40 s)
Show two images side by side, ask the jury: "Which one is fake?"
Upload the fake to `/verify` → red banner + red boxes exactly where the nodule was added.
Then upload the original → green "Tasdiqlangan".

## 3. Attack on the AI (40 s)
Open `/crash-test` → before/after: healthy X-ray, AI says ~8% pneumonia → after invisible noise ~93%.
Show the shield on `/verify`: "Yashirin hujum aniqlandi".

## 3b. Even we can't cheat (30 s)
Before the demo (local chain, no internet needed): run `./demo.sh` in the repo root instead of the usual backend command —
it starts the local blockchain, deploys the contract and the backend, and anchors new seals every 15 s by itself.
Seal the original (step 1) at least 15 s before this step.

On stage: play the insider who has our database AND the device keys:
`cd backend && .venv/bin/python -m scripts.rewrite_history_demo <seal_id> --image <fake>.png` — it re-signs the fake into the ledger and repairs the hash chain ("local ledger check: clean").
Upload the fake to `/verify` again → red **"Soxta muhr yozuvi"**: "the database no longer matches the blockchain record" (without the chain it would now say "Tasdiqlangan").
Say: "Nobody can rewrite the history of seals — not a hacker, not a hospital, not us."

Pitfalls:
- The script really rewrites that seal — use a fresh seal for every rehearsal.
- Keep `./demo.sh` running until the demo is over: the local chain lives in its memory. After a restart the backend re-anchors old seals by itself within 15 s.

## 4. Passport (20 s)
Open the model's passport: robustness score, verdict, PDF.
Say: "This is the standard task №6 asks for: every AI model gets a passport before it touches patients."

## 5. Close (30 s)
Who pays: AI vendors (certification), hospitals (image protection), Ministry (one standard for all AI pilots).
Growth: pilot hospital → all regions → Central Asia.

## Backup
- Laptop runs everything locally, no internet needed.
- Recorded video of the full flow on the desktop.

## Jury Q&A
| Question | Answer |
|---|---|
| Where is the AI? | Detective (finds fakes without a seal), crash test (AI attacks AI), shield (blocks hidden attacks). The seal itself is math — that's why it's 100% certain. |
| What if the key is stolen? | Keys live only in the gateway (hardware module in production), can be revoked and rotated. |
| Old images? | Archive can be sealed once from today; the detective covers images without a seal. |
| Does it slow doctors down? | Seal/verify takes milliseconds per image. |
| Does this already exist? | The science exists and *Radiology* recommends signatures at capture; we found no product that combines seal + detective + crash test + passport, and nothing in Uzbekistan. |
| Why blockchain, not just a database? | A database can be edited by its admin. The chain holds the fingerprint where no one, including us, can change it. Only hashes go on-chain — no patient data. |
| How secure is it? | Standard primitives: SHA-256 (FIPS 180-4), Ed25519 (FIPS 186-5), TLS 1.3; 12-point threat model; we just showed four attacks being caught live. |
| Legal side? | No patient names stored, data stays in Uzbekistan, AI only advises — the doctor decides. |
