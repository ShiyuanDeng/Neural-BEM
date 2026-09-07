"""Independent perturbation paths and evidence gates for the E experiment."""

import json

import numpy as np
import pytest

import run_kress_shape_derivative_validation as study


@pytest.mark.parametrize("name", ["circle", "ellipse", "star"])
def test_declared_paths_have_exact_coherent_directional_jets(name):
    cosine, sine, _ = study._case_coefficients(name)
    parameters = 2*np.pi*np.arange(64)/64
    for direction in study._directions(cosine, sine):
        step = 1e-5
        negative = study._path(cosine, sine, direction, -step).evaluate(parameters)
        positive = study._path(cosine, sine, direction, step).evaluate(parameters)
        derivatives = study._direction_jets(direction, parameters)
        for attribute, exact in zip(("points", "first_derivatives", "second_derivatives", "third_derivatives"), derivatives):
            finite_difference = (getattr(positive, attribute)-getattr(negative, attribute))/(2*step)
            np.testing.assert_allclose(finite_difference, exact, rtol=3e-8, atol=2e-10)


def test_reference_and_production_pairing_use_complex_strengths_consistently():
    cosine, sine, _ = study._case_coefficients("circle")
    producer = study.fourier_curve(cosine, sine, component_id="pairing")
    frequencies = np.array([2*np.pi*.5e9])
    acquisition = study._acquisition()
    work = dict(production_forward_solves=0, mie_reference_evaluations=0)
    exact = study._mie_reference(producer, frequencies, 6., 3., acquisition, work=work)
    actual = study._paired(study._solve(producer, 64, frequencies, 6., 3., acquisition, work=work))
    np.testing.assert_allclose(actual, exact, rtol=2e-10, atol=1e-20)
    np.testing.assert_array_equal(exact[0], exact[-1])
    assert work == dict(production_forward_solves=1, mie_reference_evaluations=1)


def test_observation_transform_is_fixed_and_real_stacked():
    observed = np.array([[1+2j, 0j], [-.5+.3j, 0j], [2-.3j, 0j]])*1e-7
    transform = study._transform(observed)
    assert np.all(np.isfinite(transform))
    before = transform.copy()
    predicted = observed + (1e-8+2e-8j)
    direction = np.array([[1., .4], [.2, -.7], [.8, .1]])*(1e-8-.3e-8j)
    delta = predicted-observed
    analytical = float((transform @ np.r_[delta.real.ravel(), delta.imag.ravel()])
                       @ (transform @ np.r_[direction.real.ravel(), direction.imag.ravel()]))
    h = 1e-4
    fd = (study._loss(predicted+h*direction, observed, transform)
          - study._loss(predicted-h*direction, observed, transform))/(2*h)
    assert fd == pytest.approx(analytical, rel=2e-10)
    np.testing.assert_array_equal(transform, before)


def test_historical_validation_output_cannot_be_overwritten(tmp_path):
    destination = study._fresh_output(tmp_path/"evidence")
    sentinel = destination/"metrics.json"
    sentinel.write_text("existing", encoding="utf-8")
    with pytest.raises(FileExistsError, match="new or empty"):
        study._fresh_output(destination)
    assert sentinel.read_text(encoding="utf-8") == "existing"


@pytest.mark.parametrize("nodes,discrete,physical,expected", [
    ([32], True, False, 0),
    ([32], False, False, 2),
    ([32, 64], True, True, 0),
    ([32, 64], True, False, 2),
    ([32, 64], False, True, 2),
])
def test_multigrid_cli_requires_physical_gate(nodes, discrete, physical, expected):
    manifest = dict(configuration=dict(nodes=nodes), discrete_gate_passed=discrete,
                    physical_gate_passed=physical)
    assert study._validation_exit_code(manifest) == expected


def test_zero_scattering_fd_error_uses_nonvanishing_incident_field_scale():
    from gpr_bem_kress.shape_derivative import linearize_kress_forward
    cosine, sine, _ = study._case_coefficients("zero_contrast")
    direction = study._directions(cosine, sine)[0]
    work = dict(production_forward_solves=0)
    frequencies = np.array([2*np.pi*.5e9])
    acquisition = study._acquisition()
    base = study._solve(study._path(cosine, sine, direction, 0.), 32, frequencies, 6., 6., acquisition, work=work)
    h = .001
    negative, positive = [study._solve(study._path(cosine, sine, direction, sign*h), 32,
                         frequencies, 6., 6., acquisition, work=work) for sign in (-1., 1.)]
    jvp = linearize_kress_forward(base[0], study._core_direction(direction, base[0].system.geometry))
    metrics = study._fd_errors([jvp], negative, positive, h)
    assert metrics["scattered_mixed_ratio"] < 1.
    assert metrics["scattered_absolute_error"] < 1e-16


def test_tiny_derivative_driver_writes_separate_fixed_node_and_oracle_evidence(tmp_path):
    destination = tmp_path/"new"
    code = study.main(["--output-dir", str(destination), "--cases", "circle", "--nodes", "32",
                       "--frequencies-ghz", ".5", "--steps", ".001", ".0001"])
    metrics = json.loads((destination/"metrics.json").read_text(encoding="utf-8"))
    assert code == 0
    assert metrics["discrete_gate_passed"]
    assert len(metrics["derivative_records"]) == 8
    assert len(metrics["fd_records"]) == 16
    assert metrics["work"]["analytical_jvp_evaluations"] == 8
    assert metrics["cases"]["circle"]["reference"]["identity"] == "independent_fixed_mode_Mie"
    assert metrics["cases"]["circle"]["observation_sha256"]
    assert metrics["provenance"]["source_sha256"]
    with np.load(destination/"arrays.npz", allow_pickle=False) as arrays:
        assert "circle_32_interior_epsr_paired_jvp" in arrays.files
