"""Root signatures for issued model passports."""
import hashlib
import json

from app.models import Passport, iso_utc
from app.seal import keys
from app.seal.signing import passport_message


def message_for(p: Passport) -> bytes:
    return passport_message(
        report=json.loads(p.report_json or "{}"),
        passport_id=p.id,
        created_at=iso_utc(p.created_at),
        organisation=p.organisation,
    )


def fingerprint(p: Passport) -> str:
    return hashlib.sha256(message_for(p)).hexdigest()[:16]


def sign(p: Passport) -> str:
    p.signature_hex = keys.sign_root(message_for(p)).hex()
    return p.signature_hex


def verify(p: Passport) -> bool:
    if not p.signature_hex:
        return False
    try:
        signature = bytes.fromhex(p.signature_hex)
    except ValueError:
        return False
    return keys.verify_root(signature, message_for(p))
