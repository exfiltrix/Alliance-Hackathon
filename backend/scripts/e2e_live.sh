#!/usr/bin/env bash
# HYG-05: live end-to-end check of the running demo — real HTTP, real servers, real database.
#
#   Backend : uvicorn app.main:app --port 8000        (from backend/)
#   Frontend: npm run build && npm run start          (from by_billy/frontend/, port 3000)
#
#   bash scripts/e2e_live.sh
#
# This is the HTTP twin of scripts/demo_smoke.py: demo_smoke proves the pipeline in-process
# against a throwaway database, this one proves the two processes a jury will actually see.
# It deliberately talks to the RUNNING servers instead of starting its own, so it also
# catches configuration mistakes (stale device token, wrong .env.local, a backend left
# running against the wrong database).
#
# Tools: curl for all HTTP, plus the backend's own .venv python for JSON parsing, for the
# PNG surgery in check (c) and for scripts/tamper_demo + scripts/attack_demo. Nothing is
# installed and no new dependency is needed.
set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BACKEND_DIR=$(dirname "$SCRIPT_DIR")
REPO_ROOT=$(dirname "$BACKEND_DIR")
PYTHON="${MEDSEAL_PYTHON:-$BACKEND_DIR/.venv/bin/python}"
ENV_LOCAL="$REPO_ROOT/by_billy/frontend/.env.local"
SAMPLES="$REPO_ROOT/data/samples"
SAMPLE="${MEDSEAL_E2E_SAMPLE:-00000001_000.png}"
UNRELATED_SAMPLE="${MEDSEAL_E2E_UNRELATED:-00027426_000.png}"
JPG_SAMPLE="${MEDSEAL_E2E_JPG:-16747_3_1.jpg}"

BACKEND="${MEDSEAL_BACKEND_URL:-http://127.0.0.1:8000/api}"
FRONTEND="${MEDSEAL_FRONTEND_URL:-http://127.0.0.1:3000}"
CRASH_TIMEOUT="${MEDSEAL_E2E_CRASH_TIMEOUT:-1800}"

PASS_COUNT=0
FAIL_COUNT=0
FAILED_CHECKS=()

# ---------------------------------------------------------------- helpers
say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
pass() { PASS_COUNT=$((PASS_COUNT + 1)); printf '  \033[32mPASS\033[0m %s\n' "$*"; }
fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  FAILED_CHECKS+=("$*")
  printf '  \033[31mFAIL\033[0m %s\n' "$*"
}
note() { printf '  \033[33mNOTE\033[0m %s\n' "$*"; }
check() {  # check <label> <expected> <actual>
  if [ "$2" = "$3" ]; then pass "$1 ($3)"; else fail "$1: expected [$2], got [$3]"; fi
}
check_in() {  # check_in <label> <allowed-a> <allowed-b> <actual>
  case "$4" in
    "$2"|"$3") pass "$1 ($4)" ;;
    *) fail "$1: expected [$2] or [$3], got [$4]" ;;
  esac
}
code() { curl -s -o /dev/null -w '%{http_code}' -m 60 "$@"; }
env_local() {  # value of KEY in .env.local, surrounding quotes stripped
  [ -f "$ENV_LOCAL" ] || return 0
  sed -n "s/^$1=//p" "$ENV_LOCAL" | tail -n 1 | tr -d "\"'"
}
jget() {  # jget <json-file> <python expression over d> -> value
  "$PYTHON" -c '
import json, sys
d = json.load(open(sys.argv[1]))
try:
    v = eval(sys.argv[2])
except Exception as e:
    v = "<missing: %s>" % e
print(v if not isinstance(v, (dict, list)) else json.dumps(v))
' "$1" "$2" 2>/dev/null
}
verify() {  # verify <file>: POST /verify, answer in $WORK/verify.json
  VERIFY_CODE=$(curl -s -o "$WORK/verify.json" -w '%{http_code}' -m 300 -F "file=@$1" "$BACKEND/verify")
}
has_basic_challenge() { printf '%s' "$1" | tr -d '\r' | grep -qi '^www-authenticate:[[:space:]]*Basic'; }

WORK=$(mktemp -d "${TMPDIR:-/tmp}/medseal-e2e.XXXXXX")
trap 'rm -rf "$WORK"' EXIT

GATEWAY_USER=${MEDSEAL_GATEWAY_USER:-$(env_local MEDSEAL_GATEWAY_USER)}
GATEWAY_PASS=${MEDSEAL_GATEWAY_PASSWORD:-$(env_local MEDSEAL_GATEWAY_PASSWORD)}
DEVICE_TOKEN=${MEDSEAL_DEVICE_TOKEN:-$(env_local MEDSEAL_DEVICE_TOKEN)}
AUTH_OK=(-u "$GATEWAY_USER:$GATEWAY_PASS")
AUTH_BAD=(-u "$GATEWAY_USER:not-the-configured-password")

printf '\033[1mMedSeal live end-to-end check\033[0m\n'
printf 'backend  : %s\nfrontend : %s\npython   : %s\nworkdir  : %s\n' "$BACKEND" "$FRONTEND" "$PYTHON" "$WORK"

# ---------------------------------------------------------------- 0. preflight
say "0. Preflight: both servers are up and configured"
if [ -x "$PYTHON" ]; then pass "backend virtualenv python found"; else
  fail "backend virtualenv python not found at $PYTHON"
  printf '\nAborting: the checks need the backend environment.\n'
  exit 2
fi
check "GET $BACKEND/health" "200" "$(code "$BACKEND/health")"
check "GET $FRONTEND/ (home page)" "200" "$(code "$FRONTEND/")"
if [ -n "$GATEWAY_USER" ] && [ -n "$GATEWAY_PASS" ]; then
  pass "gateway credentials found in $(basename "$ENV_LOCAL")"
else
  fail "MEDSEAL_GATEWAY_USER/PASSWORD are not set (and not found in $ENV_LOCAL)"
fi
if [ -n "$DEVICE_TOKEN" ]; then
  pass "gateway device token found in $(basename "$ENV_LOCAL")"
else
  fail "MEDSEAL_DEVICE_TOKEN is not set (and not found in $ENV_LOCAL) - mint one with scripts.create_demo_device.py"
fi
if [ -f "$SAMPLES/$SAMPLE" ]; then pass "sample $SAMPLE present"; else
  fail "sample $SAMPLES/$SAMPLE missing - run python -m scripts.fetch_samples"
fi

# ---------------------------------------------------------------- a. gateway auth (P1-01)
say "a. Gateway HTTP Basic Auth: /seal and /api/seal"
H=$(curl -s -D - -o /dev/null -m 30 "$FRONTEND/seal")
check "GET /seal without credentials" "401" "$(printf '%s' "$H" | head -1 | awk '{print $2}')"
if has_basic_challenge "$H"; then pass "GET /seal sends 'WWW-Authenticate: Basic'"; else
  fail "GET /seal without credentials did not send a WWW-Authenticate: Basic header"
fi
H=$(curl -s -D - -o /dev/null -m 30 -X POST "$FRONTEND/api/seal")
check "POST /api/seal without credentials" "401" "$(printf '%s' "$H" | head -1 | awk '{print $2}')"
if has_basic_challenge "$H"; then pass "POST /api/seal sends 'WWW-Authenticate: Basic'"; else
  fail "POST /api/seal without credentials did not send a WWW-Authenticate: Basic header"
fi
check "GET /seal with a wrong password" "401" "$(code "${AUTH_BAD[@]}" "$FRONTEND/seal")"
check "POST /api/seal with a wrong password" "401" "$(code "${AUTH_BAD[@]}" -X POST "$FRONTEND/api/seal")"
check "GET /seal with the right credentials" "200" "$(code "${AUTH_OK[@]}" "$FRONTEND/seal")"

# ---------------------------------------------------------------- b. seal -> download -> verify
say "b. Seal a real X-ray through :3000, download it, verify it on the backend"
cp "$SAMPLES/$SAMPLE" "$WORK/input.png"
SEAL_CODE=$(curl -s -o "$WORK/seal.json" -w '%{http_code}' -m 120 "${AUTH_OK[@]}" \
  -F "file=@$WORK/input.png" "$FRONTEND/api/seal")
check "POST :3000/api/seal" "200" "$SEAL_CODE"
SEAL_ID=$(jget "$WORK/seal.json" "d.get('seal_id')")
SEAL_UID=$(jget "$WORK/seal.json" "d.get('uid')")
if [ -n "$SEAL_ID" ] && [ "$SEAL_ID" != "None" ]; then
  pass "seal created: seal_id=$SEAL_ID uid=$SEAL_UID tiles=$(jget "$WORK/seal.json" "d.get('tiles')") in $(jget "$WORK/seal.json" "d.get('seal_ms')")ms"
else
  fail "no seal_id in the response: $(cat "$WORK/seal.json")"
  printf '\nAborting: every later check needs a real seal.\n'
  exit 1
fi

DL_CODE=$(curl -s -o "$WORK/sealed.png" -w '%{http_code}' -m 60 "${AUTH_OK[@]}" "$FRONTEND/api/seal/$SEAL_ID/file")
check "GET :3000/api/seal/$SEAL_ID/file" "200" "$DL_CODE"
if head -c 8 "$WORK/sealed.png" | od -An -tx1 | tr -d ' \n' | grep -q '^89504e470d0a1a0a$'; then
  pass "downloaded file is a PNG"
else
  fail "downloaded file is not a PNG: $(head -c 64 "$WORK/sealed.png")"
fi
if "$PYTHON" -c "import sys
from PIL import Image
sys.exit(0 if 'medseal_uid' in Image.open(sys.argv[1]).text else 1)" "$WORK/sealed.png"; then
  pass "downloaded PNG carries the medseal_uid chunk"
else
  fail "downloaded PNG has no medseal_uid chunk"
fi

verify "$WORK/sealed.png"
check "POST $BACKEND/verify" "200" "$VERIFY_CODE"
check "status of the sealed original" "authentic" "$(jget "$WORK/verify.json" "d.get('status')")"
check "matched_by" "uid" "$(jget "$WORK/verify.json" "d.get('matched_by')")"
check "seal_id reported back" "$SEAL_ID" "$(jget "$WORK/verify.json" "d.get('seal_id')")"
SHIELD_CLEAN=$(jget "$WORK/verify.json" "(d.get('shield') or {}).get('attack_suspected')")
check "shield on the clean sealed image: attack_suspected" "False" "$SHIELD_CLEAN"
DET_CLEAN=$(jget "$WORK/verify.json" "(d.get('detective') or {}).get('probability', 'null')")
if [ "$DET_CLEAN" = "null" ]; then
  note "detective is null on this response (no weights/detective.pt) - not a shield failure"
else
  note "detective probability available: $DET_CLEAN"
fi

# ---------------------------------------------------------------- c. the four tamper cases
say "c. Tamper cases (P1-03 content-based recovery)"
( cd "$BACKEND_DIR" && "$PYTHON" -m scripts.tamper_demo "$WORK/sealed.png" ) >"$WORK/tamper.log" 2>&1
if [ -f "$WORK/sealed_tampered.png" ]; then
  pass "scripts.tamper_demo produced sealed_tampered.png (medseal_uid kept)"
else
  fail "scripts.tamper_demo produced no output: $(cat "$WORK/tamper.log")"
fi

# Re-save a PNG without any tEXt chunk: exactly what an image editor or a metadata
# stripper produces, i.e. the seal ID is gone.
resave_no_chunk() {  # <src> <dst>
  "$PYTHON" - "$1" "$2" <<'PY'
import sys
from PIL import Image
img = Image.open(sys.argv[1])          # no pnginfo= -> every tEXt chunk is dropped
img.save(sys.argv[2], "PNG")
PY
}

verify "$WORK/sealed_tampered.png"
check "tampered, seal ID kept: status" "tampered" "$(jget "$WORK/verify.json" "d.get('status')")"
TILE_RANGE=$("$PYTHON" -c "
import json
n = len(json.load(open('$WORK/verify.json'))['changed_tiles'])
print('yes' if 0 < n < 20 else 'no(%d)' % n)")
check "tampered, seal ID kept: a local edit, 0 < changed_tiles < 20" "yes" "$TILE_RANGE"

resave_no_chunk "$WORK/sealed_tampered.png" "$WORK/tampered_nouid.png"
verify "$WORK/tampered_nouid.png"
check "tampered, seal ID stripped: status" "tampered" "$(jget "$WORK/verify.json" "d.get('status')")"
check "tampered, seal ID stripped: reason" "seal_id_removed" "$(jget "$WORK/verify.json" "d.get('reason')")"
check "tampered, seal ID stripped: matched_by" "content" "$(jget "$WORK/verify.json" "d.get('matched_by')")"

resave_no_chunk "$WORK/sealed.png" "$WORK/resaved_nouid.png"
verify "$WORK/resaved_nouid.png"
check "untouched image re-saved without the chunk: status" "authentic" "$(jget "$WORK/verify.json" "d.get('status')")"
check "untouched image re-saved without the chunk: warning" "seal_id_missing" "$(jget "$WORK/verify.json" "d.get('warning')")"

if [ -f "$SAMPLES/$UNRELATED_SAMPLE" ]; then
  verify "$SAMPLES/$UNRELATED_SAMPLE"
  check "unrelated X-ray of the same size: status" "unsigned" "$(jget "$WORK/verify.json" "d.get('status')")"
  check "unrelated X-ray of the same size: matched_by" "None" "$(jget "$WORK/verify.json" "d.get('matched_by')")"
else
  fail "unrelated sample $SAMPLES/$UNRELATED_SAMPLE missing"
fi

# ---------------------------------------------------------------- d. adversarial shield
say "d. Adversarial attack: the shield flags it, a clean image is not flagged"
STEM="${SAMPLE%.png}"
( cd "$BACKEND_DIR" && "$PYTHON" -m scripts.attack_demo "$SAMPLES/$SAMPLE" --eps 2 --method pgd --out "$WORK" ) >"$WORK/attack.log" 2>&1
if [ -f "$WORK/${STEM}_attacked.png" ]; then
  pass "scripts.attack_demo --eps 2 --method pgd: $(grep -E ':.*->' "$WORK/attack.log" | head -1)"
else
  fail "scripts.attack_demo produced no output: $(cat "$WORK/attack.log")"
fi
verify "$WORK/${STEM}_attacked.png"
check "attacked image: shield.attack_suspected" "True" "$(jget "$WORK/verify.json" "(d.get('shield') or {}).get('attack_suspected')")"
check "attacked image: shield.score above threshold" "yes" "$("$PYTHON" -c "
import json
s = json.load(open('$WORK/verify.json')).get('shield') or {}
print('yes' if s.get('score', 0) > s.get('threshold', 1) else 'no')")"
verify "$WORK/${STEM}_before.png"
check "clean image: shield.attack_suspected" "False" "$(jget "$WORK/verify.json" "(d.get('shield') or {}).get('attack_suspected')")"
DET_BEFORE=$(jget "$WORK/verify.json" "(d.get('detective') or {}).get('probability', 'null')")
if [ "$DET_BEFORE" = "null" ]; then
  note "detective returned null (no weights/detective.pt) - shield checks are unaffected"
else
  note "detective probability on the clean image: $DET_BEFORE"
fi

# ---------------------------------------------------------------- e. crash test
say "e. Crash test through :3000: protocol compliance and 409 while busy"
curl -s -o "$WORK/models.json" -m 30 "$BACKEND/models"
MODEL_ID=$(jget "$WORK/models.json" "d[0]['id'] if d else None")
if [ -n "$MODEL_ID" ] && [ "$MODEL_ID" != "None" ]; then
  pass "model under test: id=$MODEL_ID $(jget "$WORK/models.json" "d[0]['name']")"
else
  fail "GET $BACKEND/models returned nothing usable"
  exit 1
fi
BODY="{\"model_id\":$MODEL_ID,\"n_images\":50,\"eps\":[0.5,1,2,4],\"method\":\"pgd\"}"
CT1=$(curl -s -o "$WORK/ct1.json" -w '%{http_code}' -m 60 "${AUTH_OK[@]}" -X POST \
  -H 'Content-Type: application/json' -d "$BODY" "$FRONTEND/api/crash-test")
check "POST :3000/api/crash-test (pgd, n=50, eps includes 1)" "202" "$CT1"
JOB=$(jget "$WORK/ct1.json" "d.get('job_id')")
CT2=$(curl -s -o "$WORK/ct2.json" -w '%{http_code}' -m 60 "${AUTH_OK[@]}" -X POST \
  -H 'Content-Type: application/json' -d "$BODY" "$FRONTEND/api/crash-test")
check "second POST while that job is running" "409" "$CT2"
if grep -q "already running" "$WORK/ct2.json"; then
  pass "the 409 body says why: $(cat "$WORK/ct2.json")"
else
  fail "the 409 body does not mention a running job: $(cat "$WORK/ct2.json")"
fi

printf '  ... polling job %s (timeout %ss)\n' "$JOB" "$CRASH_TIMEOUT"
DEADLINE=$(( $(date +%s) + CRASH_TIMEOUT ))
STATUS=""
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
  curl -s -o "$WORK/ct_status.json" -m 30 "$BACKEND/crash-test/$JOB"
  STATUS=$(jget "$WORK/ct_status.json" "d.get('status')")
  printf '\r  ... status=%s progress=%s   ' "$STATUS" "$(jget "$WORK/ct_status.json" "d.get('progress')")"
  case "$STATUS" in
    done) printf '\n'; break ;;
    error) printf '\n'; fail "crash test failed: $(jget "$WORK/ct_status.json" "d.get('error')")"; break ;;
  esac
  sleep 5
done
if [ "$STATUS" = "done" ]; then pass "crash test finished"; else
  fail "crash test did not finish within ${CRASH_TIMEOUT}s (last status: $STATUS)"
fi
check "protocol_compliant (pgd, n>=50, eps includes 1)" "True" "$(jget "$WORK/ct_status.json" "d.get('protocol_compliant')")"
SCORE=$(jget "$WORK/ct_status.json" "d.get('robustness_score')")
if [ -n "$SCORE" ] && [ "$SCORE" != "None" ]; then
  pass "robustness_score present: $SCORE (n_images=$(jget "$WORK/ct_status.json" "d.get('n_images')") of n_requested=$(jget "$WORK/ct_status.json" "d.get('n_requested')"))"
else
  fail "no robustness_score in the crash-test result"
fi

# ---------------------------------------------------------------- f. passport
say "f. Passport: issued through :3000, signed, verifiable, exportable"
P1=$(curl -s -o "$WORK/p1.json" -w '%{http_code}' -m 60 "${AUTH_OK[@]}" -X POST \
  -H 'Content-Type: application/json' \
  -d "{\"model_id\":$MODEL_ID,\"crash_test_id\":$JOB,\"organisation\":\"MedSeal live check\"}" \
  "$FRONTEND/api/passport")
check "POST :3000/api/passport" "201" "$P1"
PASSPORT_ID=$(jget "$WORK/p1.json" "d.get('id')")
check "verdict" "allowed_with_conditions" "$(jget "$WORK/p1.json" "d.get('verdict')")"
HAS_CLINICAL=$("$PYTHON" -c "
import json
d = json.load(open('$WORK/p1.json'))
print(any('clinical_validation_required' in str(c) for c in d.get('conditions', [])))")
check "conditions include clinical_validation_required" "True" "$HAS_CLINICAL"
curl -s -o "$WORK/pv.json" -m 30 "$BACKEND/passport/$PASSPORT_ID/verify"
check "GET $BACKEND/passport/$PASSPORT_ID/verify -> valid" "True" "$(jget "$WORK/pv.json" "d.get('valid')")"
check "fingerprint matches the issued passport" "$(jget "$WORK/p1.json" "d.get('fingerprint')")" "$(jget "$WORK/pv.json" "d.get('fingerprint')")"
for LANG in uz ru; do
  PDF_CODE=$(curl -s -o "$WORK/passport-$LANG.pdf" -w '%{http_code}' -m 60 \
    "$BACKEND/passport/$PASSPORT_ID/pdf?lang=$LANG")
  check "GET $BACKEND/passport/$PASSPORT_ID/pdf?lang=$LANG" "200" "$PDF_CODE"
  check "  $LANG content-type" "application/pdf" \
    "$(curl -s -o /dev/null -w '%{content_type}' -m 60 "$BACKEND/passport/$PASSPORT_ID/pdf?lang=$LANG")"
  SIZE=$(wc -c < "$WORK/passport-$LANG.pdf" | tr -d ' ')
  if [ "$SIZE" -gt 1000 ]; then pass "  $LANG PDF is not empty ($SIZE bytes)"; else fail "  $LANG PDF is empty ($SIZE bytes)"; fi
  if head -c 5 "$WORK/passport-$LANG.pdf" | grep -q '%PDF-'; then pass "  $LANG file starts with %PDF-"; else
    fail "  $LANG file is not a PDF"
  fi
done

# ---------------------------------------------------------------- g. abuse cases
say "g. Oversized uploads and unauthenticated downloads"
dd if=/dev/zero of="$WORK/big.bin" bs=1048576 count=51 2>/dev/null
BIG_CODE=$(curl -s -o /dev/null -w '%{http_code}' -m 300 "${AUTH_OK[@]}" -F "file=@$WORK/big.bin" "$FRONTEND/api/seal")
check_in "POST :3000/api/seal with a 51 MB body" "413" "415" "$BIG_CODE"
# A PNG header claiming 400 megapixels: must be refused from the header, before decoding.
"$PYTHON" - "$WORK/huge.png" <<'PY'
import struct, sys, zlib
w = h = 20000
ihdr = struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0)          # 400 MP, greyscale
chunk = struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr
data = b"\x89PNG\r\n\x1a\n" + chunk + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr))
open(sys.argv[1], "wb").write(data)
PY
check_in "POST $BACKEND/verify with a 400 MP PNG header" "413" "415" \
  "$(code -X POST -m 60 -F "file=@$WORK/huge.png" "$BACKEND/verify")"
if [ -f "$SAMPLES/$JPG_SAMPLE" ]; then
  check "POST $BACKEND/verify with a JPG (unsupported type)" "415" \
    "$(code -X POST -m 60 -F "file=@$SAMPLES/$JPG_SAMPLE" "$BACKEND/verify")"
else
  note "sample $JPG_SAMPLE missing, skipping the unsupported-type check"
fi
check "GET $BACKEND/seal/$SEAL_ID/file with no token" "401" "$(code "$BACKEND/seal/$SEAL_ID/file")"
check "GET $BACKEND/seals with no token" "401" "$(code "$BACKEND/seals")"
check "GET $BACKEND/seal/$SEAL_ID/file with the device token" "200" \
  "$(code -H "Authorization: Bearer $DEVICE_TOKEN" "$BACKEND/seal/$SEAL_ID/file")"

# ---------------------------------------------------------------- verdict
printf '\n\033[1m== Result\033[0m\n'
printf '  passed: %s\n  failed: %s\n' "$PASS_COUNT" "$FAIL_COUNT"
if [ "$FAIL_COUNT" -ne 0 ]; then
  printf '\n\033[31mFAILED checks:\033[0m\n'
  for c in "${FAILED_CHECKS[@]}"; do printf '  - %s\n' "$c"; done
  printf '\n\033[31mLIVE END-TO-END CHECK FAILED\033[0m\n'
  exit 1
fi
printf '\n\033[32mLIVE END-TO-END CHECK PASSED (%s checks)\033[0m\n' "$PASS_COUNT"
