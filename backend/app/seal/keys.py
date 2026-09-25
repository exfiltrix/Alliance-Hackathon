"""Gateway key store.

Private keys are read and written only here and used only by app.seal.service.
They are never logged, never returned by the API and never leave this module
except as an in-memory key object for signing. In production this is an HSM/TPM.
"""
import os

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from app.config import settings


def _key_path(device_id: int):
    return settings.keys_dir / f"device_{device_id}.pem"


def create_device_key(device_id: int) -> str:
    """Generate and store a key pair for a device. Returns only the public key (hex)."""
    key = Ed25519PrivateKey.generate()
    settings.keys_dir.mkdir(parents=True, exist_ok=True)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    path = _key_path(device_id)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(pem)
    return public_key_hex(key.public_key())


def load_private_key(device_id: int) -> Ed25519PrivateKey:
    path = _key_path(device_id)
    if not path.exists():
        raise KeyError(f"no private key for device {device_id}")
    return serialization.load_pem_private_key(path.read_bytes(), password=None)


def public_key_hex(pub: Ed25519PublicKey) -> str:
    return pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()


def public_key_from_hex(hex_str: str) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(bytes.fromhex(hex_str))
