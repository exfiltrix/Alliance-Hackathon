import pytest

from tests.test_ai import SAMPLES, WEIGHTS


def builtin_model_id(client):
    models = client.get("/api/models").json()
    assert len(models) == 1 and models[0]["version"] == "densenet121-res224-all"
    return models[0]["id"]


def test_validation(client):
    mid = builtin_model_id(client)
    assert client.post("/api/crash-test", json={"model_id": 999}).status_code == 404
    assert client.post("/api/crash-test", json={"model_id": mid, "eps": [0]}).status_code == 422
    assert client.post("/api/crash-test", json={"model_id": mid, "method": "cw"}).status_code == 422
    assert client.get("/api/crash-test/999").status_code == 404


@pytest.mark.ai
@pytest.mark.skipif(not SAMPLES.exists() or not WEIGHTS.exists(), reason="needs samples and weights")
def test_crash_test_job(client):
    mid = builtin_model_id(client)
    r = client.post("/api/crash-test", json={"model_id": mid, "n_images": 3, "eps": [0.5, 2], "method": "pgd"})
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    # TestClient runs background tasks before returning, so the job is finished here
    res = client.get(f"/api/crash-test/{job_id}").json()
    assert res["status"] == "done", res
    assert res["n_images"] == 3
    assert set(res["flip_rate"]) == {"0.5", "1", "2"}  # eps=1 is always added for the score
    assert res["flip_rate"]["2"] == 1.0
    assert res["robustness_score"] == round(10 * (1 - res["flip_rate"]["1"]), 1)
    assert all(v > 40 for v in res["psnr"].values())
    ex = res["example"]
    assert ex["before_score"] < 0.5 < ex["after_score"]

    assert client.get("/api/crash-tests").json()[0]["job_id"] == job_id
    assert client.get("/api/stats").json()["models_tested"] == 1
