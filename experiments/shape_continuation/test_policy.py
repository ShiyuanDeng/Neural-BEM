"""The admission rule, the probe accounting, and what each arm is allowed to see."""
import numpy as np
import pytest

from .atlas import Whitening, cell_at
from .continuation import Decision, run_adaptive
from .forward import Acquisition, Work, solve
from .geometry import FourierCurve
from .inverse import FitConfig, Observation
from .policy import (AtlasPolicy, detection_thresholds, harmonic_horizons,
                     harmonic_sensitivity, probe, window_band)
from .run import fixture


def observations(wavenumbers, contrast=0.33, nodes=384, scene="glider"):
    truth = fixture(scene)
    out = []
    for wavenumber in wavenumbers:
        acquisition = Acquisition.ring(max(4, int(10 * wavenumber)), max(4, int(10 * wavenumber)))
        out.append(Observation(wavenumber, acquisition,
                               solve(truth, wavenumber, contrast, acquisition, nodes).prediction))
    return tuple(out)


def test_detection_threshold_is_the_displacement_that_reaches_one_sigma():
    """A displacement at the threshold must move the data by one noise unit."""
    shape, contrast, band, nodes = FourierCurve.circle(1.0), 0.33, 6, 256
    observation = observations([3.0], contrast, nodes=512)[0]
    whitening = Whitening("relative", 1e-3)
    cell = cell_at(shape, observation, contrast, band, nodes, whitening=whitening)
    perimeter = float(shape.nodes(1024).perimeter)
    thresholds = detection_thresholds(harmonic_sensitivity(cell), perimeter)
    # Column p carries SNR s_p for a unit coefficient, i.e. RMS 1/sqrt(L).
    sensitivity = harmonic_sensitivity(cell)
    assert np.allclose(thresholds[1:] * sensitivity[1:] * np.sqrt(perimeter), 1.0)
    assert np.all(np.diff(thresholds[1:6]) > 0)  # higher harmonics need more motion


def test_harmonic_horizons_saturate_and_fall_with_sensitivity():
    sensitivity = np.array([1.0, 1.0, 0.8, 0.4, 0.05, 1e-6])
    horizons = harmonic_horizons(sensitivity, 0.02, 2.0)
    assert np.allclose(horizons[:3], 0.02)          # saturated at the ceiling
    assert np.isclose(horizons[3], 0.02 * 0.8)      # linear below it
    assert horizons[5] < 1e-5
    assert np.all(harmonic_horizons(sensitivity, float("nan"), 2.0) == 0)


def test_window_band_needs_both_detectability_and_predictability():
    """A harmonic detectable only beyond its own horizon is refused."""
    sensitivity = np.array([50.0, 50.0, 50.0, 4.0, 1e-3])
    perimeter = 2 * np.pi
    generous = window_band(sensitivity, perimeter, 1.0)
    strict = window_band(sensitivity, perimeter, 1e-3)
    assert generous >= 3 > strict
    assert window_band(sensitivity, perimeter, 1.0, safety=1e-9) == 1


def test_window_band_is_contiguous():
    sensitivity = np.array([50.0, 50.0, 1e-9, 50.0, 50.0])
    assert window_band(sensitivity, 2 * np.pi, 1.0) == 1


def test_window_band_is_insensitive_to_the_safety_factor():
    """Sensitivity decays exponentially past the frontier, so the cut is sharp."""
    harmonics = np.arange(41)
    sensitivity = 1e5 * np.exp(-np.clip(harmonics - 12, 0, None) ** 2 / 8)
    bands = [window_band(sensitivity, 2 * np.pi, 0.03, safety=safety)
             for safety in (1.0, 0.1, 0.01)]
    assert max(bands) - min(bands) <= 3


def test_probe_charges_every_solve_to_the_shared_budget():
    shape, contrast = FourierCurve.circle(1.0), 0.33
    observation = observations([2.0], contrast, nodes=512)[0]
    work = Work(max_forwards=50, max_seconds=120)
    report = probe(shape, observation, contrast, probe_band=10, storage_band=40,
                   nodes=192, whitening=Whitening("relative", 1e-3), work=work,
                   radius=0.06, safety=1.0, horizon_tolerance=0.1,
                   brackets=(2.0, 1.0, 0.5, 0.25))
    assert report.forwards == work.attempted >= 2
    assert report.band >= 1
    assert report.horizon_rungs
    if report.usable:
        assert 0 < report.horizon <= 0.12


def test_probe_reports_a_horizon_that_matches_its_own_criterion():
    shape, contrast = FourierCurve.circle(1.0), 0.33
    observation = observations([4.0], contrast, nodes=512)[0]
    report = probe(shape, observation, contrast, probe_band=16, storage_band=48,
                   nodes=256, whitening=Whitening("relative", 1e-3),
                   work=Work(max_forwards=60, max_seconds=180), radius=0.03,
                   safety=1.0, horizon_tolerance=0.1, brackets=(2.0, 1.0, 0.5, 0.25))
    assert report.usable
    accepted = [rung for rung in report.horizon_rungs if rung.get("relative_error", 1) <= 0.1]
    assert accepted and np.isclose(report.horizon, accepted[0]["achieved"])
    rejected = [rung for rung in report.horizon_rungs if rung.get("relative_error", 0) > 0.1]
    assert all(rung["amplitude"] > report.horizon for rung in rejected)


@pytest.mark.parametrize("mode,probes", (("fixed", 0), ("band", 1)))
def test_arms_differ_only_in_what_they_measure(mode, probes):
    contrast = 0.33
    data = observations([1.0, 1.25, 1.5], contrast, nodes=384)
    work = Work(max_forwards=400, max_seconds=300)
    policy = AtlasPolicy(observations=data, contrast=contrast, work=work, mode=mode,
                         config=FitConfig(max_iterations=1), k_stop=1.5,
                         points_per_wavelength=20.0, minimum_nodes=96)
    result = run_adaptive(FourierCurve.circle(1.0), data, contrast, policy,
                          work=work, max_decisions=3)
    assert len(policy.decisions) >= 1
    assert (len(policy.probes) >= probes) if probes else (policy.probes == [])
    assert [d["wavenumber"] for d in policy.decisions][:3] == [1.0, 1.25, 1.5][:len(policy.decisions)]
    assert result.stop_reason in ("policy_stop", "decision_limit", "budget_exhausted")


def test_a_fixed_arm_reproduces_the_prescribed_band_rule():
    contrast, perimeter = 10.0, 2 * np.pi
    policy = AtlasPolicy(observations=observations([1.0], contrast, nodes=768),
                         contrast=contrast, work=Work(), mode="fixed")
    assert policy.prescribed_band(2.0, perimeter) == int(np.floor(3 * 2.0 * np.sqrt(10)))
    policy.band_rule = "driver"
    assert policy.prescribed_band(2.0, perimeter) == int(np.floor(2 * 2.0 * perimeter / (2 * np.pi)))


def test_candidate_order_walks_down_from_the_boldest_jump():
    policy = AtlasPolicy(observations=observations([1.0], 0.33, nodes=384),
                         contrast=0.33, work=Work(), maximum_probes=3)
    order = [float(v) for v in policy.candidate_order(np.array([1.25, 1.5, 1.75, 2.0, 2.5]))]
    assert order[0] == 2.5 and order[-1] == 1.25
    assert order == sorted(order, reverse=True)


def test_jumps_are_capped_and_the_top_is_refined_only_while_progress_continues():
    policy = AtlasPolicy(observations=observations([1.0], 0.33, nodes=384),
                         contrast=0.33, work=Work(), maximum_jump=2.0, k_stop=8.0)
    policy.grid = np.arange(1.0, 8.25, 0.25)
    context = type("C", (), dict(history=(), shape=None, work={}))()
    assert list(policy.candidates(1.0, context)) == list(np.arange(1.25, 2.01, 0.25))
    assert len(policy.candidates(8.0, context)) == 0  # no history means no progress
