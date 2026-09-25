from app.ai.statistics import clopper_pearson


def test_clopper_pearson_matches_reference_intervals():
    lower, upper = clopper_pearson(29, 29)
    assert abs(lower - 0.880555) < 1e-5
    assert upper == 1.0

    lower, upper = clopper_pearson(4, 450)
    assert abs(lower - 0.002427) < 1e-5
    assert abs(upper - 0.022602) < 1e-5


def test_clopper_pearson_handles_boundaries():
    assert clopper_pearson(0, 10)[0] == 0.0
    assert clopper_pearson(10, 10)[1] == 1.0
