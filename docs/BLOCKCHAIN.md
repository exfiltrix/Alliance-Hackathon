# MedSeal — blockchain anchoring

Goal: **nobody — an attacker, a hospital, or the MedSeal operator itself — can rewrite the history of seals.**
The blockchain stores only fingerprints (hashes). Never images, never patient data.

## How it works

```
seals (ledger) ──every 10 min──► batch Merkle root ──tx──► MedSealAnchor contract
verify(image) ──► seal ok? ──► Merkle proof → batch root ──► root on-chain? ──► "Anchored"
```

## 1. Smart contract (Solidity ^0.8.24)

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract MedSealAnchor {
    address public immutable owner;
    struct Anchor { bytes32 root; uint64 time; uint32 count; }
    Anchor[] public anchors;
    mapping(bytes32 => bool) public anchored;
    event Anchored(uint256 indexed id, bytes32 root, uint32 count);

    constructor() { owner = msg.sender; }

    function anchor(bytes32 root, uint32 count) external returns (uint256 id) {
        require(msg.sender == owner, "only MedSeal");
        require(!anchored[root], "already anchored");
        anchors.push(Anchor(root, uint64(block.timestamp), count));
        anchored[root] = true;
        id = anchors.length - 1;
        emit Anchored(id, root, count);
    }

    function total() external view returns (uint256) { return anchors.length; }
}
```

No update or delete function exists — history is append-only by construction.
Hackathon: deploy on **Ethereum Sepolia** (or Polygon Amoy) via Remix or Hardhat; verify the source on Etherscan so the jury can read it.
Production: permissioned chain (Hyperledger Fabric / Besu) with nodes at the Ministry of Health and hospitals.

## 2. Merkle tree rules (use everywhere, including tile hashing)

- Domain separation (prevents second-preimage tricks): `leaf = sha256(0x00 || data)`, `node = sha256(0x01 || left || right)`.
- Leaves in a fixed order (ledger entry id ascending). Odd level: duplicate the last node.
- **Update `reference/medseal_poc.py` logic to these rules when porting** and keep tests green.

Batch leaf = the seal's `entry_hash` (from the hash-chained ledger).

## 3. Anchoring service (`backend/app/anchor/`)

- Library: `web3.py`. Config from env only: `RPC_URL`, `ANCHOR_PRIVATE_KEY`, `CONTRACT_ADDRESS`, `CHAIN_ID`, `EXPLORER_URL`. Never log or return the key; `.env` is gitignored.
- Every 10 min (APScheduler) or `POST /api/anchors/run` in demo:
  1. select seals with `anchor_id IS NULL`; if none → skip;
  2. build the batch Merkle tree; store each seal's proof (list of `[side, hash]`);
  3. send `anchor(root, count)`; wait for 1 confirmation (hackathon) / 12 (production);
  4. save `anchors` row + set `anchor_id` on the seals.
- Failure (RPC down, gas): seals keep working; retry next cycle; status "pending anchor" in UI.

### Table `anchors`
`id, batch_root_hex, count, tx_hash, block_number, chain_id, onchain_index, created_at, status (pending|confirmed|failed)`
Add to `seals`: `anchor_id`, `merkle_proof_json`.

## 4. Verification

1. Seal check as before (signature + tiles).
2. Recompute batch root from the seal's `entry_hash` + stored proof.
3. Read `anchors(onchain_index)` from the contract (**from the chain, not our DB**) and compare root.
4. Result field `blockchain`: `anchored | pending | mismatch | unavailable`.
   `mismatch` = our database was altered → show as **critical**.

## 5. API additions
- `GET /api/anchors` → list with tx links.
- `POST /api/anchors/run` → force a batch (demo).
- `/api/verify` response gains:
```json
"blockchain": { "status": "anchored", "block": 6712345, "time": "2026-09-26T10:10:12Z",
                "tx_url": "https://sepolia.etherscan.io/tx/0x…" }
```

## 6. Tests
- proof for every leaf verifies; a changed leaf fails;
- editing a seal row in SQLite after anchoring → verify returns `mismatch`;
- contract: non-owner `anchor` reverts; duplicate root reverts (Hardhat test or Remix).

## 7. As implemented (differences from the plan above)
- Contract + Hardhat tests + deploy script: `contracts/` (`npx hardhat test`). Backend: `backend/app/anchor/` (`chain.py` web3 client, `service.py` batching + check), Merkle: `backend/app/seal/merkle.py`.
- Proofs live in a separate table `seal_anchors(seal_id, anchor_id, proof_json)`, not in new `seals` columns: the ledger stays append-only and its hash chain untouched. `anchors` stores only confirmed batches (a failed send leaves no row; the seals stay pending and are retried).
- Background batching is a plain thread like the folder watcher (no APScheduler). `POST /api/anchors/run` requires the admin token.
- The leaf is recomputed from the row's current content at verify time (not the stored `entry_hash`). Because `entry_hash` covers `prev_hash`, rewriting one row and repairing the chain makes every later row mismatch too.
- `mismatch` also sets `status: "forged"`, `reason: "blockchain_mismatch"`, so a UI that ignores `blockchain` still shows red. A seal with no proof although the chain holds a batch mined > 5 min after it → `mismatch` (`detail: "proof_missing"`): deleting the proof does not hide a rewrite.
- `blockchain: null` when anchoring is off (no `RPC_URL` / `CONTRACT_ADDRESS` / `ANCHOR_PRIVATE_KEY` in `backend/.env`) or the image is unsigned.
- Tile hashing keeps the frozen v1 format (no domain separation) — only the batch tree uses it. Migrating tiles needs a format version on the seal; see CLAUDE.md.
- Honest limit: seals are only protected by the chain once anchored (≤ 10 min window).
