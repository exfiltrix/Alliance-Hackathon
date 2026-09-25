# MedSeal Audit Remediation Status

Last updated: 2026-09-25T15:42:52Z, from the results of the commit **before** this one:
`d54cf0b` — `HYG: reproducible dependencies, gitignore, smoke test, documentation (HYG-01..HYG-05)`.
This file describes that commit's state, not the working tree at the moment this file itself
is written (this file's own commit is `DOCS`-only and changes nothing else).

This is a handoff for the next session. It replaces an earlier version of this file that claimed
"build passed" without a fresh run on the then-current tree — that claim was false for the tree it
described. Every result below was produced by actually running the command in this session,
against `HEAD = d54cf0b`, after all edits to the files it covers.

## Repository state

- Branch: `fix/audit-2026-09`.
- Commits this round, in order: `7b0e61a` (SEC), `9e76f23` (IMG), `a2420b8` (CRY), `4b9b7cc` (AI),
  `d33e9e5` (FE), `d54cf0b` (HYG). Each commit message documents which task IDs it covers,
  including secondary ones for files that mix more than one phase (unavoidable without
  interactive staging, per this round's constraints — see each message's "Also contains" note).
- `git status --porcelain` is clean on `HEAD` except this file, which is committed separately
  right after this rewrite.
- No private keys, tokens, salts, `.env.local` files or `.pem`/`.db`/`anchors.jsonl`/`storage/`
  content were staged or committed; every staged diff this round was grepped for secret-shaped
  content before each commit (all clean).

## Gates on HEAD `d54cf0b` (real output, this session)

| Command | Result |
|---|---|
| `backend: pytest -m "not ai" -q` | **85 passed, 3 skipped, 1 deselected** |
| `backend: pytest -q` (full) | **85 passed, 4 skipped** (torch not installed; AI-marked tests report SKIPPED, not passed) |
| `backend: python -m scripts.demo_smoke` | **14/14 PASS** |
| `frontend: npm run lint` | clean |
| `frontend: rm -rf .next && npm run build` | clean, no TypeScript errors, no `any` introduced |
| Fresh throwaway venv (`pip install -r backend/requirements-dev.txt` + `pytest -m "not ai" -q`) | **85 passed, 3 skipped, 1 deselected** — same as the project's own `.venv` (HYG-01 verification) |

## Task review (this round's Step 4)

`TASK-ID | files | criteria met? | test(s) | gap`

| Task | Files | Met? | Test(s) | Gap |
|---|---|---|---|---|
| SEC-01 | `routers/seal.py` | yes | `test_sealed_files_and_list_require_auth` | — |
| SEC-02 | `ai/crash_test.py`, `routers/crash_test.py`, `main.py` | yes | `test_second_crash_test_while_running_returns_409` (new this round), `test_crash_test_job` (fixed a stale synchronous-completion assumption) | — |
| SEC-03 | `config.py`, `imaging.py` | yes | `test_oversized_png_header_is_rejected_before_decode` | — |
| SEC-04 | `ai/detective.py`, `ai/shield.py`, `ai/hooks.py`, `routers/common.py`, `routers/seal.py`, `routers/verify.py` | yes | `test_grad_cam_is_thread_safe` (new this round, AI-marked, **not executed in this environment** — no torch; report as written, not verified) | the concurrency claim for `detective.grad_cam` is unverified here; `shield.check`'s own lock has no dedicated concurrency test (only the detective one was in scope this round) |
| SEC-05 | `seal/ledger.py`, `db.py` | yes | `test_concurrent_seals_keep_the_ledger_intact` (new this round, 10 concurrent seals via threads) | the retry-on-`IntegrityError` path itself needs a multi-*process* race to trigger for real; the in-process lock makes that untestable from one pytest process — documented as a known limitation instead (`ARCHITECTURE.md` §6) |
| SEC-06 | `app/auth.py`, `ai/detective.py`, `requirements-ai.txt` | yes | `test_revoke_is_idempotent`, `test_admin_auth_rejects_non_ascii_without_500` | — |
| IMG-01 | `imaging.py`, `scripts/attack_demo.py`, `scripts/train_detective.py`, `scripts/calibrate_shield.py` | yes | `test_display_pixels_applies_intercept_and_inverts_monochrome1` | — |
| IMG-02 | `imaging.py` | yes | `test_png_la_alpha_only_edit_is_detected`, `test_16_bit_colour_png_is_rejected` | — |
| IMG-03 | `imaging.py` | yes | `test_strip_patient_tags_recurses_and_keeps_uid`, `test_dicom_seal_strips_patient_tags` | — |
| IMG-04 | `imaging.py`, `models.py` | yes | `test_v2_overlay_metadata_change_is_detected` | — |
| IMG-05 | `verify/service.py` | yes | `test_ai_is_not_applied_to_ct` | — |
| IMG-06 | `verify/preview.py` | yes | `test_changed_tile_box_has_red_outer_and_white_inner_strokes` | — |
| CRY-01 | `seal/signing.py`, `seal/service.py`, `seal/ledger.py`, `verify/service.py` | yes | `test_v2_signature_binds_created_at`, `test_v2_signature_binds_device_id`, `test_patient_reference_detects_wrong_patient`, `test_v1_seal_still_verifies_with_its_original_message_format` (new this round — no test previously exercised the `sig_version < 2` verification branch at all) | — |
| CRY-02 | `seal/keys.py`, `routers/devices.py`, `scripts/create_root_key.py`, `scripts/certify_devices.py` | yes | `test_replacing_device_key_is_untrusted`, `test_uncertified_device_is_rejected_or_warned_by_migration_mode`, `test_certify_devices_script_migrates_existing_seals_back_to_authentic` (new this round — runs the real migration script, not just the settings flag) | the local `backend/medseal.db` has 0 devices/seals, so the literal "migrate a copy of the real DB" instruction had nothing to migrate; the new test is the fixture-based fallback the instructions allow, and is stronger evidence than a one-off manual run since it is repeatable |
| CRY-03 | `seal/anchors.py`, `routers/seal.py` | yes | `test_anchor_detects_rewritten_but_rechained_row`, `test_ledger_hash_chain` | — |
| CRY-04 | `passport/signing.py`, `routers/passport.py` | yes | `test_issue_and_read` (fingerprint present, `/passport/{id}/verify` flips to `false` after editing `report_json`) | — |
| AI-01 | `ai/statistics.py`, `passport/report.py`, `shield_calibration.json` | yes (decided: point estimates, Option A) | `test_shield_compatible_uses_point_estimates_not_interval_bounds` (new this round), `test_statistics.py` (Clopper-Pearson correctness) | the stop-and-ask itself was previously skipped (decided implicitly in code, never actually put to the user); this round's follow-up order resolved it explicitly — see `AI:` commit body |
| AI-02 | `passport/report.py` | yes | `test_verdict_rules` (parametrised) | — |
| AI-03 | — | not done (explicitly out of scope this round) | — | no torch locally; listed as an open risk below |
| FE-01 | `dictionary.ts`, deleted login/register/`auth.ts` | yes | `npm run build` clean | — |
| FE-02 | `types.ts`, `dictionary.ts`, `mock.ts`, `verify/page.tsx` | yes | `npm run build` clean | found and fixed during this round's review: `ForgedReason`/`TamperedReason`/`warning` were missing `untrusted_device`, `patient_mismatch`, `device_not_certified`; `VerifyResponse` had no `patient_check`/`phi_warning` fields at all — see the `FE:` commit body |
| HYG-01 | `requirements*.txt` | yes | fresh throwaway venv install + `pytest -m "not ai" -q` (see gates table) | `requirements-ai.txt` stays on lower bounds (no local torch) with the exact pin command documented in its header, as the instructions allow |
| HYG-02 | `.gitignore` | yes | manual inspection | — |
| HYG-03 | deleted `by_billy/docs/`, `by_billy/CLAUDE.md`, `by_billy/reference/muhr_poc.py` | yes | grepped for references before committing the deletion (none found) | — |
| HYG-04 | `README.md`, `ARCHITECTURE.md`, `API.md`, `CLAUDE.md`, `DEMO.md` | yes | manual read-through against the actual code (not the spec) | — |
| HYG-05 | `scripts/demo_smoke.py` | yes | ran directly (see gates table) | — |

## Found during review, fixed this round (not part of the original audit list)

1. **Frontend build was red** on the tree this round started from: `imagesRequested`,
   `imagesLoaded`, `protocolLabel`, `protocolValue` were defined only in `dictionary.ts`'s
   `crash` section; `passport/[id]/page.tsx` reads `dictionary.passport`, which didn't have
   them. Fixed by adding them to `passport` too (kept in `crash` as well, since
   `crash-test/page.tsx` genuinely reads them from there).
2. **`tests/test_crash_test.py` was entirely skipped without torch**, including its two purely
   non-AI tests (auth requirement, input validation): it imported `SAMPLES`/`WEIGHTS` from
   `tests.test_ai` at module level, and `test_ai.py`'s own `pytest.importorskip("torch")`
   Skipped exception cascaded into it. Fixed by recomputing those two constants locally.
3. **No test exercised the `sig_version < 2` (pre-CRY-01) verification branch at all** — every
   seal created via the test API is freshly sealed as v2. Added a test that builds a genuine
   v1-format row with the frozen `core.seal()` and confirms it still verifies, and that a
   corrupted v1 signature is still caught by the v1-specific check.
4. **No test ran the actual CRY-02 migration script** (`scripts.certify_devices`) — only the
   `MEDSEAL_REQUIRE_DEVICE_CERT` settings flag was tested. Added a test that runs the script for
   real against an uncertified device and confirms its seal verifies `authentic` afterwards.
5. **Missing SEC-02/SEC-05 concurrency tests** the original audit order asked for. Added
   `test_second_crash_test_while_running_returns_409` and
   `test_concurrent_seals_keep_the_ledger_intact`.
6. **Frontend type/dictionary gaps**: the backend could already return `reason:
   "untrusted_device"`, `reason: "patient_mismatch"`, `warning: "device_not_certified"`, and
   `phi_warning: "burned_in_annotation"` with no frontend type, translation, or rendering for
   any of them. Fixed (see the `FE:` commit body).

## Migration commands (CRY-02, for an existing deployment)

```bash
cd backend
export MEDSEAL_ADMIN_TOKEN=<your admin token>
.venv/bin/python -m scripts.create_root_key      # once; refuses to overwrite an existing root key
.venv/bin/python -m scripts.certify_devices --authorization "Bearer $MEDSEAL_ADMIN_TOKEN"
```
Verified end-to-end against a fixture (not the real local DB, which has 0 devices/seals):
`tests/test_api.py::test_certify_devices_script_migrates_existing_seals_back_to_authentic`.
With `MEDSEAL_REQUIRE_DEVICE_CERT=1` (the default) after this migration, a previously-sealed
image from a now-certified device verifies `authentic` again; before running it, the same image
verifies `forged`/`untrusted_device`.

## Open risks (honest, as of `d54cf0b`)

1. **AI-03 not done.** No adaptive-attack evaluation; `adaptive_attack_tested: false` is shown
   everywhere the shield reports a result. No torch installed in this environment to do it.
2. **Demo root key on the same host** as everything else. Production needs it offline/HSM.
3. **No rate limiting** on any endpoint.
4. **Detective not validated on real forgeries** — synthetic-only metrics, `experimental: true`
   is hardcoded.
5. **SEC-04's `detective.grad_cam` thread-safety test is written but not executed** in this
   environment (no torch) — report it as unverified, not as passing.
6. **Single-process locks** (SEC-02's worker queue, SEC-05's ledger append) do not protect a
   multi-worker/multi-process deployment; see `ARCHITECTURE.md` §6.
7. **O(n) content-based seal recovery** (P1-03) — fine at demo scale, not indexed for production.
8. **Merkle tree has no leaf/node domain separation** — a known weakness class, deliberately
   unchanged because the tile/Merkle format is frozen; a future tile-format v2 would fix it.
