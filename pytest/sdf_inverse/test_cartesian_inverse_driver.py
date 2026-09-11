"""Physical driver checks for the MLP-free Cartesian entry point."""
import json

import run_explicit_cartesian_fourier_inverse as driver
import run_mlp_sdf_inverse_comparison as radial_driver
import sdf_inverse.neural_optimization as inverse


def test_circle_driver_never_uses_neural_work_or_unrelated_star_reference(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Cartesian curve-only driver entered neural work')

    monkeypatch.setattr(radial_driver.SmoothMLPSDF2D, '__init__', forbidden)
    monkeypatch.setattr(driver.torch.nn.Identity, 'forward', forbidden)
    for name in ('_field_audit', '_audit_points', 'redistance_neural_sdf_to_curve',
                 'build_ordered_sdf_geometry'):
        monkeypatch.setattr(inverse, name, forbidden)
    # Analytic initialization is extracted once by the driver. All inverse
    # steps use explicit curves; no network extraction is allowed in the loop.
    assert driver.main(['--target', 'circle', '--initial-shape', 'circle',
        '--train-ghz', '0.5', '--holdout-ghz', '1.0', '--num-pairs', '2',
        '--num-nodes', '32', '--maximum-mode', '2', '--outer-iterations', '1',
        '--continuation-strategy', 'none', '--output-dir', str(tmp_path)]) == 0
    metrics = json.loads((tmp_path / 'metrics.json').read_text())
    assert metrics['results']['accepted_updates'] == 1
    assert metrics['results']['final_train_relative_l2'] < metrics['results']['initial_train_relative_l2']
    assert not metrics['parity_evaluated']
    assert metrics['parity_achieved'] is None
    assert metrics['reference_run'] is None
    assert 'target' in metrics['parity_reference_mismatches']
    assert '1.068e-08' not in (tmp_path / 'summary.md').read_text()


def test_saved_star_reference_is_applicable_to_the_matched_problem():
    args = driver._parse_args([])
    args.num_nodes = 128
    assert driver._reference_mismatches(args) == []
