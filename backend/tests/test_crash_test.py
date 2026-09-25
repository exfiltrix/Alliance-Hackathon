import sys
import threading
import time
from pathlib import Path

import pytest

from tests.conftest import admin_headers

# tests.test_ai does `torch = pytest.importorskip("torch")` at module level, which raises
# Skipped on import when torch is absent. Importing SAMPLES/WEIGHTS from it at *this* module's
# top level used to let that Skipped exception cascade into here too, silently skipping every
# test below -- including the plain, non-AI ones (auth, validation, SEC-02 queueing) that have
# nothing to do with torch. These are recomputed locally instead (same definitions as
# tests/test_ai.py) so only the one @pytest.mark.ai test below is gated on torch/weights.
SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"
WEIGHTS = Path.home() / ".torchxrayvision" / "models_data"


def builtin_model_id(client):
    models = client.get("/api/models").json()
    assert len(models) == 1 and models[0]["version"] == "densenet121-res224-all"
    return models[0]["id"]


def test_crash_test_requires_admin_token(client):
    """P1-04: crash tests are an admin-only, credentialed action."""
    mid = builtin_model_id(client)
    assert client.post("/api/crash-test", json={"model_id": mid}).status_code == 401
    assert client.post(
        "/api/crash-test", json={"model_id": mid}, headers={"Authorization": "Bearer wrong"}
    ).status_code == 401


def test_validation(client):
    mid = builtin_model_id(client)
    h = admin_headers()
    assert client.post("/api/crash-test", json={"model_id": 999}, headers=h).status_code == 404
    assert client.post("/api/crash-test", json={"model_id": mid, "eps": [0]}, headers=h).status_code == 422
    assert client.post("/api/crash-test", json={"model_id": mid, "method": "cw"}, headers=h).status_code == 422
    assert client.get("/api/crash-test/999").status_code == 404  # reading status stays public


def test_second_crash_test_while_running_returns_409(client, monkeypatch):
    """SEC-02: the dedicated single worker holds one job at a time; a second POST while it is
    busy is refused with 409 instead of queuing on the shared request/DB thread pool. Uses a
    fake `app.ai.crash_test` module (via sys.modules) so this runs without torch installed."""
    mid = builtin_model_id(client)
    started = threading.Event()
    release = threading.Event()

    class FakeCrashTest:
        @staticmethod
        def run(n_images, eps, method, progress=None):
            started.set()
            assert release.wait(timeout=10), "test deadlocked waiting for release"
            return {
                "n_images": n_images, "method": method, "pathology": "Pneumonia", "eps": eps,
                "flip_rate": {str(e): 0.0 for e in eps}, "psnr": {str(e): 50.0 for e in eps},
                "robustness_score": 10.0,
            }

    monkeypatch.setitem(sys.modules, "app.ai.crash_test", FakeCrashTest)
    h = admin_headers()
    body = {"model_id": mid, "n_images": 1, "eps": [1], "method": "pgd"}

    r1 = client.post("/api/crash-test", json=body, headers=h)
    assert r1.status_code == 202
    assert started.wait(timeout=5), "worker never picked up the first job"

    r2 = client.post("/api/crash-test", json=body, headers=h)
    assert r2.status_code == 409

    release.set()
    job_id = r1.json()["job_id"]
    status = None
    for _ in range(100):
        status = client.get(f"/api/crash-test/{job_id}").json()
        if status["status"] == "done":
            break
        time.sleep(0.05)
    assert status["status"] == "done", status

    # the worker is free again now that the first job finished
    r3 = client.post("/api/crash-test", json=body, headers=h)
    assert r3.status_code == 202
    started.wait(timeout=5)
    release.set()
    for _ in range(100):
        if client.get(f"/api/crash-test/{r3.json()['job_id']}").json()["status"] == "done":
            break
        time.sleep(0.05)


@pytest.mark.ai
@pytest.mark.skipif(not SAMPLES.exists() or not WEIGHTS.exists(), reason="needs samples and weights")
def test_crash_test_job(client):
    mid = builtin_model_id(client)
    r = client.post(
        "/api/crash-test", json={"model_id": mid, "n_images": 3, "eps": [0.5, 2], "method": "pgd"},
        headers=admin_headers(),
    )
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    # SEC-02: the job runs on a dedicated worker thread, not on the request's own thread, so
    # it is not necessarily finished the instant POST returns — poll with a timeout instead of
    # assuming TestClient's old BackgroundTasks-are-synchronous behaviour (rule 2: this test
    # previously asserted the job was already "done" right after the POST; SEC-02 replaced the
    # BackgroundTasks-based worker with a dedicated ThreadPoolExecutor, so that assumption no
    # longer holds and the test now polls).
    res = None
    for _ in range(600):  # up to 60s: real PGD on a handful of images
        res = client.get(f"/api/crash-test/{job_id}").json()
        if res["status"] in ("done", "error"):
            break
        time.sleep(0.1)
    assert res["status"] == "done", res
    assert res["n_images"] == 3
    assert res["n_requested"] == 3
    assert res["protocol_compliant"] is False  # n_images=3 < the passport protocol's minimum of 50
    assert set(res["flip_rate"]) == {"0.5", "1", "2"}  # eps=1 is always added for the score
    assert res["flip_rate"]["2"] == 1.0
    assert res["robustness_score"] == round(10 * (1 - res["flip_rate"]["1"]), 1)
    assert all(v > 40 for v in res["psnr"].values())
    ex = res["example"]
    assert ex["before_score"] < 0.5 < ex["after_score"]

    assert client.get("/api/crash-tests").json()[0]["job_id"] == job_id
    assert client.get("/api/stats").json()["models_tested"] == 1
