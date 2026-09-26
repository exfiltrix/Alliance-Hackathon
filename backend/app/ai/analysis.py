"""AI reading of a verified chest X-ray: pathologies above a finding threshold + a referral hint.

Torch-free on purpose: takes the {pathology: score} dict from model.predict() and applies rules,
so the gating and referral logic is testable without the model.

Only a trusted image is read (status authentic and the shield saw no attack): reading a tampered
or attacked image would turn a forgery into a diagnosis. Texts live in the frontend dictionary
(verify.analysis); the API returns codes only.
"""

# Scores are op_thresh-calibrated (0.5 = the model's own cut-off), but on NIH images labelled
# "No Finding" 81% still have some pathology above 0.5 (3.7 on average). At 0.6: 17% of normal
# images get any finding vs 59% of images with findings (150 + 150 NIH images, 2026-09-26).
FINDING_THRESHOLD = 0.6
# Any finding this likely means "see a doctor urgently": 3% of normal images vs 28% of images
# with findings reach it (same 150 + 150 NIH images).
HIGH_RISK_THRESHOLD = 0.8

SPECIALTY = {
    "Atelectasis": "pulmonology",
    "Consolidation": "pulmonology",
    "Infiltration": "pulmonology",
    "Emphysema": "pulmonology",
    "Fibrosis": "pulmonology",
    "Effusion": "pulmonology",
    "Pneumonia": "pulmonology",
    "Pleural_Thickening": "pulmonology",
    "Lung Opacity": "pulmonology",
    "Cardiomegaly": "cardiology",
    "Edema": "cardiology",
    "Enlarged Cardiomediastinum": "cardiology",
    "Nodule": "oncology",
    "Mass": "oncology",
    "Lung Lesion": "oncology",
    "Pneumothorax": "thoracic_surgery",
    "Fracture": "traumatology",
    "Hernia": "surgery",
}
# Emergencies whatever the score: never fired on the normal images above.
URGENT = {"Pneumothorax", "Edema"}
URGENCY_ORDER = {"urgent": 0, "soon": 1, "routine": 2}


def _urgent(finding: dict) -> bool:
    return finding["pathology"] in URGENT or finding["probability"] >= HIGH_RISK_THRESHOLD


def blocked(reason: str) -> dict:
    """reason: the verify status (tampered/forged/unsigned) or attack_suspected / shield_unavailable."""
    return {"status": "blocked", "reason": reason}


def read(scores: dict[str, float]) -> dict:
    findings = sorted(
        ({"pathology": p, "probability": round(s, 3)} for p, s in scores.items() if s >= FINDING_THRESHOLD),
        key=lambda f: -f["probability"],
    )
    by_specialty: dict[str, list[dict]] = {}
    for f in findings:
        by_specialty.setdefault(SPECIALTY.get(f["pathology"], "general_practice"), []).append(f)
    referrals = [
        {
            "specialty": sp,
            "urgency": "urgent" if any(_urgent(f) for f in fs) else "soon",
            "pathologies": [f["pathology"] for f in fs],
        }
        for sp, fs in by_specialty.items()
    ] or [{"specialty": "general_practice", "urgency": "routine", "pathologies": []}]
    referrals.sort(key=lambda r: URGENCY_ORDER[r["urgency"]])
    # Overall advice: high = see a doctor as soon as possible; medium = see a doctor and follow
    # their advice; none = no signs of risk. Texts live in the frontend dictionary.
    risk = "high" if any(_urgent(f) for f in findings) else "medium" if findings else "none"
    return {
        "status": "done",
        "risk": risk,
        "experimental": True,
        "threshold": FINDING_THRESHOLD,
        "findings": findings,
        "referrals": referrals,
    }
