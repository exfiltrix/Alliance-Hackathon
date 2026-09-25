"""End-to-end demo smoke test using only temporary state.

Run from backend/:
    .venv/bin/python -m scripts.demo_smoke

The script never touches the real database, key directory, storage directory, or anchor file.
It intentionally writes the passport crash-test row directly so the smoke test does not need
torch, model weights, or a downloaded dataset.
"""
import io
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, PngImagePlugin


def _set_temp_environment(root: Path) -> None:
    os.environ.update(
        {
            "MEDSEAL_DB_URL": f"sqlite:///{root / 'smoke.db'}",
            "MEDSEAL_KEYS_DIR": str(root / "keys"),
            "MEDSEAL_STORAGE_DIR": str(root / "storage"),
            "MEDSEAL_ROOT_KEY_PATH": str(root / "keys" / "root.pem"),
            "MEDSEAL_ROOT_PUBKEY_PATH": str(root / "keys" / "root.pub"),
            "MEDSEAL_ANCHOR_PATH": str(root / "anchors" / "anchors.jsonl"),
            "MEDSEAL_ADMIN_TOKEN": "smoke-admin-token",
            "MEDSEAL_AI": "0",
            "MEDSEAL_REQUIRE_DEVICE_CERT": "1",
        }
    )


def _png(size: int = 256) -> bytes:
    import numpy as np

    yy, xx = np.mgrid[0:size, 0:size]
    pixels = np.clip(70 + 100 * np.exp(-(((yy - size / 2) / 40) ** 2 + ((xx - size / 2) / 55) ** 2)), 0, 255).astype("uint8")
    out = io.BytesIO()
    Image.fromarray(pixels, "L").save(out, "PNG")
    return out.getvalue()


def _replace_pixels(data: bytes, pixels) -> bytes:
    image = Image.open(io.BytesIO(data))
    info = PngImagePlugin.PngInfo()
    for key, value in image.text.items():
        info.add_text(key, value)
    out = io.BytesIO()
    Image.fromarray(pixels, image.mode).save(out, "PNG", pnginfo=info)
    return out.getvalue()


def _strip_uid(data: bytes) -> bytes:
    image = Image.open(io.BytesIO(data))
    out = io.BytesIO()
    Image.fromarray(np.array(image), image.mode).save(out, "PNG")
    return out.getvalue()


def main() -> int:
    failures: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        if condition:
            print(f"PASS: {name}")
        else:
            message = f"{name}: {detail}" if detail else name
            failures.append(message)
            print(f"FAIL: {message}")

    with tempfile.TemporaryDirectory(prefix="medseal-smoke-") as temp:
        _set_temp_environment(Path(temp))
        from fastapi.testclient import TestClient
        from sqlalchemy import select

        from app import db
        from app.main import app
        from app.models import AIModel, CrashTest, Seal
        from app.seal import keys, ledger

        keys.create_root_key()
        with TestClient(app) as client:
            admin = {"Authorization": "Bearer smoke-admin-token"}
            model_response = client.get("/api/models").json()
            check("models endpoint", bool(model_response), "no model was seeded")

            device_response = client.post(
                "/api/devices", json={"name": "Smoke scanner", "hospital": "Smoke hospital"}, headers=admin
            )
            check("certified device creation", device_response.status_code == 201, device_response.text)
            device = device_response.json()
            device_headers = {"Authorization": f"Bearer {device['token']}"}

            original = _png()
            seal_response = client.post("/api/seal", files={"file": ("smoke.png", original)}, headers=device_headers)
            check("seal", seal_response.status_code == 200, seal_response.text)
            seal_body = seal_response.json()
            sealed = client.get(seal_body["download_url"], headers=device_headers).content
            check("authenticated download", client.get(seal_body["download_url"], headers=device_headers).status_code == 200)

            verified = client.post("/api/verify", files={"file": ("smoke.png", sealed)}).json()
            check("authentic verification", verified.get("status") == "authentic", str(verified))

            pixels = np.array(Image.open(io.BytesIO(sealed)))
            pixels[140, 70] ^= 1
            tampered = _replace_pixels(sealed, pixels)
            tampered_result = client.post("/api/verify", files={"file": ("tampered.png", tampered)}).json()
            check("tamper with UID", tampered_result.get("status") == "tampered", str(tampered_result))
            check("tamper tile", tampered_result.get("changed_tiles") == [[128, 64]], str(tampered_result))

            stripped = _strip_uid(tampered)
            stripped_result = client.post("/api/verify", files={"file": ("stripped.png", stripped)}).json()
            check(
                "tamper without UID",
                stripped_result.get("status") == "tampered" and stripped_result.get("reason") == "seal_id_removed",
                str(stripped_result),
            )

            resaved = _strip_uid(sealed)
            resaved_result = client.post("/api/verify", files={"file": ("resaved.png", resaved)}).json()
            check(
                "content-authentic resave",
                resaved_result.get("status") == "authentic" and resaved_result.get("warning") == "seal_id_missing",
                str(resaved_result),
            )

            with db.SessionLocal() as session:
                row = session.scalar(select(Seal).order_by(Seal.id))
                row.root_hex = "f" * 64
                row.entry_hash = ledger.entry_hash(row.prev_hash, row)
                session.commit()
            chain = client.get("/api/ledger/check").json()
            check("external anchor detects rewrite", chain.get("ok") is False, str(chain))
            check("anchor mismatch is reported", chain.get("anchor_mismatch") == [seal_body["seal_id"]], str(chain))

            with db.SessionLocal() as session:
                model = session.scalar(select(AIModel))
                crash = CrashTest(
                    model_id=model.id,
                    n_images=50,
                    results_json=(
                        '{"n_requested":50,"n_images":50,"method":"pgd","pathology":"Pneumonia",'
                        '"data":["synthetic"],"eps":[0.5,1,2,4],"flip_rate":{"0.5":0.2,"1":0.98,"2":1,"4":1},'
                        '"psnr":{"0.5":55,"1":50,"2":48,"4":45},"robustness_score":0.2}'
                    ),
                    robustness_score=0.2,
                )
                session.add(crash)
                session.commit()
                crash_id = crash.id
                model_id = model.id
            passport_response = client.post(
                "/api/passport", json={"model_id": model_id, "crash_test_id": crash_id}, headers=admin
            )
            check("passport issue", passport_response.status_code == 201, passport_response.text)
            passport = passport_response.json()
            verification = client.get(f"/api/passport/{passport['id']}/verify").json()
            check("passport signature", verification.get("valid") is True, str(verification))
            check("passport fingerprint", bool(passport.get("fingerprint")), str(passport))

    if failures:
        print(f"SMOKE FAILED: {len(failures)} check(s)")
        return 1
    print("SMOKE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
