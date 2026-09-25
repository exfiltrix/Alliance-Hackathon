"""Runtime settings. Everything can be overridden with MEDSEAL_* environment variables."""
import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


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
    # Public/synthetic images (scripts/fetch_*.py). Crash test reads data/nih/normal, then data/samples.
    data_dir: Path = _path("MEDSEAL_DATA_DIR", BACKEND_DIR.parent / "data")
    # Run the AI shield/detective inside /verify (needs torch + weights). MEDSEAL_AI=0 turns them off.
    ai_enabled: bool = os.environ.get("MEDSEAL_AI", "1") != "0"
    # Required to create/revoke devices (POST /devices, /devices/{id}/revoke). No default: unset means
    # those endpoints refuse every request, rather than silently accepting an empty bearer token.
    admin_token: str = os.environ.get("MEDSEAL_ADMIN_TOKEN", "")
    # Shield threshold + measured quality (scripts/calibrate_shield.py). Committed; the passport reads it too.
    shield_calibration: Path = BACKEND_DIR / "app" / "ai" / "shield_calibration.json"
    # Detective weights (scripts/train_detective.py) and their held-out quality.
    detective_weights: Path = _path("MEDSEAL_DETECTIVE_WEIGHTS", BACKEND_DIR / "weights" / "detective.pt")
    detective_metrics: Path = BACKEND_DIR / "app" / "ai" / "detective_metrics.json"


settings = Settings()
