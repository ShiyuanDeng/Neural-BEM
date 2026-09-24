"""Band rules (SC-023) and band policies (SC-025) choose what they declare."""
from types import SimpleNamespace

import numpy as np

from . import conditional_rules as cr
from .policy_cases import BandPolicy, HELD_OUT, held_out_curve, progress_chooser


def rows(**columns):
    bands = columns.pop("band")
    return [dict(band=b, **{k: v[i] for k, v in columns.items()}) for i, b in enumerate(bands)]


def test_declared_rules_on_a_synthetic_decision():
    group = rows(band=[2, 4, 8, 16, 32], capture=[.3, .6, .92, .97, 1.], validation_fraction=[.1, .3, .3, .2, -.1],
                 dof_ratio=[1., .9, .7, .45, .2])
    assert cr.ladder(group, dict(ladder_band=9)) == 8
    assert cr.fixed(group, {}) == 32
    assert cr.knee(group, {}) == 8
    assert cr.validation(group, {}) == 4  # ties go to the smaller band
    assert cr.dof(group, {}) == 8
    assert cr.validation(rows(band=[2, 4], capture=[1, 1], validation_fraction=[None, None], dof_ratio=[1, 1]), {}) is None


def test_evaluation_reports_regret_against_the_best_band():
    candidates = []
    for band, gain, capture in ((2, .1, .5), (4, .4, .95), (8, .2, 1.)):
        candidates.append(dict(arm="a", case="c", state=0, stage=1, f_max_hz=5e8, damping=1e-3, control="physical",
                               gate="G1", band=band, gain=gain, capture=capture, validation_fraction=None,
                               dof_ratio=1., admissible=True, halving=0, first_order_gain=0., distance_before_m=1.))
    (result,) = cr.evaluate(candidates, {5e8: 3})
    assert result["oracle_band"] == 4 and result["oracle_gain"] == .4
    assert result["ladder"]["band"] == 2 and np.isclose(result["ladder"]["regret"], .3)
    assert result["knee"]["band"] == 4 and result["knee"]["regret"] == 0


def test_progress_controller_doubles_only_after_a_stalled_stage():
    choose = progress_chooser([3, 5, 7, 9])
    stage = lambda stop, start, end: SimpleNamespace(stop_reason=stop, initial_loss=start, final_loss=end)
    assert choose(None, [])[0] == 3
    assert choose(None, [stage("gradient_tolerance", 1., .5)])[0] == 5
    assert choose(None, [None, stage("no_decreasing_step", 1., .95)])[0] == 10  # stalled: 2 x 5
    assert choose(None, [None, None, stage("no_decreasing_step", 1., .5)])[0] == 10  # progressing: keep


def test_band_policy_records_decisions_and_stops_after_its_stages():
    template = SimpleNamespace(label="s1", update_modes=3)
    from dataclasses import dataclass, replace

    @dataclass(frozen=True)
    class Stage:
        label: str
        update_modes: int
    policy = BandPolicy([Stage("s1", 3)], lambda t, h: (7, dict(reason="test")), "test")
    assert policy.next_stage([]) == Stage("s1", 7)
    assert policy.decisions == [dict(stage="s1", band=7, reason="test")]
    assert policy.next_stage([object()]) is None


def test_held_out_truths_are_valid_counterclockwise_curves():
    for name in HELD_OUT:
        curve = held_out_curve(name)
        curve.validate()
        assert curve.band in (8, 10)
