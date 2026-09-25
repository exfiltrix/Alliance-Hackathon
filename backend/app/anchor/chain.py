"""Talking to the MedSealAnchor contract (contracts/contracts/MedSealAnchor.sol).

Web3Chain: any EVM network over JSON-RPC — a local Hardhat node for the offline demo, Sepolia
for the jury. MemoryChain: same rules in memory, for tests only.
The anchoring key is used here only to sign transactions; it is never logged or returned.
"""
import threading
import time
from dataclasses import dataclass
from typing import Protocol

from app.config import settings

# Only what the backend calls. Full ABI: contracts/artifacts/ after `npx hardhat compile`.
ABI = [
    {"type": "function", "name": "anchor", "stateMutability": "nonpayable",
     "inputs": [{"name": "root", "type": "bytes32"}, {"name": "count", "type": "uint32"}],
     "outputs": [{"name": "id", "type": "uint256"}]},
    {"type": "function", "name": "anchors", "stateMutability": "view",
     "inputs": [{"name": "", "type": "uint256"}],
     "outputs": [{"name": "root", "type": "bytes32"}, {"name": "time", "type": "uint64"},
                 {"name": "count", "type": "uint32"}]},
    {"type": "function", "name": "anchored", "stateMutability": "view",
     "inputs": [{"name": "", "type": "bytes32"}], "outputs": [{"name": "", "type": "bool"}]},
    {"type": "function", "name": "owner", "stateMutability": "view",
     "inputs": [], "outputs": [{"name": "", "type": "address"}]},
    {"type": "function", "name": "total", "stateMutability": "view",
     "inputs": [], "outputs": [{"name": "", "type": "uint256"}]},
    {"type": "event", "name": "Anchored", "anonymous": False,
     "inputs": [{"name": "id", "type": "uint256", "indexed": True},
                {"name": "root", "type": "bytes32", "indexed": False},
                {"name": "count", "type": "uint32", "indexed": False}]},
]


class ChainError(Exception):
    """Network down, not enough gas, wrong key... Seals keep working; anchoring retries later."""


@dataclass
class AnchorTx:
    tx_hash: str
    block_number: int
    onchain_index: int


@dataclass
class OnchainAnchor:
    root: bytes
    time: int  # unix seconds, block timestamp
    count: int


class Chain(Protocol):
    chain_id: int

    def anchor(self, root: bytes, count: int) -> AnchorTx: ...

    def get_anchor(self, index: int) -> OnchainAnchor: ...

    def total(self) -> int: ...


class Web3Chain:
    def __init__(self, rpc_url: str, contract_address: str, private_key: str, chain_id: int = 0,
                 confirmations: int = 1, timeout_s: float = 180):
        from web3 import Web3  # imported lazily: the backend runs without web3 when anchoring is off

        self._w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 10}))
        self._contract = self._w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=ABI)
        self._account = self._w3.eth.account.from_key(private_key)
        self._expected_chain_id = chain_id
        self._chain_id: int | None = None
        self._confirmations = max(1, confirmations)
        self._timeout_s = timeout_s
        self._cache: dict[int, OnchainAnchor] = {}  # on-chain anchors never change, so caching is safe

    @property
    def chain_id(self) -> int:
        if self._chain_id is None:
            try:
                self._chain_id = self._w3.eth.chain_id
            except Exception as e:
                raise ChainError(f"RPC unreachable: {type(e).__name__}") from e
            if self._expected_chain_id and self._chain_id != self._expected_chain_id:
                raise ChainError(f"RPC is chain {self._chain_id}, CHAIN_ID says {self._expected_chain_id}")
        return self._chain_id

    def anchor(self, root: bytes, count: int) -> AnchorTx:
        chain_id = self.chain_id
        try:
            if self._contract.functions.owner().call() != self._account.address:
                raise ChainError("ANCHOR_PRIVATE_KEY is not the owner of the contract")
            if self._contract.functions.anchored(root).call():
                raise ChainError("root already anchored")
            tx = self._contract.functions.anchor(root, count).build_transaction({
                "from": self._account.address,
                "nonce": self._w3.eth.get_transaction_count(self._account.address, "pending"),
                "chainId": chain_id,
            })
            signed = self._account.sign_transaction(tx)
            tx_hash = self._w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=self._timeout_s)
            if receipt["status"] != 1:
                raise ChainError("anchor transaction reverted")
            self._wait_confirmations(receipt["blockNumber"])
            events = self._contract.events.Anchored().process_receipt(receipt)
        except ChainError:
            raise
        except Exception as e:
            # Only the exception type (plus a revert reason): connection errors quote the RPC URL,
            # which for hosted providers contains the API key.
            from web3.exceptions import ContractLogicError

            detail = f": {e}"[:200] if isinstance(e, ContractLogicError) else ""
            raise ChainError(f"anchoring failed: {type(e).__name__}{detail}") from e
        if not events:
            raise ChainError("no Anchored event in the receipt")
        return AnchorTx(tx_hash="0x" + bytes(tx_hash).hex().removeprefix("0x"),
                        block_number=receipt["blockNumber"], onchain_index=int(events[0]["args"]["id"]))

    def _wait_confirmations(self, block: int) -> None:
        deadline = time.monotonic() + self._timeout_s
        while self._w3.eth.block_number - block + 1 < self._confirmations:
            if time.monotonic() > deadline:
                raise ChainError("timed out waiting for confirmations")
            time.sleep(2)

    def get_anchor(self, index: int) -> OnchainAnchor:
        if index in self._cache:
            return self._cache[index]
        try:
            root, t, count = self._contract.functions.anchors(index).call()
        except Exception as e:
            raise ChainError(f"cannot read anchor {index}: {type(e).__name__}") from e
        self._cache[index] = OnchainAnchor(root=bytes(root), time=int(t), count=int(count))
        return self._cache[index]

    def total(self) -> int:
        try:
            return int(self._contract.functions.total().call())
        except Exception as e:
            raise ChainError(f"cannot read total: {type(e).__name__}") from e


class MemoryChain:
    """In-memory stand-in with the contract's rules (append-only, no duplicate roots). Tests only."""

    def __init__(self, chain_id: int = 31337):
        self.chain_id = chain_id
        self.anchors: list[OnchainAnchor] = []
        self.online = True

    def anchor(self, root: bytes, count: int) -> AnchorTx:
        if not self.online:
            raise ChainError("RPC unreachable")
        if any(a.root == root for a in self.anchors):
            raise ChainError("root already anchored")
        self.anchors.append(OnchainAnchor(root=root, time=int(time.time()), count=count))
        n = len(self.anchors) - 1
        return AnchorTx(tx_hash="0x" + f"{n:064x}", block_number=100 + n, onchain_index=n)

    def get_anchor(self, index: int) -> OnchainAnchor:
        if not self.online:
            raise ChainError("RPC unreachable")
        if index >= len(self.anchors):
            raise ChainError(f"no anchor {index}")
        return self.anchors[index]

    def total(self) -> int:
        if not self.online:
            raise ChainError("RPC unreachable")
        return len(self.anchors)


_lock = threading.Lock()
_chain: Chain | None = None
_override: Chain | None = None


def configured() -> bool:
    return bool(settings.rpc_url and settings.contract_address and settings.anchor_private_key)


def get_chain() -> Chain | None:
    """The configured chain, or None when anchoring is off (no RPC_URL / CONTRACT_ADDRESS / key)."""
    global _chain
    if _override is not None:
        return _override
    if not configured():
        return None
    with _lock:
        if _chain is None:
            _chain = Web3Chain(settings.rpc_url, settings.contract_address, settings.anchor_private_key,
                               settings.chain_id, settings.anchor_confirmations)
        return _chain


def set_chain(chain: Chain | None) -> None:
    """Tests: use this chain instead of the configured one (None = back to settings)."""
    global _override, _chain
    _override, _chain = chain, None


def tx_url(tx_hash: str) -> str | None:
    return f"{settings.explorer_url}/tx/{tx_hash}" if settings.explorer_url else None
