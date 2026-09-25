"""Creates the demo gateway device directly (no HTTP, no admin token needed) and prints its
bearer token once. Put the token in by_billy/frontend/.env.local as MEDSEAL_DEVICE_TOKEN.

Run from backend/: .venv/bin/python -m scripts.create_demo_device [name] [hospital]
"""
import sys

from app.auth import hash_token, new_device_token
from app.db import SessionLocal, init_engine
from app.models import Device
from app.seal import keys


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "KT-01"
    hospital = sys.argv[2] if len(sys.argv) > 2 else "Namangan viloyat shifoxonasi"

    init_engine()
    with SessionLocal() as session:
        device = Device(name=name, hospital=hospital, public_key_hex="")
        session.add(device)
        session.flush()
        device.public_key_hex = keys.create_device_key(device.id)
        token = new_device_token()
        device.token_hash = hash_token(token)
        session.commit()

        print(f"Device #{device.id} '{name}' created.")
        print(f"MEDSEAL_DEVICE_TOKEN={token}")
        print("(shown once — store it in by_billy/frontend/.env.local; it is not recoverable from the DB)")


if __name__ == "__main__":
    main()
