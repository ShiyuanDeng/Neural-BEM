"""Guard EW-001 reproduction coverage and registered cost decision."""
import pytest
from .ew001 import compare_rows, terminal


def row(error, block='T'):
    return dict(contrast=4., frequency_hz=2.5e9, kind='real', grid=256,
                trace_cutoff=128, block=block, normalized_max_diagonal_error=error)


def test_reproduction_gate_preserves_coverage_and_tolerance():
    assert compare_rows([row(.04)], [row(.04)])['passed']
    assert not compare_rows([row(.04+2e-12)], [row(.04)])['passed']
    with pytest.raises(ValueError):
        compare_rows([row(.04, 'V')], [row(.04)])
    with pytest.raises(ValueError):
        compare_rows([row(.04), row(.04)], [row(.04)])


def test_decision_requires_circle_pass_and_cost_at_both_widths():
    assert terminal(False, [.1, .1]) == 'CIRCLE_FAILS_AT_UNREGISTERED_SPLIT'
    assert terminal(True, [.49, .49]) == 'CIRCLE_QUALIFIED_AND_COST_PLAUSIBLE'
    assert terminal(True, [.49, .5]) == 'CIRCLE_QUALIFIED_BUT_UNECONOMIC_2D'
