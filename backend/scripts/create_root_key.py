"""Create the local demo root signing key.

Usage from backend/:
    .venv/bin/python -m scripts.create_root_key
    .venv/bin/python -m scripts.create_root_key --force  # explicit rotation; invalidates old trust
"""
import argparse

from app.config import settings
from app.seal import keys


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the MedSeal root signing key")
    parser.add_argument("--force", action="store_true", help="overwrite an existing root key (explicit rotation)")
    args = parser.parse_args()
    keys.create_root_key(force=args.force)
    print(f"root public key: {settings.root_pubkey_path}")
    print(f"root private key: {settings.root_key_path} (mode 0600; never commit it)")


if __name__ == "__main__":
    main()
