#!/usr/bin/env bash
# One command before the demo: local blockchain + MedSealAnchor contract + backend.
#   ./demo.sh          (Ctrl+C stops the backend and the chain it started)
# Seals are anchored automatically every 15 s here (MEDSEAL_ANCHOR_INTERVAL), no curl needed.
# The frontend runs separately: cd by_billy/frontend && npm run dev
set -euo pipefail
root=$(cd "$(dirname "$0")" && pwd)
env_file="$root/backend/.env"
rpc_url=http://127.0.0.1:8545
port="${MEDSEAL_PORT:-8000}"
say() { echo -e "\033[36m▶ $*\033[0m"; }

rpc() {
  curl -s -m 2 -X POST -H 'content-type: application/json' \
    --data "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"$1\",\"params\":$2}" "$rpc_url"
}

if lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "port $port is busy — is the backend already running? Stop it first (Ctrl+C in its terminal)."
  exit 1
fi
[ -x "$root/backend/.venv/bin/uvicorn" ] || { echo "backend venv missing: see CLAUDE.md (Команды)"; exit 1; }
[ -d "$root/contracts/node_modules" ] || { say "installing contract tools"; (cd "$root/contracts" && npm ci --silent); }

# 1. backend/.env with local-chain settings (never overwritten if it exists)
if [ ! -f "$env_file" ]; then
  say "creating backend/.env for the local chain"
  # Account #0 of every Hardhat node, derived from Hardhat's public test mnemonic, so no key
  # is stored in this repo. Public test key: NEVER use it on a real network.
  dev_key=$(cd "$root/contracts" && node -e 'console.log(require("ethers").Wallet.fromPhrase(
    "test test test test test test test test test test test junk").privateKey)')
  umask 077
  cat > "$env_file" <<EOF
MEDSEAL_ADMIN_TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
# Account #0 of the local Hardhat node: public test key, NEVER use it on a real network.
RPC_URL=$rpc_url
ANCHOR_PRIVATE_KEY=$dev_key
CONTRACT_ADDRESS=0x5FbDB2315678afecb367f032d93F642f64180aa3
CHAIN_ID=31337
EXPLORER_URL=
EOF
fi
grep -q "^RPC_URL=$rpc_url" "$env_file" || { echo "backend/.env points to another chain (not $rpc_url) — not touching it"; exit 1; }

# 2. local chain (reuse it if it is already running)
node_pid=""
if ! rpc eth_chainId '[]' | grep -q result; then
  say "starting local blockchain (log: contracts/node.log)"
  (cd "$root/contracts" && exec npx hardhat node > node.log 2>&1) &
  node_pid=$!
  for _ in $(seq 60); do rpc eth_chainId '[]' | grep -q result && break; sleep 0.5; done
  rpc eth_chainId '[]' | grep -q result || { echo "chain did not start, see contracts/node.log"; exit 1; }
fi
cleanup() { [ -n "$node_pid" ] && kill "$node_pid" 2>/dev/null && say "local blockchain stopped"; }
trap cleanup EXIT

# 3. contract: deploy if the address in .env has no code (fresh node), keep .env in sync
addr=$(grep '^CONTRACT_ADDRESS=' "$env_file" | cut -d= -f2)
if rpc eth_getCode "[\"$addr\",\"latest\"]" | grep -q '"result":"0x"'; then
  say "deploying MedSealAnchor"
  new_addr=$(cd "$root/contracts" && npx hardhat run scripts/deploy.js --network localhost | grep '^CONTRACT_ADDRESS=' | cut -d= -f2)
  if [ "$new_addr" != "$addr" ]; then
    sed -i.bak "s/^CONTRACT_ADDRESS=.*/CONTRACT_ADDRESS=$new_addr/" "$env_file" && rm -f "$env_file.bak"
    say "CONTRACT_ADDRESS updated in backend/.env"
  fi
fi
say "blockchain ready — contract $(grep '^CONTRACT_ADDRESS=' "$env_file" | cut -d= -f2)"

# 4. backend (reachable from phones on the same Wi-Fi too)
say "backend on http://localhost:$port (Swagger: /docs). Ctrl+C to stop."
cd "$root/backend"
MEDSEAL_ANCHOR_INTERVAL="${MEDSEAL_ANCHOR_INTERVAL:-15}" .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$port"
