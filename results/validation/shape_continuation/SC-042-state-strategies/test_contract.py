"""Check scientific intervention identity and loss-independent input selection."""
import importlib.util
from pathlib import Path
import numpy as np

spec = importlib.util.spec_from_file_location('sc042_tested', Path(__file__).with_name('run.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_once_and_boundary_share_first_state_but_differ_later():
    c = np.zeros(385, complex)
    c[193] = 1
    c[192+70] = .0001
    curve = runner.FourierCurve(c)
    a, _ = runner.treatment(curve, 'once', 0)
    b, _ = runner.treatment(curve, 'boundary', 0)
    cap, _ = runner.treatment(curve, 'cap', 0)
    assert np.array_equal(a.coefficients, b.coefficients)
    assert np.array_equal(a.values(1024), cap.values(1024))
    later_once, cleaned = runner.treatment(curve, 'once', 1)
    assert not cleaned and np.array_equal(later_once.coefficients, curve.coefficients)
    later_boundary, cleaned = runner.treatment(curve, 'boundary', 1)
    assert cleaned and later_boundary.coefficients[262] == 0


def test_all_arms_have_matched_data_M_nodes_and_work():
    for case in runner.CASES:
        configurations = [runner.stages_for(case, a) for a in runner.ARMS]
        first = configurations[0]
        for entry in configurations[1:]:
            assert np.array_equal(first[0].coefficients, entry[0].coefficients)
            assert first[2] == entry[2]
            for a, b in zip(first[1], entry[1]):
                assert (a.update_modes, a.nodes, a.refined_nodes, a.quota, a.weights) == (b.update_modes, b.nodes, b.refined_nodes, b.quota, b.weights)
                assert all(np.array_equal(x.scattered, y.scattered) for x, y in zip(a.observations, b.observations))


def test_committed_starts_have_expected_bands_and_finite_losses():
    for case in runner.CASES:
        curve, path, loss, nodes = runner.start_record(case)
        assert path.suffix == '.json' and path.exists()
        assert curve.band == 192 and np.isfinite(loss) and loss >= 0
        assert nodes > 2*curve.band
