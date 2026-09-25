"""Small dependency-free confidence-interval helpers for calibration reports."""
import math


def _binom_cdf(successes: int, trials: int, probability: float) -> float:
    return sum(
        math.comb(trials, k) * probability**k * (1.0 - probability) ** (trials - k)
        for k in range(successes + 1)
    )


def clopper_pearson(successes: int, trials: int, confidence: float = 0.95) -> tuple[float, float]:
    """Exact two-sided binomial interval using bisection and the stdlib only."""
    if not 0 <= successes <= trials or trials <= 0:
        raise ValueError("successes must be between zero and trials")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between zero and one")
    alpha = 1.0 - confidence
    lower = 0.0
    if successes > 0:
        lo, hi = 0.0, successes / trials
        for _ in range(80):
            mid = (lo + hi) / 2.0
            if _binom_cdf(successes - 1, trials, mid) > 1.0 - alpha / 2.0:
                lo = mid
            else:
                hi = mid
        lower = (lo + hi) / 2.0

    upper = 1.0
    if successes < trials:
        lo, hi = successes / trials, 1.0
        for _ in range(80):
            mid = (lo + hi) / 2.0
            if _binom_cdf(successes, trials, mid) > alpha / 2.0:
                lo = mid
            else:
                hi = mid
        upper = (lo + hi) / 2.0
    return lower, upper
