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
    max_upload_bytes: int = 50 * 1024 * 1024


settings = Settings()
