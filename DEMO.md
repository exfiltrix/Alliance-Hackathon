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
| Where is the AI? | Detective (gives an experimental tampering probability for images without a seal), crash test (measures robustness against attacks), and shield (raises a warning for likely adversarial noise). The seal is a cryptographic integrity check; it is not a clinical diagnosis or a claim that the AI cannot be fooled. |
| What if someone deletes the image ID? | Verification searches same-shape/dtype records by a non-signed dHash and then requires at least half of the original tiles to match. A partial derivative is reported as tampered with `seal_id_removed`; an identical re-save is reported as authentic with a warning. In production, add indexed candidate search and rate limits. |
| Who can seal? | In this demo, the `/seal` page and its server-side gateway routes require HTTP Basic Auth, and the backend still requires a per-device bearer token. Production would put the signing key in a gateway/HSM next to the scanner and expose no browser form. |
| What if the server is hacked? | Today the demo root key is on the same host and a database write can still be dangerous; device certificates and external anchors detect more tampering, but this is not an HSM deployment. Production should keep the root key offline/HSM, use least-privilege services, and alert on anchor/device-certificate failures. |
| Is the shield robust to an attacker who knows about it? | The committed numbers test only attacks that do not know about the shield. We report that limitation and the confidence intervals; adaptive attacks were not established here, so the shield must remain a warning rather than a guarantee. |
| What if the key is stolen? | Keys live only in the gateway (hardware module in production), can be revoked and rotated. |
| Old images? | Archive can be sealed once from today; the detective covers images without a seal. |
| Does it slow doctors down? | Seal/verify takes milliseconds per image. |
| Does this already exist? | The science exists and *Radiology* recommends signatures at capture; we found no product that combines seal + detective + crash test + passport, and nothing in Uzbekistan. |
| Legal side? | No patient names stored, data stays in Uzbekistan, AI only advises — the doctor decides. |
