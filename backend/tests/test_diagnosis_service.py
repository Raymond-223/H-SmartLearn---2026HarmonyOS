"""Unit tests for BKT service and diagnosis agent logic."""
import pytest
from app.services.bkt_service import (
    slip_guess_for_difficulty,
    bkt_update,
    bkt_sequence,
    bkt_confidence,
    information_gain,
    bkt_prior_from_existing,
    beta_update,
    prior_from_mastery_record,
    skill_estimate,
)


class TestSlipGuess:
    def test_easy_has_high_guess(self):
        slip, guess = slip_guess_for_difficulty(1)
        assert guess > 0.30  # Easy questions: more guessable
        assert slip < 0.10   # Easy: low slip

    def test_hard_has_low_guess(self):
        slip, guess = slip_guess_for_difficulty(5)
        assert guess < 0.15  # Hard questions: hard to guess
        assert slip > 0.10   # Hard: higher slip

    def test_monotonic_guess(self):
        """Guess probability decreases with difficulty."""
        guesses = [slip_guess_for_difficulty(d)[1] for d in range(1, 6)]
        assert guesses == sorted(guesses, reverse=True)

    def test_monotonic_slip(self):
        """Slip probability increases with difficulty."""
        slips = [slip_guess_for_difficulty(d)[0] for d in range(1, 6)]
        assert slips == sorted(slips)

    def test_clamp_difficulty(self):
        """Out-of-range difficulty gets clamped."""
        s1, g1 = slip_guess_for_difficulty(0)
        s2, g2 = slip_guess_for_difficulty(1)
        assert (s1, g1) == (s2, g2)

        s1, g1 = slip_guess_for_difficulty(99)
        s2, g2 = slip_guess_for_difficulty(5)
        assert (s1, g1) == (s2, g2)


class TestBKTUpdate:
    def test_correct_increases_p_know(self):
        """A correct answer should increase P(know)."""
        result = bkt_update(0.5, True, difficulty=2)
        assert result > 0.5

    def test_incorrect_decreases_p_know(self):
        """A wrong answer should decrease P(know)."""
        result = bkt_update(0.5, False, difficulty=2)
        assert result < 0.5

    def test_hard_correct_stronger_than_easy_correct(self):
        """Correct on hard (diff=5) gives larger P(know) increase than easy (diff=1)."""
        easy = bkt_update(0.5, True, difficulty=1)
        hard = bkt_update(0.5, True, difficulty=5)
        assert hard > easy

    def test_hard_wrong_stronger_than_easy_wrong(self):
        """Wrong on hard (diff=5) gives smaller P(know) decrease than easy (diff=1)."""
        easy = bkt_update(0.5, False, difficulty=1)
        hard = bkt_update(0.5, False, difficulty=5)
        # Hard wrong: higher slip means less punishing
        assert hard > easy

    def test_stays_in_bounds(self):
        """P(know) always stays in [0.02, 0.98]."""
        # Start near 1.0, get wrong many times
        p = 0.98
        for _ in range(20):
            p = bkt_update(p, False, difficulty=1)
        assert p >= 0.02

        # Start near 0.0, get correct many times
        p = 0.02
        for _ in range(20):
            p = bkt_update(p, True, difficulty=1)
        assert p <= 0.98


class TestBKTSequence:
    def test_all_correct_converges_high(self):
        obs = [(True, 2)] * 10
        result = bkt_sequence(obs, prior=0.5)
        assert result > 0.80

    def test_all_wrong_converges_low(self):
        obs = [(False, 2)] * 10
        result = bkt_sequence(obs, prior=0.5)
        assert result < 0.30

    def test_mixed_converges_toward_not_know(self):
        """With medium difficulty, wrong answers are more informative than correct ones
        (because guess=0.30 is high — a correct could be luck; slip=0.08 is low —
        getting it wrong is strong evidence of not-knowing)."""
        obs = [(True, 2), (False, 2), (True, 2), (False, 2)]
        result = bkt_sequence(obs, prior=0.5)
        # Equal correct/wrong at medium diff should lean toward not-know
        assert result < 0.5

    def test_hard_correct_converges_high(self):
        """Even a few hard-correct should give high P(know) because
        guess is very low (hard to guess) and slip is moderate."""
        hard = bkt_sequence([(True, 5)] * 10, prior=0.5)
        assert hard > 0.80


class TestConfidence:
    def test_more_evidence_higher_confidence(self):
        c1 = bkt_confidence(0.7, 2)
        c2 = bkt_confidence(0.7, 20)
        assert c2 > c1

    def test_confidence_bounded(self):
        c = bkt_confidence(0.5, 1)
        assert 0.50 <= c <= 0.98

        c = bkt_confidence(0.9, 1000)
        assert 0.50 <= c <= 0.98

    def test_confidence_at_extremes(self):
        """Confidence should be reasonable even with very strong evidence."""
        c = bkt_confidence(0.95, 50)
        assert c >= 0.70


class TestInformationGain:
    def test_max_at_uncertain(self):
        """IG is highest when P(know) ≈ 0.5."""
        ig_uncertain = information_gain(0.5, 3)
        ig_certain = information_gain(0.95, 3)
        assert ig_uncertain > ig_certain

    def test_ig_non_negative(self):
        for p in [0.1, 0.3, 0.5, 0.7, 0.9]:
            for d in range(1, 6):
                ig = information_gain(p, d)
                assert ig >= 0.0

    def test_difficulty_affects_ig(self):
        """Different difficulties yield different IG for same P(know)."""
        igs = {d: information_gain(0.6, d) for d in range(1, 6)}
        # At least some difference
        assert len(set(igs.values())) >= 2


class TestPriorConversion:
    def test_none_returns_uninformed(self):
        assert bkt_prior_from_existing(None) == 0.5

    def test_score_converts(self):
        assert bkt_prior_from_existing(80.0) == 0.8
        assert bkt_prior_from_existing(30.0) == 0.3

    def test_clamped_away_from_extremes(self):
        assert bkt_prior_from_existing(0.0) == 0.1
        assert bkt_prior_from_existing(100.0) == 0.95


class TestBetaUpdate:
    def test_correct_increases_alpha(self):
        a, b = beta_update(2.0, 2.0, difficulty=2, is_correct=True)
        assert a > 2.0
        assert b == 2.0

    def test_wrong_increases_beta(self):
        a, b = beta_update(2.0, 2.0, difficulty=2, is_correct=False)
        assert a == 2.0
        assert b > 2.0

    def test_difficulty_weight(self):
        """Harder correct should add more to alpha."""
        a_easy, _ = beta_update(2.0, 2.0, difficulty=1, is_correct=True)
        a_hard, _ = beta_update(2.0, 2.0, difficulty=5, is_correct=True)
        assert a_hard > a_easy


class TestPriorFromRecord:
    def test_none_returns_uniform(self):
        a, b = prior_from_mastery_record(None)
        assert a == 1.0 and b == 1.0

    def test_high_score_biased_alpha(self):
        a, b = prior_from_mastery_record({"score": 80.0, "evidence_count": 10})
        assert a > b

    def test_low_score_biased_beta(self):
        a, b = prior_from_mastery_record({"score": 20.0, "evidence_count": 10})
        assert b > a


class TestSkillEstimate:
    def test_mastered(self):
        est = skill_estimate(9.0, 1.0)
        assert est["p_know"] > 0.85
        assert est["level"] == "mastered"

    def test_novice(self):
        est = skill_estimate(1.0, 9.0)
        assert est["p_know"] < 0.40
        assert est["level"] == "novice"

    def test_score_scale(self):
        est = skill_estimate(7.0, 3.0)
        assert 0 <= est["score"] <= 100

    def test_uncertainty_decreases_with_evidence(self):
        est_low = skill_estimate(3.0, 3.0)     # total 6
        est_high = skill_estimate(15.0, 15.0)   # total 30
        assert est_high["uncertainty"] < est_low["uncertainty"]
