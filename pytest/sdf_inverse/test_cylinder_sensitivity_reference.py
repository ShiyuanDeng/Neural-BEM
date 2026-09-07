"""Independent exact-zero-contrast material sensitivity oracle checks."""

import numpy as np
import pytest
from scipy.special import hankel1

from gpr_bem_ref.cylinder_reference import (
    penetrable_cylinder_scattering_coefficient_ratio,
)
from sdf_inverse.cylinder_sensitivity_reference import (
    matched_material_cylinder_epsr_jvp,
)


@pytest.fixture
def case():
    center = np.asarray((0.013, -0.021))
    angle = np.asarray((0.12, 1.8, 4.4))
    return {
        "source_points": center + 0.27 * np.column_stack((np.cos(angle), np.sin(angle))),
        "receiver_points": center + 0.23 * np.column_stack((np.cos(angle + 0.16), np.sin(angle + 0.16))),
        "angular_frequency": 2.0 * np.pi * 0.8e9,
        "exterior_epsr": 4.0,
        "interior_epsr": 4.0,
        "exterior_epsr_direction": -0.3,
        "interior_epsr_direction": 0.8,
        "eps0": 8.8541878128e-12,
        "mu0": 4.0e-7 * np.pi,
        "radius": 0.047,
        "center": center,
        "maximum_mode": 64,
        "source_strength": np.asarray((1.0 + 0.2j, -0.4 + 0.8j, 0.0 - 1.3j)),
    }


def _fixed_mode_mie(case, parameter):
    """Use frozen-reference coefficients, keeping all mode indices fixed."""

    modes = np.arange(-case["maximum_mode"], case["maximum_mode"] + 1)
    material_scale = case["angular_frequency"] * np.sqrt(case["eps0"] * case["mu0"])
    exterior = material_scale * np.sqrt(
        case["exterior_epsr"] + parameter * case["exterior_epsr_direction"]
    )
    interior = material_scale * np.sqrt(
        case["interior_epsr"] + parameter * case["interior_epsr_direction"]
    )
    coefficient = penetrable_cylinder_scattering_coefficient_ratio(
        modes, exterior, interior, case["radius"],
    )
    sources = case["source_points"] - case["center"]
    receivers = case["receiver_points"] - case["center"]
    phase = np.arctan2(receivers[:, 1], receivers[:, 0]) - np.arctan2(sources[:, 1], sources[:, 0])
    return case["source_strength"] * 0.25j * np.sum(
        hankel1(modes, exterior * np.linalg.norm(sources, axis=1)[:, None])
        * coefficient
        * hankel1(modes, exterior * np.linalg.norm(receivers, axis=1)[:, None])
        * np.exp(1j * phase[:, None] * modes),
        axis=1,
    )


def test_analytic_epsr_jvp_matches_fixed_mode_mie_central_fd_ladder(case):
    exact = matched_material_cylinder_epsr_jvp(**case)
    assert exact.shape == (3,)
    assert exact.dtype == np.complex128
    assert not exact.flags.writeable
    assert np.linalg.norm(exact) > 1e-4
    errors = []
    for step in (1e-1, 1e-2, 1e-3, 1e-4, 1e-5):
        difference = (_fixed_mode_mie(case, step) - _fixed_mode_mie(case, -step)) / (2 * step)
        errors.append(np.linalg.norm(difference - exact) / np.linalg.norm(exact))
    assert errors[1] < 0.02 * errors[0], errors
    assert errors[2] < 0.02 * errors[1], errors
    assert min(errors) < 2e-9, errors


def test_complex_strengths_pairing_and_fixed_cutoff_refinement(case):
    result = matched_material_cylinder_epsr_jvp(**case)
    unit = matched_material_cylinder_epsr_jvp(**(case | {"source_strength": 1.0}))
    np.testing.assert_allclose(result, unit * case["source_strength"], rtol=2e-14, atol=0)
    refined = matched_material_cylinder_epsr_jvp(**(case | {"maximum_mode": 72}))
    np.testing.assert_allclose(result, refined, rtol=2e-14, atol=1e-16)
    for index in range(3):
        single = matched_material_cylinder_epsr_jvp(**(case | {
            "source_points": case["source_points"][index:index + 1],
            "receiver_points": case["receiver_points"][index:index + 1],
            "source_strength": case["source_strength"][index],
        }))
        assert single.shape == (1,)
        np.testing.assert_allclose(single[0], result[index], rtol=2e-14, atol=0)


def test_common_material_change_and_zero_strength_are_exact_null_directions(case):
    for direction in (0.0, 0.6, -1.2):
        result = matched_material_cylinder_epsr_jvp(**(case | {
            "exterior_epsr_direction": direction,
            "interior_epsr_direction": direction,
        }))
        np.testing.assert_array_equal(result, np.zeros(3, dtype=complex))
    result = matched_material_cylinder_epsr_jvp(**(case | {"source_strength": 0j}))
    np.testing.assert_array_equal(result, np.zeros(3, dtype=complex))


def test_exterior_and_interior_directions_are_opposite_at_match(case):
    interior = matched_material_cylinder_epsr_jvp(**(case | {
        "exterior_epsr_direction": 0.0, "interior_epsr_direction": 1.0,
    }))
    exterior = matched_material_cylinder_epsr_jvp(**(case | {
        "exterior_epsr_direction": 1.0, "interior_epsr_direction": 0.0,
    }))
    np.testing.assert_array_equal(interior, -exterior)


def test_translating_circle_and_acquisition_preserves_oracle(case):
    shift = np.asarray((-0.025, 0.17))
    translated = case | {
        "center": case["center"] + shift,
        "source_points": case["source_points"] + shift,
        "receiver_points": case["receiver_points"] + shift,
    }
    np.testing.assert_allclose(
        matched_material_cylinder_epsr_jvp(**case),
        matched_material_cylinder_epsr_jvp(**translated),
        rtol=2e-13, atol=1e-15,
    )


@pytest.mark.parametrize(("changes", "error", "message"), [
    ({"interior_epsr": 4.0 + 1e-12}, ValueError, "exactly equal"),
    ({"interior_epsr": -1.0}, ValueError, "positive"),
    ({"exterior_epsr": 0.0}, ValueError, "positive"),
    ({"exterior_epsr": complex(4.0)}, TypeError, "real scalar"),
    ({"angular_frequency": np.inf}, ValueError, "finite"),
    ({"eps0": 0.0}, ValueError, "positive"),
    ({"mu0": -1.0}, ValueError, "positive"),
    ({"radius": 0.0}, ValueError, "positive"),
    ({"center": [np.nan, 0.0]}, ValueError, "finite"),
    ({"center": [0j, 0j]}, ValueError, "real-valued"),
    ({"maximum_mode": 4}, ValueError, "at least"),
    ({"maximum_mode": 64.0}, TypeError, "integer"),
    ({"maximum_mode": True}, TypeError, "integer"),
    ({"interior_epsr_direction": np.nan}, ValueError, "finite"),
    ({"exterior_epsr_direction": 1j}, TypeError, "real scalar"),
    ({"source_strength": [1.0, 2.0]}, ValueError, "one value per pair"),
    ({"source_strength": np.inf}, ValueError, "finite"),
    ({"source_points": np.ones((3, 2), dtype=complex)}, ValueError, "real-valued"),
    ({"receiver_points": []}, ValueError, "non-empty shape"),
    ({"receiver_points": np.ones((2, 2))}, ValueError, "same paired shape"),
])
def test_invalid_inputs_fail_explicitly(case, changes, error, message):
    with pytest.raises(error, match=message):
        matched_material_cylinder_epsr_jvp(**(case | changes))


@pytest.mark.parametrize("field", ["source_points", "receiver_points"])
def test_interior_acquisition_is_rejected_even_for_null_direction(case, field):
    points = case[field].copy()
    points[0] = case["center"]
    with pytest.raises(ValueError, match="strictly exterior"):
        matched_material_cylinder_epsr_jvp(**(case | {
            field: points, "exterior_epsr_direction": 0.0, "interior_epsr_direction": 0.0,
        }))


def test_coincident_paired_source_and_receiver_rejected(case):
    with pytest.raises(ValueError, match="distinct"):
        matched_material_cylinder_epsr_jvp(**(case | {"receiver_points": case["source_points"]}))
