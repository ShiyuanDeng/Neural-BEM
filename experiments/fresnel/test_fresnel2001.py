"""Acquisition/calibration checks and independent circle-series PDE control."""
from dataclasses import replace
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "solvers"):
    sys.path.insert(0, str(path))

import numpy as np
import pytest
from scipy.constants import c
from scipy.special import hankel1

from solvers.io.fresnel2001 import load_fresnel2001, calibrate_line_sources
from experiments.fresnel.run_fresnel2001 import (
    coefficient_slots, curve_from_parameters, coefficient_directions, forward,
)
from gpr_bem_kress.shape_derivative import linearize_kress_forward
from gpr_bem_mod.cylinder_reference import penetrable_cylinder_scattered_field
from ordered_boundary import circle

DATA = ROOT / "data/fresnel/dielTM_dec8f.exp"


def test_mirror_layout_and_physical_frequency():
    data = load_fresnel2001(DATA)
    assert data.total.shape == (8, 36, 49)
    assert len(data.header) == 0
    np.testing.assert_array_equal(data.frequencies_hz, np.arange(1, 9) * 1e9)
    assert data.receiver_labels[0, 0] == 13
    assert data.receiver_labels[1, 0] == 15
    assert data.receiver_labels[9, -1] == 7
    assert data.total[0, 0, 0] == 0.251 - 0.2042j
    assert data.incident[0, 0, 0] == 0.30315 - 0.19505j
    assert data.scattered[0, 0, 0] == data.total[0, 0, 0] - data.incident[0, 0, 0]


def test_original_header_and_shuffled_rows(tmp_path):
    table = np.loadtxt(DATA)
    np.random.default_rng(17).shuffle(table)
    path = tmp_path / "original.exp"
    header = "\n".join(f"Fresnel header line {i}" for i in range(10))
    np.savetxt(path, table, header=header, comments="")
    parsed = load_fresnel2001(path)
    assert len(parsed.header) == 10
    np.testing.assert_array_equal(parsed.total, load_fresnel2001(DATA).total)


@pytest.mark.parametrize("corruption, message", [
    ("duplicate", "Duplicate"), ("missing", "Missing"), ("nan", "finite"),
    ("bad_tx", "labels"), ("fractional_rx", "integers"), ("bad_aperture", "aperture"),
    ("zero_frequency", "positive"), ("extra_column", "seven"),
])
def test_invalid_records_rejected(tmp_path, corruption, message):
    table = np.loadtxt(DATA)
    if corruption == "duplicate": table = np.vstack((table, table[0]))
    elif corruption == "missing": table = table[1:]
    elif corruption == "nan": table[0, 4] = np.nan
    elif corruption == "bad_tx": table[0, 0] = 37
    elif corruption == "fractional_rx": table[0, 1] = 13.5
    elif corruption == "bad_aperture": table[0, 1] = 1
    elif corruption == "zero_frequency": table[0, 2] = 0
    elif corruption == "extra_column": table = np.column_stack((table, table[:, 0]))
    path = tmp_path / "bad.exp"
    np.savetxt(path, table)
    with pytest.raises(ValueError, match=message):
        load_fresnel2001(path)


def synthetic_incident_data():
    data = load_fresnel2001(DATA)
    points = data.receiver_points[data.receiver_labels - 1]
    distance = np.linalg.norm(points - data.source_points[:, None, :], axis=-1)
    gains = (1 + 0.1 * np.arange(36)[None, :]) * np.exp(1j * np.arange(8)[:, None] / 3)
    incident = gains[:, :, None] * 0.25j * hankel1(0, 2 * np.pi * data.frequencies_hz[:, None, None] / c * distance)
    return replace(data, incident=incident, total=incident), gains


def test_calibration_recovers_complex_source_gains():
    data, gains = synthetic_incident_data()
    fitted = calibrate_line_sources(data)
    np.testing.assert_allclose(fitted.source_strengths, gains, rtol=1e-13)
    np.testing.assert_allclose(fitted.predicted_incident, data.incident, rtol=1e-13)
    assert max(fitted.relative_incident_error) < 1e-13


def test_calibration_rejects_missing_reference():
    data, _ = synthetic_incident_data()
    broken = data.incident.copy()
    broken[2, 4, 24] = 0
    with pytest.raises(ValueError, match="zero measured"):
        calibrate_line_sources(replace(data, incident=broken))


@pytest.mark.parametrize("fi", [0, 3, 7])
def test_kress_matches_independent_cylinder_series(fi):
    data, gains = synthetic_incident_data()
    calibration = calibrate_line_sources(data)
    curve = circle((0.0, 0.025), 0.015).discretize(64)
    computed = data.select_receiver_pairs(forward(data, calibration, curve, fi).scattered_receiver)
    selected = [(0, 0), (1, 24), (10, 48), (35, 1)]
    sources = np.array([data.source_points[t] for t, r in selected])
    receivers = np.array([data.receiver_points[data.receiver_labels[t, r] - 1] for t, r in selected])
    wave = 2 * np.pi * data.frequencies_hz[fi] / c
    exact = penetrable_cylinder_scattered_field(
        receivers, sources, k_exterior=wave, k_interior=wave * np.sqrt(3),
        radius=0.015, center=(0.0, 0.025),
        source_strength=np.array([gains[fi, t] for t, r in selected]))
    found = np.array([computed[t, r] for t, r in selected])
    assert np.linalg.norm(found - exact) / np.linalg.norm(exact) < 2e-7


def test_measured_acquisition_cartesian_jacobian_matches_fd():
    data = load_fresnel2001(DATA)
    calibration = calibrate_line_sources(data)
    slots = coefficient_slots(2)
    parameters = np.zeros(len(slots))
    parameters[slots.index(("cos", 0, 1))] = 25
    parameters[slots.index(("cos", 1, 0))] = 15
    parameters[slots.index(("sin", 1, 1))] = 15
    curve = curve_from_parameters(parameters, 2, 64)
    base = forward(data, calibration, curve, 3)
    for index in [0, 2, 7]:
        direction = coefficient_directions(curve, 2)[index]
        analytic = data.select_receiver_pairs(linearize_kress_forward(base, direction).d_scattered_receiver)
        step_mm = 1e-3
        plus, minus = parameters.copy(), parameters.copy()
        plus[index] += step_mm
        minus[index] -= step_mm
        up = forward(data, calibration, curve_from_parameters(plus, 2, 64), 3)
        down = forward(data, calibration, curve_from_parameters(minus, 2, 64), 3)
        fd = data.select_receiver_pairs(up.scattered_receiver - down.scattered_receiver) / (2 * step_mm)
        assert np.linalg.norm(analytic - fd) / np.linalg.norm(fd) < 2e-6
