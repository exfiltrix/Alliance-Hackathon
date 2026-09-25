"""Certify existing gateway devices with the local root key.

This is an administrative migration action and is intentionally separate from normal
startup. Set MEDSEAL_ADMIN_TOKEN before running it; the value is never printed.
"""
import argparse
import hmac

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal, init_engine
from app.models import Device
from app.seal import keys


def main() -> None:
    parser = argparse.ArgumentParser(description="Certify existing MedSeal devices")
    parser.add_argument("--authorization", default="", help="Bearer authorization value; defaults to MEDSEAL_ADMIN_TOKEN")
    args = parser.parse_args()
    supplied = args.authorization.removeprefix("Bearer ").strip()
    if not settings.admin_token or not hmac.compare_digest(supplied.encode(), settings.admin_token.encode()):
        raise SystemExit("Admin authorization is required; set MEDSEAL_ADMIN_TOKEN or pass --authorization")

    init_engine()
    keys.ensure_root_key()
    with SessionLocal() as session:
        devices = list(session.scalars(select(Device).order_by(Device.id)))
        changed = 0
        for device in devices:
            if keys.device_certificate_valid(device):
                continue
            keys.certify_device(device)
            changed += 1
        if changed:
            session.commit()
    print(f"certified devices: {changed}; total devices: {len(devices)}")


if __name__ == "__main__":
    main()
