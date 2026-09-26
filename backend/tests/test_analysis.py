"""AI reading + referral on /verify: rules (no model needed) and the trusted-image gate."""
import pytest

from app.ai import analysis, hooks
from app.config import settings
from tests.conftest import png_pixels, replace_png_pixels, xray_png

ALL_LOW = {p: 0.3 for p in analysis.SPECIALTY}


def test_no_findings_is_a_routine_general_practice_referral():
    r = analysis.read(ALL_LOW)
    assert r["status"] == "done" and r["experimental"] is True
    assert r["findings"] == []
    assert r["risk"] == "none"
    assert r["referrals"] == [{"specialty": "general_practice", "urgency": "routine", "pathologies": []}]


def test_scores_between_05_and_threshold_are_not_findings():
    """0.5 is the model's own cut-off, but on normal NIH images it fires 3.7 times per image."""
    assert analysis.read(ALL_LOW | {"Pneumonia": 0.59})["findings"] == []


def test_findings_are_grouped_by_specialty_and_sorted():
    r = analysis.read(ALL_LOW | {"Pneumonia": 0.7, "Effusion": 0.75, "Cardiomegaly": 0.65})
    assert [f["pathology"] for f in r["findings"]] == ["Effusion", "Pneumonia", "Cardiomegaly"]
    by = {x["specialty"]: x for x in r["referrals"]}
    assert by["pulmonology"]["pathologies"] == ["Effusion", "Pneumonia"]
    assert by["cardiology"]["urgency"] == "soon"


@pytest.mark.parametrize(
    "scores,risk",
    [
        ({}, "none"),
        ({"Pneumonia": 0.65}, "medium"),  # a finding: see a doctor
        ({"Pneumonia": 0.65, "Mass": 0.79}, "medium"),
        ({"Mass": 0.8}, "high"),  # very likely finding: as soon as possible
        ({"Edema": 0.61}, "high"),  # emergency pathology whatever the score
        ({"Pneumothorax": 0.6}, "high"),
    ],
)
def test_overall_risk(scores, risk):
    r = analysis.read(ALL_LOW | scores)
    assert r["risk"] == risk
    # the referral list agrees with the overall advice
    assert (r["referrals"][0]["urgency"] == "urgent") == (risk == "high")


def test_pneumothorax_is_urgent_and_listed_first():
    r = analysis.read(ALL_LOW | {"Cardiomegaly": 0.7, "Pneumothorax": 0.61})
    assert r["referrals"][0] == {"specialty": "thoracic_surgery", "urgency": "urgent", "pathologies": ["Pneumothorax"]}


def test_every_model_pathology_has_a_specialty():
    torch = pytest.importorskip("torch")  # noqa: F841
    pytest.importorskip("torchxrayvision")
    from app.ai import model

    assert set(model.pathologies()) == set(analysis.SPECIALTY)


# --- the gate on /verify, with the AI hooks stubbed ------------------------------------------------

DONE = analysis.read(ALL_LOW | {"Pneumonia": 0.8})


@pytest.fixture
def ai(monkeypatch):
    """AI on, shield clean, analysis stubbed; tests flip the shield via ai['attack']."""
    state = {"attack": False}
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(hooks, "run_detective", lambda px: None)
    monkeypatch.setattr(hooks, "run_shield", lambda px: {"attack_suspected": state["attack"], "score": 0, "threshold": 1})
    monkeypatch.setattr(hooks, "run_analysis", lambda px: DONE)
    return state


def _seal(client, device, data: bytes) -> bytes:
    seal = client.post("/api/seal", files={"file": ("x.png", data)}, headers=device["auth"]).json()
    return client.get(seal["download_url"], headers=device["auth"]).content


def _verify(client, data: bytes) -> dict:
    return client.post("/api/verify", files={"file": ("x.png", data)}).json()


def test_authentic_image_gets_the_analysis(client, device, ai):
    r = _verify(client, _seal(client, device, xray_png(seed=11)))
    assert r["status"] == "authentic"
    assert r["analysis"] == DONE


def test_tampered_image_is_not_read(client, device, ai):
    sealed = _seal(client, device, xray_png(seed=12))
    px = png_pixels(sealed).copy()
    px[100:110, 100:110] = 255
    r = _verify(client, replace_png_pixels(sealed, px))
    assert r["status"] == "tampered"
    assert r["analysis"] == {"status": "blocked", "reason": "tampered"}


def test_unsigned_image_is_not_read(client, ai):
    r = _verify(client, xray_png(seed=13))
    assert r["status"] == "unsigned"
    assert r["analysis"] == {"status": "blocked", "reason": "unsigned"}


def test_attacked_image_is_not_read_even_when_authentic(client, device, ai):
    ai["attack"] = True
    r = _verify(client, _seal(client, device, xray_png(seed=14)))
    assert r["status"] == "authentic"
    assert r["analysis"] == {"status": "blocked", "reason": "attack_suspected"}


def test_no_shield_means_no_reading(client, device, ai, monkeypatch):
    monkeypatch.setattr(hooks, "run_shield", lambda px: None)
    r = _verify(client, _seal(client, device, xray_png(seed=15)))
    assert r["analysis"] == {"status": "blocked", "reason": "shield_unavailable"}


def test_ai_switched_off_returns_null(client, device):
    r = _verify(client, _seal(client, device, xray_png(seed=16)))
    assert r["analysis"] is None


def test_inbox_shows_the_risk_of_a_trusted_image(client, device, ai):
    """The doctor's inbox (auto-verified uploads and watched folders) carries the overall advice."""
    from tests.conftest import doctor_headers

    sealed = _seal(client, device, xray_png(seed=17))
    item = client.post("/api/inbox", files={"files": ("x.png", sealed)}, headers=doctor_headers()).json()[0]
    assert item["risk"] == DONE["risk"] == "high"  # Pneumonia 0.8
    unsigned = client.post("/api/inbox", files={"files": ("u.png", xray_png(seed=18))}, headers=doctor_headers()).json()[0]
    assert unsigned["risk"] is None  # not read: origin unknown
