"""Bayesian Knowledge Tracing (BKT) service.

Provides pure-mathematics functions for:
- Difficulty-calibrated slip/guess parameters
- Beta-Bernoulli posterior updates (Bayesian)
- Sequential BKT over multiple observations
- Posterior variance, confidence, and information gain
- Prior conversion from existing mastery scores

All functions are stateless and deterministic — no database dependencies.
"""
from __future__ import annotations

import math
from typing import Optional


# ---------------------------------------------------------------------------
# Slip / Guess calibration by difficulty
# ---------------------------------------------------------------------------

def slip_guess_for_difficulty(difficulty: int) -> tuple[float, float]:
    """Return (P_slip, P_guess) calibrated by question difficulty.

    P_slip  = P(incorrect | knows)   — chance of a careless mistake
    P_guess = P(correct  | not_know) — chance of a lucky guess

    Harder questions have lower guess probability and higher slip probability,
    meaning a correct answer to a hard question is stronger evidence of mastery.

    Parameters
    ----------
    difficulty : int
        Question difficulty 1–5 (1 = easiest, 5 = hardest).

    Returns
    -------
    tuple[float, float]
        (P_slip, P_guess) both in [0.0, 1.0].
    """
    table = {
        1: (0.05, 0.40),   # Easy: low slip, high guess (single-choice = 0.25 baseline)
        2: (0.08, 0.30),
        3: (0.10, 0.20),
        4: (0.12, 0.15),
        5: (0.15, 0.10),   # Hard: higher slip, very low guess
    }
    clamped = max(1, min(5, difficulty))
    return table[clamped]


# ---------------------------------------------------------------------------
# Single-step BKT update
# ---------------------------------------------------------------------------

def bkt_update(prior_p_know: float, is_correct: bool, difficulty: int) -> float:
    """Single-step Bayesian Knowledge Tracing update.

    Uses Bayes' rule:
      P(know | outcome) = P(outcome | know) × P(know) / P(outcome)

    where:
      P(correct | know)     = 1 − P_slip
      P(correct | not_know) = P_guess
      P(incorrect | know)   = P_slip
      P(incorrect | not_know) = 1 − P_guess

    Parameters
    ----------
    prior_p_know : float
        Prior probability that the learner knows the skill (0–1).
    is_correct : bool
        Whether the answer was correct.
    difficulty : int
        Question difficulty 1–5.

    Returns
    -------
    float
        Posterior P(know | outcome) clamped to [0.02, 0.98] to avoid
        degenerate 0/1 states.
    """
    p_slip, p_guess = slip_guess_for_difficulty(difficulty)
    p_know = max(0.01, min(0.99, prior_p_know))

    if is_correct:
        p_outcome_given_know = 1.0 - p_slip
        p_outcome = p_outcome_given_know * p_know + p_guess * (1.0 - p_know)
        posterior = p_outcome_given_know * p_know / max(p_outcome, 1e-12)
    else:
        p_outcome_given_know = p_slip
        p_outcome = p_outcome_given_know * p_know + (1.0 - p_guess) * (1.0 - p_know)
        posterior = p_outcome_given_know * p_know / max(p_outcome, 1e-12)

    return round(max(0.02, min(0.98, posterior)), 4)


# ---------------------------------------------------------------------------
# Sequential BKT
# ---------------------------------------------------------------------------

def bkt_sequence(
    observations: list[tuple[bool, int]],
    prior: float = 0.5,
) -> float:
    """Run sequential BKT updates over a list of (is_correct, difficulty) observations.

    Each observation updates the posterior, which becomes the prior for the next.

    Parameters
    ----------
    observations : list[tuple[bool, int]]
        List of (is_correct, difficulty) tuples, in chronological order.
    prior : float
        Initial P(know) before any observations.

    Returns
    -------
    float
        Final posterior P(know) after processing all observations.
    """
    p = prior
    for is_correct, difficulty in observations:
        p = bkt_update(p, is_correct, difficulty)
    return p


# ---------------------------------------------------------------------------
# Beta distribution helpers
# ---------------------------------------------------------------------------

def _bkt_to_beta(p_know: float, effective_n: int) -> tuple[float, float]:
    """Map P(know) and effective sample size to Beta(α, β) parameters.

    α / (α + β) = p_know  and  α + β = effective_n.
    """
    n = max(2, effective_n)
    alpha = p_know * n
    beta = (1.0 - p_know) * n
    # Minimum 0.5 to avoid degenerate variance
    return max(0.5, alpha), max(0.5, beta)


def beta_variance(alpha: float, beta_val: float) -> float:
    """Variance of Beta(α, β) distribution."""
    total = alpha + beta_val
    return (alpha * beta_val) / (total * total * (total + 1.0))


def bkt_posterior_variance(p_know: float, effective_n: int) -> float:
    """Approximate posterior variance from P(know) and evidence count.

    Maps P(know) to a Beta(α, β) distribution where α+β = effective_n,
    then computes the Beta variance.

    Parameters
    ----------
    p_know : float
        Current P(know) estimate (0–1).
    effective_n : int
        Effective number of observations (evidence count).

    Returns
    -------
    float
        Posterior variance.
    """
    alpha, beta_param = _bkt_to_beta(p_know, effective_n)
    return beta_variance(alpha, beta_param)


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------

def bkt_confidence(p_know: float, evidence_count: int) -> float:
    """Bayesian confidence from posterior variance.

    confidence = 1 − 2 × √(variance)  →  bounded to [0.5, 0.98].

    More evidence → narrower posterior → lower variance → higher confidence.
    A uniform prior (α=1, β=1) with no evidence gives variance ≈ 0.083,
    confidence ≈ 0.5.

    Parameters
    ----------
    p_know : float
        Current P(know) (0–1).
    evidence_count : int
        Total weighted evidence count (α + β).

    Returns
    -------
    float
        Confidence in [0.5, 0.98].
    """
    variance = bkt_posterior_variance(p_know, max(2, evidence_count))
    raw = 1.0 - 2.0 * math.sqrt(variance)
    return round(max(0.50, min(0.98, raw)), 2)


# ---------------------------------------------------------------------------
# Information gain (for next-question recommendation)
# ---------------------------------------------------------------------------

def information_gain(p_know: float, difficulty: int) -> float:
    """Expected information gain from asking one more question.

    IG = H(prior) − E[H(posterior)]

    where H(p) = −p·log₂(p) − (1−p)·log₂(1−p) is the binary entropy,
    and the expectation is over the possible outcomes (correct/incorrect).

    Questions at the difficulty where P(know) ≈ 0.5 yield maximum IG.
    For a learner who likely knows (p ≈ 0.9), easy questions yield low IG
    (we already know they'll get it right); hard questions challenge them.

    Parameters
    ----------
    p_know : float
        Current P(know) (0–1).
    difficulty : int
        Question difficulty 1–5.

    Returns
    -------
    float
        Expected information gain in bits.
    """
    p = max(0.02, min(0.98, p_know))
    p_slip, p_guess = slip_guess_for_difficulty(difficulty)

    # Current entropy
    def _entropy(prob: float) -> float:
        if prob <= 0.0 or prob >= 1.0:
            return 0.0
        return -(prob * math.log2(prob) + (1.0 - prob) * math.log2(1.0 - prob))

    h_current = _entropy(p)

    # P(correct) = P(correct|know)*P(know) + P(correct|not_know)*P(not_know)
    p_correct = (1.0 - p_slip) * p + p_guess * (1.0 - p)

    # Posterior | correct
    p_know_given_correct = bkt_update(p, True, difficulty)
    # Posterior | incorrect
    p_know_given_incorrect = bkt_update(p, False, difficulty)

    h_expected = p_correct * _entropy(p_know_given_correct) + (1.0 - p_correct) * _entropy(p_know_given_incorrect)

    ig = h_current - h_expected
    return round(max(0.0, ig), 4)


# ---------------------------------------------------------------------------
# Prior conversion from existing mastery data
# ---------------------------------------------------------------------------

def bkt_prior_from_existing(mastery_score: Optional[float]) -> float:
    """Convert existing mastery_score (0–100) to a BKT prior P(know).

    Parameters
    ----------
    mastery_score : float or None
        Existing mastery score 0–100, or None if no prior record exists.

    Returns
    -------
    float
        P(know) prior in [0.1, 0.95].
        Returns 0.5 (uniform/uninformed) when no prior exists.
    """
    if mastery_score is None:
        return 0.5
    # Clamp away from extremes — no one is 0% or 100% certain to know
    p = mastery_score / 100.0
    return max(0.10, min(0.95, p))


# ---------------------------------------------------------------------------
# Beta-Bernoulli mastery estimate (packaged result)
# ---------------------------------------------------------------------------

def skill_estimate(
    alpha: float,
    beta_param: float,
    skill_name: str = "",
) -> dict:
    """Build a rich mastery estimate from Beta(α, β) parameters.

    Parameters
    ----------
    alpha : float
        Beta α parameter (pseudo-counts of correct evidence).
    beta_param : float
        Beta β parameter (pseudo-counts of incorrect evidence).
    skill_name : str
        Optional human-readable skill name.

    Returns
    -------
    dict with keys:
        p_know, uncertainty, confidence, evidence_strength, level, name
    """
    total = alpha + beta_param
    p_know = alpha / total
    variance = beta_variance(alpha, beta_param)
    uncertainty = round(math.sqrt(variance), 4)
    confidence = round(max(0.50, min(0.98, 1.0 - 2.0 * uncertainty)), 2)

    if p_know >= 0.85 and confidence >= 0.70:
        level = "mastered"
    elif p_know >= 0.70:
        level = "proficient"
    elif p_know >= 0.40:
        level = "developing"
    else:
        level = "novice"

    return {
        "p_know": round(p_know, 4),
        "score": round(p_know * 100.0, 1),  # backward-compat 0–100 scale
        "uncertainty": uncertainty,
        "confidence": confidence,
        "evidence_strength": round(total, 1),
        "level": level,
        "name": skill_name,
    }


# ---------------------------------------------------------------------------
# Difficulty-weighted Beta update
# ---------------------------------------------------------------------------

def beta_update(
    alpha: float,
    beta_param: float,
    difficulty: int,
    is_correct: bool,
) -> tuple[float, float]:
    """Update Beta(α, β) parameters with a difficulty-weighted observation.

    Harder questions carry more weight:
        weight = 1.0 + 0.3 × (difficulty − 2)
        range [0.7, 1.9] for difficulty 1–5.

    Correct answer → α += weight
    Wrong answer → β += weight

    Parameters
    ----------
    alpha : float
        Current Beta α.
    beta_param : float
        Current Beta β.
    difficulty : int
        Question difficulty 1–5.
    is_correct : bool
        Whether the answer was correct.

    Returns
    -------
    tuple[float, float]
        (new_alpha, new_beta).
    """
    weight = 1.0 + 0.3 * (max(1, min(5, difficulty)) - 2)
    if is_correct:
        return alpha + weight, beta_param
    else:
        return alpha, beta_param + weight


def prior_from_mastery_record(record: Optional[dict]) -> tuple[float, float]:
    """Convert a stored mastery record to Beta(α, β) parameters.

    Expected record format (from MasteryState + mastery_state dict):
        {"score": float, "confidence": float, "evidence_count": int | None}

    If no record, returns cold start prior (α=1, β=1 → P=0.5, max uncertainty).

    Parameters
    ----------
    record : dict or None
        Mastery record, or None for cold start.

    Returns
    -------
    tuple[float, float]
        (alpha, beta) parameters.
    """
    if record is None:
        return 1.0, 1.0  # uniform prior

    score = record.get("score", 50.0)
    evidence = max(1, record.get("evidence_count", 1))

    p = score / 100.0
    p = max(0.05, min(0.95, p))

    alpha = p * evidence
    beta_param = (1.0 - p) * evidence
    return max(0.5, alpha), max(0.5, beta_param)
