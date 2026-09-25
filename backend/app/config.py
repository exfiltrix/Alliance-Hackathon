"""Runtime settings. Everything can be overridden with MEDSEAL_* environment variables."""
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent

# Secrets (admin token, anchoring key, RPC URL) live only in backend/.env (gitignored) or the real
# environment; variables already set in the environment win over the file.
load_dotenv(BACKEND_DIR / ".env", override=False)


def _path(env: str, default: Path) -> Path:
    return Path(os.environ.get(env, default))


@dataclass
class Settings:
    db_url: str = os.environ.get("MEDSEAL_DB_URL", f"sqlite:///{BACKEND_DIR / 'medseal.db'}")
    # Private device keys (demo stand-in for the gateway HSM). Gitignored.
    keys_dir: Path = _path("MEDSEAL_KEYS_DIR", BACKEND_DIR / "keys")
    # Sealed files served by GET /api/seal/{id}/file. Gitignored.
    storage_dir: Path = _path("MEDSEAL_STORAGE_DIR", BACKEND_DIR / "storage")
    cors_origins: list[str] = field(
        default_factory=lambda: os.environ.get(
            "MEDSEAL_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
    )
    # Plus the frontend opened from any private-network address (phone on the same Wi-Fi), whatever the IP is.
    cors_origin_regex: str = os.environ.get(
        "MEDSEAL_CORS_ORIGIN_REGEX",
        r"http://(10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+):3000",
    )
    max_upload_bytes: int = 50 * 1024 * 1024
    # Decoded size cap (T10): a 50 MB PNG/DICOM can still decode into gigabytes ("decompression bomb").
    # Checked from the header, before any pixel is decoded. 64 Mpx = 8000x8000, far above any X-ray/CT.
    max_pixels: int = int(os.environ.get("MEDSEAL_MAX_PIXELS", str(64_000_000)))
    # POST requests per client IP per minute (T11); 0 = off. Uploads are the expensive part of the API.
    rate_limit_per_min: int = int(os.environ.get("MEDSEAL_RATE_LIMIT", "120"))
    # Public/synthetic images (scripts/fetch_*.py). Crash test reads data/nih/normal, then data/samples.
    data_dir: Path = _path("MEDSEAL_DATA_DIR", BACKEND_DIR.parent / "data")
    # Run the AI shield/detective inside /verify (needs torch + weights). MEDSEAL_AI=0 turns them off.
    ai_enabled: bool = os.environ.get("MEDSEAL_AI", "1") != "0"
    # Required to create/revoke devices (POST /devices, /devices/{id}/revoke). No default: unset means
    # those endpoints refuse every request, rather than silently accepting an empty bearer token.
    admin_token: str = field(default=os.environ.get("MEDSEAL_ADMIN_TOKEN", ""), repr=False)
    # Optional HMAC salt used to bind a DICOM PatientID without storing it. Keep it stable.
    patient_salt: str = os.environ.get("MEDSEAL_PATIENT_SALT", "")
    # Root signing material. The private key stays in the gateway/HSM; verifiers use root.pub only.
    root_key_path: Path = _path("MEDSEAL_ROOT_KEY_PATH", BACKEND_DIR / "keys" / "root.pem")
    root_pubkey_path: Path = _path("MEDSEAL_ROOT_PUBKEY_PATH", BACKEND_DIR / "keys" / "root.pub")
    require_device_cert: bool = os.environ.get("MEDSEAL_REQUIRE_DEVICE_CERT", "1") != "0"
    # Append-only external hash-chain anchors. Never store this file in the database trust root.
    anchor_path: Path = _path("MEDSEAL_ANCHOR_PATH", BACKEND_DIR / "anchors" / "anchors.jsonl")
    # Shield threshold + measured quality (scripts/calibrate_shield.py). Committed; the passport reads it too.
    shield_calibration: Path = BACKEND_DIR / "app" / "ai" / "shield_calibration.json"
    # Detective weights (scripts/train_detective.py) and their held-out quality.
    detective_weights: Path = _path("MEDSEAL_DETECTIVE_WEIGHTS", BACKEND_DIR / "weights" / "detective.pt")
    detective_metrics: Path = BACKEND_DIR / "app" / "ai" / "detective_metrics.json"
    # Automation (app/automation/watcher.py): watched folders, sealing gateway, model warm-up.
    watch_enabled: bool = os.environ.get("MEDSEAL_WATCH", "1") != "0"
    watch_dir: Path = _path("MEDSEAL_WATCH_DIR", BACKEND_DIR.parent / "data" / "watch")
    watch_interval_s: float = float(os.environ.get("MEDSEAL_WATCH_INTERVAL", "2"))
    gateway_name: str = os.environ.get("MEDSEAL_GATEWAY_NAME", "Shlyuz-Auto")
    gateway_hospital: str = os.environ.get("MEDSEAL_GATEWAY_HOSPITAL", "Namangan viloyat shifoxonasi")
    warmup: bool = os.environ.get("MEDSEAL_WARMUP", "1") != "0"
    # Blockchain anchoring (docs/BLOCKCHAIN.md). Names as in the doc, no MEDSEAL_ prefix. Anchoring is
    # on only when RPC_URL, CONTRACT_ADDRESS and ANCHOR_PRIVATE_KEY are all set; otherwise /verify
    # returns "blockchain": null. The key is never logged or returned (repr=False keeps it out of reprs).
    rpc_url: str = field(default=os.environ.get("RPC_URL", ""), repr=False)  # may embed a provider API key
    anchor_private_key: str = field(default=os.environ.get("ANCHOR_PRIVATE_KEY", ""), repr=False)
    contract_address: str = os.environ.get("CONTRACT_ADDRESS", "")
    chain_id: int = int(os.environ.get("CHAIN_ID") or 0)
    explorer_url: str = os.environ.get("EXPLORER_URL", "").rstrip("/")  # e.g. https://sepolia.etherscan.io
    anchor_enabled: bool = os.environ.get("MEDSEAL_ANCHOR", "1") != "0"  # background batching loop
    anchor_interval_s: float = float(os.environ.get("MEDSEAL_ANCHOR_INTERVAL", "600"))
    anchor_confirmations: int = int(os.environ.get("MEDSEAL_ANCHOR_CONFIRMATIONS", "1"))


settings = Settings()
