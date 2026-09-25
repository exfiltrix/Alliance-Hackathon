"""Gateway and root key material.

Private keys are read and written only here and used only by the signing modules.
They are never logged, never returned by the API and never leave this module except
as an in-memory key object. In production the root/device private keys belong in an
HSM/TPM; the local files are a demo-only stand-in.
"""
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from app.config import settings
from app.models import Device, iso_utc


CERT_PREFIX = b"MEDSEAL-DEVICE-v1\n"


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _key_path(device_id: int) -> Path:
    return settings.keys_dir / f"device_{device_id}.pem"


def _write_private(path: Path, key: Ed25519PrivateKey) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    tmp = path.with_name(f".{path.name}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(pem)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def _write_public(path: Path, key: Ed25519PublicKey) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pem = key.public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    tmp = path.with_name(f".{path.name}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(pem)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def create_device_key(device_id: int) -> str:
    """Generate and store a device key pair. Returns only the public key (hex)."""
    key = Ed25519PrivateKey.generate()
    _write_private(_key_path(device_id), key)
    return public_key_hex(key.public_key())


def load_private_key(device_id: int) -> Ed25519PrivateKey:
    path = _key_path(device_id)
    if not path.exists():
        raise KeyError(f"no private key for device {device_id}")
    key = serialization.load_pem_private_key(path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError(f"device key {device_id} is not Ed25519")
    return key


def public_key_hex(pub: Ed25519PublicKey) -> str:
    return pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()


def public_key_from_hex(hex_str: str) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(bytes.fromhex(hex_str))


def root_key_exists() -> bool:
    return settings.root_key_path.exists() and settings.root_pubkey_path.exists()


def ensure_root_key() -> None:
    """Create the local demo root key once, without ever replacing an existing trust root."""
    if not root_key_exists():
        create_root_key()


def create_root_key(force: bool = False) -> None:
    """Create root.pem/root.pub atomically; refuse an implicit overwrite by default."""
    private_path, public_path = settings.root_key_path, settings.root_pubkey_path
    if not force and (private_path.exists() or public_path.exists()):
        raise FileExistsError("root key already exists; refusing to overwrite the trust root")
    key = Ed25519PrivateKey.generate()
    _write_private(private_path, key)
    _write_public(public_path, key.public_key())


def load_root_private_key() -> Ed25519PrivateKey:
    if not settings.root_key_path.exists():
        raise KeyError("root key is not configured; run python -m scripts.create_root_key")
    key = serialization.load_pem_private_key(settings.root_key_path.read_bytes(), password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("root key is not Ed25519")
    return key


def load_root_public_key() -> Ed25519PublicKey:
    if not settings.root_pubkey_path.exists():
        raise KeyError("root public key is not configured")
    key = serialization.load_pem_public_key(settings.root_pubkey_path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError("root public key is not Ed25519")
    return key


def sign_root(message: bytes) -> bytes:
    return load_root_private_key().sign(message)


def verify_root(signature: bytes, message: bytes) -> bool:
    try:
        load_root_public_key().verify(signature, message)
    except Exception:
        return False
    return True


def device_certificate_message(device: Device) -> bytes:
    return CERT_PREFIX + canonical_json(
        {
            "device_id": device.id,
            "name": device.name,
            "hospital": device.hospital,
            "public_key_hex": device.public_key_hex,
            "created_at": iso_utc(device.created_at),
        }
    )


def certify_device(device: Device) -> str:
    signature = sign_root(device_certificate_message(device))
    device.cert_sig_hex = signature.hex()
    return device.cert_sig_hex


def device_certificate_valid(device: Device) -> bool:
    if not device.cert_sig_hex:
        return False
    try:
        signature = bytes.fromhex(device.cert_sig_hex)
    except ValueError:
        return False
    return verify_root(signature, device_certificate_message(device))
