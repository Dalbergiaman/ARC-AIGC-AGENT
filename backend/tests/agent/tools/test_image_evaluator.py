"""Unit tests for image_evaluator — weight calculation only, no LLM calls."""
import pytest

from agent.tools.image_evaluator import (
    _WEIGHTS_NO_REF,
    _WEIGHTS_WITH_REF,
    _RawScores,
    _compute_weighted_score,
)


def test_weights_no_ref_sum_to_one():
    assert abs(sum(_WEIGHTS_NO_REF.values()) - 1.0) < 1e-9


def test_weights_with_ref_sum_to_one():
    assert abs(sum(_WEIGHTS_WITH_REF.values()) - 1.0) < 1e-9


def test_no_ref_excludes_reference_score():
    assert "reference_score" not in _WEIGHTS_NO_REF


def test_with_ref_includes_reference_score():
    assert "reference_score" in _WEIGHTS_WITH_REF


def test_compute_weighted_score_no_ref_perfect():
    scores = _RawScores(
        style_score=1.0,
        material_score=1.0,
        lighting_score=1.0,
        composition_score=1.0,
        quality_score=1.0,
        reference_score=None,
        feedback="perfect",
    )
    result = _compute_weighted_score(scores, has_reference=False)
    assert abs(result - 1.0) < 1e-4


def test_compute_weighted_score_no_ref_zero():
    scores = _RawScores(
        style_score=0.0,
        material_score=0.0,
        lighting_score=0.0,
        composition_score=0.0,
        quality_score=0.0,
        reference_score=None,
        feedback="zero",
    )
    result = _compute_weighted_score(scores, has_reference=False)
    assert result == 0.0


def test_compute_weighted_score_with_ref_perfect():
    scores = _RawScores(
        style_score=1.0,
        material_score=1.0,
        lighting_score=1.0,
        composition_score=1.0,
        quality_score=1.0,
        reference_score=1.0,
        feedback="perfect",
    )
    result = _compute_weighted_score(scores, has_reference=True)
    assert abs(result - 1.0) < 1e-4


def test_compute_weighted_score_precision():
    # style=0.8 (30%), material=0.6 (20%), lighting=0.7 (20%),
    # composition=0.9 (15%), quality=0.5 (15%) → no ref
    scores = _RawScores(
        style_score=0.8,
        material_score=0.6,
        lighting_score=0.7,
        composition_score=0.9,
        quality_score=0.5,
        reference_score=None,
        feedback="test",
    )
    expected = 0.8 * 0.30 + 0.6 * 0.20 + 0.7 * 0.20 + 0.9 * 0.15 + 0.5 * 0.15
    result = _compute_weighted_score(scores, has_reference=False)
    assert abs(result - expected) < 1e-4


def test_score_clamped_to_range():
    scores = _RawScores(
        style_score=1.5,    # over 1.0, should be clamped
        material_score=-0.1, # under 0.0, should be clamped
        lighting_score=0.5,
        composition_score=0.5,
        quality_score=0.5,
        reference_score=None,
        feedback="clamp test",
    )
    assert scores.style_score == 1.0
    assert scores.material_score == 0.0
